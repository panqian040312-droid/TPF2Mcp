-- 地形图层采集器（等高线 + 水深的数据源，只读）
--
-- 数据源：`game.interface.getHeight({x, y})` —— 官方接口，游戏自带的战役 mod 用了
-- 20 多处（medal2worms.lua / part1.lua / medal1beach.lua …）。从那些用法能确定两件事：
--   * 海平面 = 0（`if getHeight({v.x, v.y}) > 0.2 then` 判陆地）
--   * 单位是米（相邻比较用 `- 2`）
-- 所以**一次采样同时支撑等高线与水深两个开关**：等高线取 height 的正值，
-- 水深取 -height（负值即水下）。
--
-- 为什么不用 TERRAIN_TILE_HEIGHTMAP 组件：那是每个 tile 一份的顶点大数组，3136 个
-- tile 挨个读会撞上"百万级数据"的红线（见 world_probe.lua 顶部那条警告）。
-- getHeight 是引擎内部的点查询，一次只算一个点，没有这个风险。
--
-- 网格范围从 TERRAIN_TILE 组件的 position 推：3136 = 56 x 56，正好是地形 tile 网格，
-- 比从铁路网范围外扩、或者猜地图尺寸都可靠。（该组件的 position 在 world_probe v4
-- 里已确认可读；不能读的是 heightmap 的顶点数组，两者是不同的组件。）
--
-- ⚠ 分帧：一次要采 3136 x SUBDIV^2 个点，一帧做完会卡帧。所以这个采集器是**流式**的
-- —— 每个 update 采 BATCH 个点，全部采完才写出。registry 侧为此支持 streaming 层。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

-- 每个 terrain tile 再细分几份。1 = 只用 tile 中心（约 224 m 网格，等高线会发方格感）；
-- 2 = 每方向插一倍（约 112 m 网格，够画等高线）。
local SUBDIV = 2
-- 每帧最多采样多少个点。getHeight 本身是 C++ 点查询很便宜，但 Lua 循环有成本；
-- 宁可多花几帧也不要掉帧。
local BATCH = 400
-- 高度量化：整数 = round(height * SCALE)，前端除回去。0.1 m 精度足够画等高线，
-- 又能把 JSON 里的浮点数变成短整数。
local SCALE = 10
-- 缺失哨兵。JSON 数组不能有洞（json.encode 会跳过 nil 把数组截断），所以用哨兵值。
-- -32768 / SCALE = -3276.8 m，真实地形到不了。
local MISSING = -32768
-- 重采周期（update 数）。地形是静态的，只有玩家动地形才会变，所以拍得很稀。
local RESAMPLE_EVERY = 24000
-- 启动前先等世界加载完（地形网格要等存档读完才完整）。
local START_DELAY = 300

local job = nil
local diagnostics = nil

-- ---------------------------------------------------------------- 基础读取

local function get_height_function()
    local ok, fn = pcall(function() return game.interface.getHeight end)
    if ok and type(fn) == "function" then return fn end
    return nil
end

-- 取某点的地形高度（米）。参数形式按游戏源码里的用法逐个试：
--   getHeight({v.x, v.y}) / getHeight({e.position[1], e.position[2]})
-- 返回 nil 表示这一点取不到。
local function sample_height(fn, x, y)
    local ok, value = pcall(fn, { x, y })
    if ok and type(value) == "number" then return value end
    ok, value = pcall(fn, { x = x, y = y })
    if ok and type(value) == "number" then return value end
    ok, value = pcall(fn, { x, y, 0 })
    if ok and type(value) == "number" then return value end
    return nil
end

local function read_tile_position(entity)
    local tile = component_access.get(entity, "TERRAIN_TILE")
    if tile == nil then return nil end
    local position = common.field(tile, "position")
    local x, y = common.field(position, "x"), common.field(position, "y")
    if type(x) ~= "number" or type(y) ~= "number" then
        -- 少数实现把 position 放成 {x,y,z} 数组
        x, y = common.field(position, 1), common.field(position, 2)
    end
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return x, y
end

