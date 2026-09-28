-- 地形图层采集器（等高线 + 水深的数据源，只读）
--
-- 数据源：`game.interface.getHeight({x, y})` —— 官方接口，游戏自带的战役 mod 用了
-- 20 多处（medal2worms.lua / part1.lua / medal1beach.lua …）。从那些用法能确定两件事：
--   * 海平面 = 0（`if getHeight({v.x, v.y}) > 0.2 then` 判陆地）
--   * 单位是米（相邻比较用 `- 2`）
-- 所以**一次采样同时支撑等高线与水深两个开关**：等高线取 height 的正值，
-- 水深取 -height（负值即水下）。
--
-- 🔴 采样网格用**世界坐标**，范围由路网节点推出 —— 不用 TERRAIN_TILE 的 position。
--
-- 2026-09-29 踩过的坑：`TERRAIN_TILE` 的 position 是**网格索引**（相邻 tile 的 x 差恰好是 1），
-- 不是世界坐标。第一版拿它当世界坐标调 getHeight，采样点全挤在地图中心 56 m 见方的一块里，
-- 实测高度范围只有 12.1 ~ 15.3 m —— 整张地形图是废的。
--
-- 现在改成：遍历 BASE_NODE（道路与铁路节点）求包围盒并集，外扩一点作为采样范围。
-- 坐标一定是世界坐标，覆盖范围是"玩家能看到的一切"（路铺到哪，地形就采到哪）。
--
-- ⚠ 分帧：一帧采不完，所以这个采集器是**流式**的 —— 每个 update 采 BATCH 个点，
-- 全部采完才写出。registry 侧为此支持 streaming 层。
--
-- 别读 `TERRAIN_TILE_HEIGHTMAP`：那是每个 tile 一份的顶点大数组，读 3136 份会撞上
-- "百万级数据"的红线（见 world_probe.lua 顶部警告）。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

-- 目标采样步长（米）。170 m 与地形自身的 tile 尺度同量级，画等高线够用。
local TARGET_STEP = 170
-- 网格点数的下限 / 上限。上限决定最坏情况的分帧帧数（200×200 = 4 万点 / 每帧 400 = 100 帧）。
local MIN_CELLS = 48
local MAX_CELLS = 200
-- 采样范围在活动范围外再扩这么多（相对比例），免得边缘等高线贴着边界断开。
local EDGE_MARGIN = 0.08
-- 每个 update 最多采样多少个点。getHeight 本身是 C++ 点查询很便宜（实测 0.016 ms/次），
-- 但 Lua 循环有成本，宁可多花几帧也不要掉帧。
local BATCH = 400
-- 高度量化：整数 = round(height * SCALE)，前端除回去。
local SCALE = 10
-- 缺失哨兵。JSON 数组不能有洞（json.encode 会跳过 nil 把数组截断），所以用哨兵值。
local MISSING = -32768
-- 重采周期（update 数）。地形是静态的，只有玩家动地形才会变，所以拍得很稀。
local RESAMPLE_EVERY = 24000
-- 启动前先等世界加载完（路网节点要等存档读完才完整）。
local START_DELAY = 300

local job = nil
local diagnostics = nil

-- ---------------------------------------------------------------- 基础读取

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

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

-- 采样范围：所有 BASE_NODE 的包围盒并集。
-- BASE_NODE 覆盖道路与铁路的全部节点（本存档 9793 个），所以它的范围就是
-- "玩家铺出去的世界" —— 城镇、产业、路网都落在这个范围里。
local function activity_bounds()
    local min_x, max_x, min_y, max_y = nil, nil, nil, nil
    local seen, unreadable = 0, 0
    local ok, reason = common.safe_for_each_entity("BASE_NODE", function(entity)
        local node = component_access.get(entity, "BASE_NODE")
        local position = vec(common.field(node, "position")) or vec(common.field(node, "pos"))
        if position == nil then unreadable = unreadable + 1 return end
        seen = seen + 1
        min_x = min_x == nil and position.x or math.min(min_x, position.x)
        max_x = max_x == nil and position.x or math.max(max_x, position.x)
        min_y = min_y == nil and position.y or math.min(min_y, position.y)
        max_y = max_y == nil and position.y or math.max(max_y, position.y)
    end, {})
    if not ok then return nil, "BASE_NODE walk failed: " .. tostring(reason) end
    if min_x == nil then return nil, "no readable BASE_NODE position" end
    return { min_x = min_x, max_x = max_x, min_y = min_y, max_y = max_y,
             nodes = seen, unreadable = unreadable }
