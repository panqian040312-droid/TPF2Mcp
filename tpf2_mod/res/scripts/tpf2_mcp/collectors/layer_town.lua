-- 城镇图层 / 需求探针（只读）
--
-- 用户 2026-09-30 诉求：游戏里城区上空有个牌子，写着【城市名 + 需要的货物】，
-- 那排小图标就是货种图标。对应到数据：
--     城市名   → `TOWN.name`
--     牌子位置 → `TOWN.position`
--     需要的货 → 官方 api.type 的 `Town.cargoNeeds`
--                （`{{货种id,...},{货种id,...},{货种id,...}}` = 住宅 / 商业 / 工业 三个城区）
--   货种 id → 名称/图标的字典在 `api.res.cargoTypeRep`（collectors/cargo.lua 已经在采）。
--
-- 🔴 为什么还要专门采一次 —— 世界探针里那几个字段**读不出内容**：
--   `world-probe.json` 的 component_walk.TOWN 实测字段是
--     id / name / position / lu2cargoInfo / counts / townDestCounts /
--     useLinesCounts / useLinesPercentage / type
--   —— **没有 `cargoNeeds` 这个名字**，只有 `lu2cargoInfo`（lu = land use → cargo info，
--   语义上应当就是它）。而且 `lu2cargoInfo` / `counts` / `townDestCounts` / `useLinesCounts`
--   在世界探针里**全部报 `length: 0`**。
--
--   ⚠️ **length 0 不等于空**！`common.array_count` 走的是 `#value`，
--   而 `#` 对 **map（非连续整数 key）** 返回 0，对标准 Lua table 也一样。
--   世界探针用的正是 `array_count`，所以它看不到内容 —— 与 `first_id` 那个坑同源。
--
--   ⇒ 所以本采集器**必须用 `pairs` 遍历**，并且把"每个字段到底是什么形状"
--     （array / map / 空 / 不可遍历）如实报出来。**这才是它存在的首要目的**：
--     先把形状钉死，再谈接前端。
--
-- 输出：bridge/layer-town.json（geometry_kind = "TOWN"，整层不切块）

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

local TOWN_LIMIT = 500      -- 本存档城镇数量级：几百
local ENTRY_LIMIT = 48      -- 单个字段最多展开多少条（防某个大 map 撑爆 payload）
local DEPTH_LIMIT = 3       -- 递归深度
local SAMPLE_TOWNS = 6      -- 完整样例城镇数

local SILENT = setmetatable({}, { __index = function() return true end })

-- 逐字段做形状画像的候选。`cargoNeeds` 是官方文档里的名字，**已实测确认为真需求字段**
-- （27/27 城镇都有，array 形状）；其余四个是 ECS 世界探针里看到的名字，实测均为 length 0，
-- 不是需求数据。保留它们是为了让 shape_report 每次都如实报出"哪些字段还在、哪些已消失"。
local DEMAND_KEYS = { "lu2cargoInfo", "cargoNeeds", "counts", "townDestCounts", "useLinesCounts" }