-- 把有序数组按倍数细分（相邻两点之间线性插值）。
local function resample(values, subdiv)
    if subdiv <= 1 or #values < 2 then return values end
    local out = {}
    for i = 1, #values - 1 do
        out[#out + 1] = values[i]
        local step = (values[i + 1] - values[i]) / subdiv
        for k = 1, subdiv - 1 do
            out[#out + 1] = values[i] + step * k
        end
    end
    out[#out + 1] = values[#values]
    return out
end

local function table_min_max(values)
    local minimum, maximum = nil, nil
    for i = 1, #values do
        local value = values[i]
        if minimum == nil or value < minimum then minimum = value end
        if maximum == nil or value > maximum then maximum = value end
    end
    return minimum, maximum
end

-- 水体采样：WATER_MESH 的 pos 里应当带水面高度。只读前几个当诊断 ——
-- 海平面是 0 的话，height < 0 就够判水；若水面普遍不为 0，下一版再按 mesh 高度算水深。
local function probe_water_surface()
    local samples = {}
    local seen = 0
    pcall(function()
        common.safe_for_each_entity("WATER_MESH", function(entity)
            if seen >= 3 then return end
            local mesh = component_access.get(entity, "WATER_MESH")
            if mesh == nil then return end
            local position = common.field(mesh, "pos") or common.field(mesh, "position")
            if position == nil then return end
            local x = common.field(position, "x") or common.field(position, 1)
            local y = common.field(position, "y") or common.field(position, 2)
            local z = common.field(position, "z") or common.field(position, 3)
            seen = seen + 1
            samples[#samples + 1] = { x = x, y = y, z = z }
        end, {})
    end)
    return samples
end

-- ---------------------------------------------------------------- 建网格

local function start_job(update_count)
    local xs, ys = {}, {}
    local seen_x, seen_y = {}, {}
    local tiles = 0
    local unreadable = 0

    local ok, reason = common.safe_for_each_entity("TERRAIN_TILE", function(entity)
        local x, y = read_tile_position(entity)
        if x == nil then
            unreadable = unreadable + 1
            return
        end
        tiles = tiles + 1
        if not seen_x[x] then seen_x[x] = true; xs[#xs + 1] = x end
        if not seen_y[y] then seen_y[y] = true; ys[#ys + 1] = y end
    end, {})

    if not ok then return nil, "TERRAIN_TILE walk failed: " .. tostring(reason) end
    if #xs < 2 or #ys < 2 then
        return nil, "terrain grid too small: " .. #xs .. " x " .. #ys .. " (unreadable tiles: " .. unreadable .. ")"
    end

    table.sort(xs)
    table.sort(ys)
    local tile_cols, tile_rows = #xs, #ys
    local min_x, max_x = xs[1], xs[#xs]
    local min_y, max_y = ys[1], ys[#ys]
    local tile_step_x = (max_x - min_x) / math.max(tile_cols - 1, 1)
    local tile_step_y = (max_y - min_y) / math.max(tile_rows - 1, 1)

    local grid_xs = resample(xs, SUBDIV)
    local grid_ys = resample(ys, SUBDIV)
    local cols, rows = #grid_xs, #grid_ys

    local height_fn = get_height_function()

    -- 自检：拿网格中心点试一次，把结果和耗时记进产物。
    -- 改一次 Lua 就要重启一次游戏，所以产物必须自带诊断，不能靠再探一轮。
    local probe = {
        interface_available = height_fn ~= nil,
        tile_count = tiles,
        unreadable_tiles = unreadable,
        tile_cols = tile_cols,
        tile_rows = tile_rows,
        tile_step_x = tile_step_x,
        tile_step_y = tile_step_y,
        tile_span_x = max_x - min_x,
        tile_span_y = max_y - min_y,
        subdiv = SUBDIV,
        cols = cols,
        rows = rows,
        grid_step_x = (max_x - min_x) / math.max(cols - 1, 1),
        grid_step_y = (max_y - min_y) / math.max(rows - 1, 1),
        water_mesh_samples = probe_water_surface(),
    }

    if height_fn ~= nil then
        local center_x = grid_xs[math.floor(cols / 2) + 1]
        local center_y = grid_ys[math.floor(rows / 2) + 1]
        local clock = common.clock()
        local value = sample_height(height_fn, center_x, center_y)
        probe.sample_ms = (common.clock() - clock) * 1000
        probe.sample_point = { x = center_x, y = center_y }
        probe.sample_value = value
        -- 再连采 64 个点估单点成本（os.clock 精度低，单次测不出来）
        if value ~= nil then
            local clock2 = common.clock()
            local taken = 0
            for i = 1, 64 do
                if sample_height(height_fn, center_x + i, center_y) ~= nil then taken = taken + 1 end
            end
            local elapsed = common.clock() - clock2
            probe.per_call_ms = elapsed * 1000 / 64
            probe.calls_ok = taken
        end
    end

    diagnostics = probe

    job = {
        xs = grid_xs,
        ys = grid_ys,
        cols = cols,
        rows = rows,
        heights = {},
        cursor = 1,
        missing = 0,
        height_fn = height_fn,
        started_at_update = update_count,
        tile_count = tiles,
    }
    return job
end

-- ---------------------------------------------------------------- 出结果

local function finish(j, update_count)
    local total = j.cols * j.rows
    local heights = {}
    for index = 1, total do
        local value = j.heights[index]
        heights[index] = value ~= nil and value or MISSING
    end

    local min_h, max_h = nil, nil
    local water_points = 0
    for index = 1, total do
        local value = heights[index]
        if value ~= MISSING then
            if min_h == nil or value < min_h then min_h = value end
            if max_h == nil or value > max_h then max_h = value end
            if value < 0 then water_points = water_points + 1 end
        end
    end

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "GRID",
        grid = {
            origin = { x = j.xs[1], y = j.ys[1] },
            step_x = (j.xs[j.cols] - j.xs[1]) / math.max(j.cols - 1, 1),
            step_y = (j.ys[j.rows] - j.ys[1]) / math.max(j.rows - 1, 1),
            cols = j.cols,
            rows = j.rows,
            scale = SCALE,
            missing = MISSING,
            sea_level = 0,
        },
        heights = heights,
        counts = {
            total = total,
            cols = j.cols,
            rows = j.rows,
            terrain_tiles = j.tile_count,
            missing = j.missing,
            water_points = water_points,
            min_height = min_h and (min_h / SCALE) or nil,
            max_height = max_h and (max_h / SCALE) or nil,
            duration_updates = update_count - (j.started_at_update or update_count),
        },
        diagnostics = diagnostics,
        errors = {},
    }
end

-- ---------------------------------------------------------------- 对外接口（流式）

-- registry 每个 update 调一次。
--   should_start : 调度相位是否已到（能不能起新一轮）
-- 返回 nil 表示"还在采，别写文件"；返回 table 表示"这一轮采完了，这是产物"。
function M.advance(should_start, update_count)
    if job == nil then
        if not should_start then return nil end
        local started, error_message = start_job(update_count)
        if started == nil then
            return {
                status = "ERROR",
                source_status = "ENGINE_OBSERVED",
                geometry_kind = "GRID",
                error = error_message,
                errors = { { note = error_message } },
            }
        end
        return nil
    end

    if job.height_fn == nil then
        local failed = {
            status = "ERROR",
            source_status = "ENGINE_OBSERVED",
            geometry_kind = "GRID",
            error = "game.interface.getHeight unavailable",
            diagnostics = diagnostics,
            errors = { { note = "game.interface.getHeight is not a function" } },
        }
        job = nil
        return failed
    end

    local total = job.cols * job.rows
    local produced = 0
    while job.cursor <= total and produced < BATCH do
        local index = job.cursor - 1
        local col = index % job.cols
        local row = math.floor(index / job.cols)
        local value = sample_height(job.height_fn, job.xs[col + 1], job.ys[row + 1])
        if value == nil then
            job.missing = job.missing + 1
        else
            job.heights[job.cursor] = math.floor(value * SCALE + 0.5)
        end
        job.cursor = job.cursor + 1
        produced = produced + 1
    end

    if job.cursor <= total then return nil end

    local payload = finish(job, update_count)
    job = nil
    return payload
end

-- 当前是否正在采（供诊断/状态用）
function M.busy()
    return job ~= nil
end

return M