end

-- ---------------------------------------------------------------- 建网格

local function start_job(update_count)
    local bounds, bounds_error = activity_bounds()
    if bounds == nil then return nil, bounds_error end

    local span_x = bounds.max_x - bounds.min_x
    local span_y = bounds.max_y - bounds.min_y
    if span_x <= 0 or span_y <= 0 then
        return nil, "degenerate activity extent: " .. span_x .. " x " .. span_y
    end

    local min_x = bounds.min_x - span_x * EDGE_MARGIN
    local max_x = bounds.max_x + span_x * EDGE_MARGIN
    local min_y = bounds.min_y - span_y * EDGE_MARGIN
    local max_y = bounds.max_y + span_y * EDGE_MARGIN

    local cols = math.floor((max_x - min_x) / TARGET_STEP) + 1
    local rows = math.floor((max_y - min_y) / TARGET_STEP) + 1
    cols = math.max(MIN_CELLS, math.min(cols, MAX_CELLS))
    rows = math.max(MIN_CELLS, math.min(rows, MAX_CELLS))

    local step_x = (max_x - min_x) / (cols - 1)
    local step_y = (max_y - min_y) / (rows - 1)

    local height_fn = get_height_function()

    -- 自检：拿网格中心点试一次，把结果和单次耗时记进产物。
    -- 改一次 Lua 就要重启一次游戏，所以产物必须自带诊断，不能靠再探一轮。
    local probe = {
        interface_available = height_fn ~= nil,
        extent_source = "BASE_NODE bbox",
        extent_nodes = bounds.nodes,
        extent_unreadable = bounds.unreadable,
        extent_x = { min_x, max_x },
        extent_y = { min_y, max_y },
        cols = cols,
        rows = rows,
        step_x = step_x,
        step_y = step_y,
        total_samples = cols * rows,
        frames_expected = math.ceil(cols * rows / BATCH),
        water_mesh_samples = probe_water_surface(),
    }

    if height_fn ~= nil then
        local center_x = (min_x + max_x) / 2
        local center_y = (min_y + max_y) / 2
        local clock = common.clock()
        local value = sample_height(height_fn, center_x, center_y)
        probe.sample_ms = (common.clock() - clock) * 1000
        probe.sample_point = { x = center_x, y = center_y }
        probe.sample_value = value
        -- 连采 64 个点估单点成本（os.clock 精度低，单次测不出来）
        if value ~= nil then
            local clock2 = common.clock()
            local taken = 0
            for i = 1, 64 do
                if sample_height(height_fn, center_x + i * step_x, center_y) ~= nil then taken = taken + 1 end
            end
            probe.per_call_ms = (common.clock() - clock2) * 1000 / 64
            probe.calls_ok = taken
        end
        -- 边界探测：沿四个方向往外走到失效，用来核对采样范围是否合理
        -- （如果四个方向都能走很远，说明 getHeight 在地图外也返回值，探测结果不能用）
        local function probe_axis(axis, sign)
            local best, distance = 0, TARGET_STEP * 4
            for _ = 1, 60 do
                local sampled = (axis == "x") and sample_height(height_fn, distance * sign, center_y)
                    or sample_height(height_fn, center_x, distance * sign)
                if sampled == nil then break end
                best = distance
                distance = distance * 1.12
            end
            return best
        end
        probe.extent_probe = {
            x_positive = probe_axis("x", 1),
            x_negative = probe_axis("x", -1),
            y_positive = probe_axis("y", 1),
            y_negative = probe_axis("y", -1),
        }
    end

    diagnostics = probe

    job = {
        xs = {},
        ys = {},
        cols = cols,
        rows = rows,
        heights = {},
        cursor = 1,
        missing = 0,
        height_fn = height_fn,
        started_at_update = update_count,
    }
    for i = 1, cols do job.xs[i] = min_x + (i - 1) * step_x end
    for j = 1, rows do job.ys[j] = min_y + (j - 1) * step_y end
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