-- ── 递归描述一个值。探针专用：宁可啰嗦，也要把"它到底是什么"看清楚。──────────────
-- array 走 sequence_values（依赖 #），map 走 pairs —— **map 这条路是本文件的重点**。
local function describe(value, depth)
    if value == nil then return { type = "nil" } end
    local kind = type(value)
    if kind == "number" or kind == "string" or kind == "boolean" then
        return { type = kind, value = value }
    end
    if kind ~= "table" and kind ~= "userdata" then
        -- 函数 / 线程 / 其它：不展开，只报类型
        return { type = kind }
    end

    local out = { type = kind }

    -- ① 先试 array（sequence_values 内部用 #，失败会返回空表）
    local count = common.array_count(value)
    out.length = count
    local seq = common.sequence_values(value)
    if #seq > 0 then
        out.mode = "array"
        out.items = {}
        for i = 1, math.min(#seq, math.min(ENTRY_LIMIT, 8)) do
            out.items[#out.items + 1] = describe(seq[i], depth + 1)
        end
        return out
    end

    -- ② 再试 map —— length 为 0 但 pairs 可能有内容，这正是关键分支
    if depth >= DEPTH_LIMIT then
        out.mode = "too_deep"
        return out
    end
    local entries = {}
    local seen = 0
    local ok, err = pcall(function()
        for k, v in pairs(value) do
            seen = seen + 1
            if seen <= ENTRY_LIMIT then
                entries[#entries + 1] = { key = describe(k, depth + 1), value = describe(v, depth + 1) }
            end
        end
    end)
    out.key_count = seen
    if ok then
        out.mode = seen > 0 and "map" or "empty"
        if #entries > 0 then out.entries = entries end
    else
        out.mode = "uniterable"
        out.error = tostring(err)
    end
    return out
end

-- 读一个 vec3（position）。两种形状都要认：
--   ① map  { x = …, y = …, z = … }
--   ② 数组 [ x, y, z ]   ← 实测 TOWN.position 就是这个形状
--      （world-probe：`"position": {"type":"table","length":3}` —— length 3 ⇒ 数组，不是 map）
-- 第一版只认 ①，这是 27/27 个城镇 with_position 全为 0 的直接原因。
local function point_at(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then
        local a, b, c = common.field(value, 1), common.field(value, 2), common.field(value, 3)
        if type(a) == "number" and type(b) == "number" then
            x, y, z = a, b, c
        else
            a, b, c = common.field(value, 0), common.field(value, 1), common.field(value, 2)
            if type(a) == "number" and type(b) == "number" then x, y, z = a, b, c end
        end
    end
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

function M.collect()
    local errors = {}
    local started = common.clock()

    local towns = {}
    local scanned = 0
    local with_position, with_name = 0, 0
    local position_probe = nil     -- 第一条 position 的取值诊断（见下面 pick_parsed 那段的注释）
    local position_via = {}        -- 坐标是从哪条取值路拿到的：component / interface

    -- 形状统计：字段名 → 各种 mode 出现次数
    local shapes = {}
    for _, key in ipairs(DEMAND_KEYS) do
        shapes[key] = { present = 0, array = 0, map = 0, empty = 0, uniterable = 0, too_deep = 0, sample = nil }
    end

    common.safe_for_each_entity("TOWN", function(entity)
        scanned = scanned + 1
        if #towns >= TOWN_LIMIT then return end

        local component = common.safe_get_component(entity, "TOWN", SILENT)
        if component == nil then return end

        -- ── 两条取值路，都必须走 ─────────────────────────────────────────────
        -- TOWN 组件的 `__index` 是**函数式 getter**（world-probe: index_is_function = true）：
        --   ① `component[key]`   —— 只认引擎注册过 getter 的字段（如 cargoNeeds）
        --   ② `pairs(component)` —— 遍历全部成员（如 name / position / useLinesPercentage，
        --                           这几个恰恰**没有** getter，① 取不到）
        -- 实测（2026-09-30 19:58 首采）：第一版只走 ①，结果这三个字段 27/27 全空，
        -- 而且 shape_report 还误报 lu2cargoInfo「不存在」—— 其实它在 ② 里，只是 length 0。
        -- 所以：① 优先、② 兜底。
        local flat = nil
        local function flat_table()
            if flat == nil then
                flat = {}
                pcall(function()
                    for k, v in pairs(component) do flat[k] = v end
                end)
            end
            return flat
        end
        local function pick(key)
            local direct = common.field(component, key)
            if direct ~= nil then return direct end
            return flat_table()[key]
        end
        -- 取值 + **当场解析**：getter 有可能返回一个"非 nil 但解析不出内容"的空壳
        -- （position 就是这种），只看"非 nil"会误判成已经拿到，从而不再去试 pairs。
        -- 2026-09-30 实测：`with_name = 27` 但 `with_position = 0`，就是卡在这一步。
        local function pick_parsed(key, parse)
            local from_direct = parse(common.field(component, key))
            if from_direct ~= nil then return from_direct end
            return parse(flat_table()[key])
        end

        local name = common.name_from_component(common.safe_get_component(entity, "NAME", SILENT))
        if type(name) ~= "string" then
            local direct = pick("name")
            if type(direct) == "string" then name = direct end
        end
        local entry = {
            id = common.entity_id(entity),
            name = name,
        }
        if type(entry.name) == "string" then with_name = with_name + 1 end

        local raw_position = common.field(component, "position")
        local position = pick_parsed("position", point_at)
        local position_source = position ~= nil and "component" or nil
        if position == nil then
            -- 第三条路：`game.interface.getEntity(id)` 的**聚合表**。
            -- 为什么加：2026-09-30 实测 `component["position"]`（getter）与 `pairs(component)`
            -- **两条路都拿不到坐标**（position_probe 里 via_getter_type=nil、parsed_ok=false），
            -- 而 layer_road 早就证过"有些字段只存在于 interface 聚合表"（streetType 就是）。
            -- 三类取值路各管一批字段，少走一条就漏数据 —— 这是本项目最反复的一类坑。
            local ok_view, view = pcall(function()
                return game.interface.getEntity(common.entity_id(entity))
            end)
            if ok_view and view ~= nil then
                position = point_at(common.field(view, "position"))
                if position ~= nil then position_source = "interface" end
            end
        end
        if position_probe == nil then
            -- 诊断：万一还取不到，靠这几项就能判断卡在哪条取值路上，不用再猜。
            position_probe = {
                via_getter_type = type(raw_position),
                getter_text = tostring(raw_position):sub(1, 60),
                parsed_ok = position ~= nil,
                source = position_source or "none",
            }
        end
        if position ~= nil then
            with_position = with_position + 1
            position_via[position_source] = (position_via[position_source] or 0) + 1
            entry.x, entry.y, entry.z = position.x, position.y, position.z
        end

        entry.use_lines_percentage = pick("useLinesPercentage")

        -- ★ 逐字段描述形状。前 SAMPLE_TOWNS 个城镇保留完整展开，其余只记形状。
        local detail = {}
        for _, key in ipairs(DEMAND_KEYS) do
            local raw = pick(key)
            local stat = shapes[key]
            if raw == nil then
                -- 字段不存在：不记 present
            else
                stat.present = stat.present + 1
                local d = describe(raw, 0)
                local mode = d.mode or "scalar"
                if stat[mode] ~= nil then stat[mode] = stat[mode] + 1 end
                if stat.sample == nil and (d.mode == "map" or d.mode == "array") then
                    stat.sample = d
                end
                if #towns < SAMPLE_TOWNS then detail[key] = d end
                -- 注意：完整展开只进 detail，**不**再往 entry 上挂一份，否则每个城镇都带一大坨
            end
        end
        if next(detail) ~= nil then entry.detail = detail end

        -- ── 需求：真字段是 `cargoNeeds`，不是 lu2cargoInfo ────────────────────
        -- 实测（2026-09-30 19:58 首采）：27/27 个城镇都有 cargoNeeds（array 形状）；
        -- 而 lu2cargoInfo / counts / townDestCounts / useLinesCounts 在 ① 路全部取不到，
        -- 走 ② 路（pairs）才看得见 —— 且 length 全为 0，它们**不是**需求数据。
        -- cargoNeeds 形状 = **3 个区**（住宅 / 商业 / 工业），每区是一串货种 id：
        --     [ (空) , [16, 14, 15] , [11, 12, 13] ]   ← 武汉；住宅区此刻无需求
        -- 货种 id → 名称/图标：由前端查 api.res.cargoTypeRep（collectors/cargo.lua 已在采）。
        local needs = {}
        local demand_total = 0
        local raw_needs = pick("cargoNeeds")
        if raw_needs ~= nil then
            for _, zone in ipairs(common.sequence_values(raw_needs)) do
                local ids = {}
                for _, id_value in ipairs(common.sequence_values(zone)) do
                    local n = tonumber(tostring(id_value))
                    if n ~= nil and n > 0 then ids[#ids + 1] = n end
                end
                needs[#needs + 1] = ids
                demand_total = demand_total + #ids
            end
        end
        if #needs > 0 then entry.needs = needs end
        entry.demand_count = demand_total

        towns[#towns + 1] = entry
    end, errors)

    table.sort(towns, function(a, b) return tostring(a.id) < tostring(b.id) end)

    local with_demand = 0
    for _, t in ipairs(towns) do
        if (t.demand_count or 0) > 0 then with_demand = with_demand + 1 end
    end

    local out_shapes = {}
    for key, stat in pairs(shapes) do
        out_shapes[key] = {
            present = stat.present,
            array = stat.array,
            map = stat.map,
            empty = stat.empty,
            uniterable = stat.uniterable,
            too_deep = stat.too_deep,
            sample = stat.sample,
        }
    end

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "TOWN",
        -- 这份产物一半是数据、一半是探针报告。shape_report 是**首要交付**：
        -- 它回答"lu2cargoInfo 到底是 map 还是 array、有没有内容"这个问题。
        note = "demand fields are read with pairs (not #) on purpose; see shape_report",
        counts = {
            total = #towns,
            towns = #towns,
            scanned = scanned,
            with_name = with_name,
            with_position = with_position,
            with_demand = with_demand,
            position_probe = position_probe,
            position_via = position_via,
        },
        shape_report = out_shapes,
        towns = towns,
        duration_ms = (common.clock() - started) * 1000,
        errors = errors,
    }
end

return M
