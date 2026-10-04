-- Read-only world probe (v4).
--
-- v3 战果：72 个可解析组件 + 38 个组件的精确实体数 + 12 张 API 注册表。
-- v3 短板：组件「有哪些字段」没答完 —— 通用字段名单 9373 条探测里只有 94 条非 nil（1.0%），
--         277 KB 输出里 99% 是 {"type":"nil"}。
--
-- v4 的四件事：
--   ① 换一条路拿字段名。`game.interface.getEntity(id)` 返回的是**可 pairs() 枚举的聚合表**，
--      字段名 = 小驼峰组件名（e.stationGroup / e.simBuildings / e.vehicles[w].fileName）。
--      这是从游戏自带的官方 mod（mods/urbangames_campaign_mission_*）源码里翻出来的真实用法，
--      那批 mod 里 getEntity 出现 518 次。→ 字段名不必再手写名单，直接枚举。
--   ② 补 v3 留下的 6 个缺口：api.engine.transport / api.engine.terrain / api.util /
--      api.engine.system.<X> 方法表（31 个）/ api.res.*Rep 方法表（15 张）/ 组件字段名。
--   ③ 补遍历：TRAIN / RAIL_VEHICLE / ROAD_VEHICLE / SHIP / AIRCRAFT 五个车种 + TERRAIN_TILE。
--   ④ 修 v3 的浪费：字段探测只保留非 nil；补回 walk_budget。
--
-- 只读：不发送任何写命令，不改游戏状态。
-- 安全边界：PARCEL / ASSET_GROUP / BOUNDING_VOLUME 这类已近上限的巨型组件不重复遍历；
--          SIM_PERSON / SIM_CARGO / SIM_ENTITY_MOVING / MODEL_INSTANCE_LIST 一律不遍历
--          （mod 作者当年就因为一次性遍历把游戏搞崩过）。
local common = require "tpf2_mcp/collectors/common"
local M = {}

-- ===== 0. 参数 ============================================================
local SAMPLE_LIMIT = 3             -- 每个组件抓几个实体做明细
local AGG_KEY_LIMIT = 120          -- 聚合实体最多记录多少个字段
local MT_KEY_LIMIT = 150           -- metatable.__index 最多记录多少个键
local WALK_BUDGET = 420000         -- 累计实体遍历预算（v3 实测 378,942，留约 10% 余量）

-- ===== 1. 名字推导 ========================================================
-- PascalCase -> UPPER_SNAKE（v3 验证 100% 成立，无例外）
local function upper_snake(name)
    local s = string.gsub(name, "(%l)(%u)", "%1_%2")
    s = string.gsub(s, "(%u)(%u%l)", "%1_%2")
    return string.upper(s)
end

-- ===== 2. 候选组件名 ======================================================
-- 2a. 来自 api.type 成员名的推导结果（运行时填）
-- 2b. 策展名单：不在 api.type 里但已知/怀疑是组件的名字
local CURATED = {
    -- 已在用（回归对照）
    "LINE", "STATION", "STATION_GROUP", "STATION_TERMINAL", "TRANSPORT_VEHICLE",
    "VEHICLE_DEPOT", "SIGNAL", "SIGNAL_LIST", "BASE_EDGE", "BASE_EDGE_TRACK",
    "BASE_NODE", "BASE_NODE_TRAFFIC_LIGHT", "NAME", "BOUNDING_VOLUME", "CONSTRUCTION",
    "SIM_BUILDING", "TOWN", "TOWN_BUILDING", "TOWN_BUILDING_PARAMS", "BUILDING_TYPE",
    "MOVE_PATH", "PATH", "PATH_POS", "GAME_TIME", "GAME_SPEED", "TICK_EPOCH",
    "PLAYER", "ACCOUNT", "INFO", "MOVE_PATH_AIRCRAFT", "TRANSPORT_HISTORY",
    -- 地形 / 水体 / 地图
    "MAP", "TERRAIN", "TERRAIN_TILE", "TERRAIN_TILE_BRUSH", "TERRAIN_TILE_HEIGHTMAP",
    "REPLACE_TERRAIN", "GROUND_TEXTURE", "AUTO_GROUND_TEX", "WATER_MESH",
    -- 建筑 / 产业
    "CONSTRUCTION_DESC", "STATIC_CONSTRUCTION_TEMPLATE", "DYNAMIC_CONSTRUCTION_TEMPLATE",
    "MODULE_DESC", "LOT_LIST", "ASSET_GROUP", "ASSET_GROUP_AUTO_REMOVE", "PARCEL",
    "PARCEL_DATA", "MODEL_INSTANCE", "MODEL_INSTANCE_LIST", "THIN_MODEL_INSTANCE",
    -- 道路 / 街道
    "BASE_EDGE_STREET", "STREET_TYPE", "STREET_PROPOSAL", "SIMPLE_STREET_PROPOSAL",
    "LANE_CONFIG", "RAILROAD_CROSSING", "RAILROAD_CROSSING_TYPE", "TRAFFIC_LIGHT_TYPE",
    "BASE_PARALLEL_STRIP",
    -- 通用路网
    "TRANSPORT_NETWORK", "TRANSPORT_NODE", "TRANSPORT_EDGE", "TRANSPORT_NODE_DATA",
    "TRANSPORT_EDGE_DATA", "TP_NET_DATA", "TP_NET_LINK", "TRACK_TYPE",
    "EDGE_GEOMETRY", "EDGE_POS", "EDGE_ID", "NODE_ID", "SIGNAL_ID",
    -- 航空 / 水上 / 桥隧
    "RUNWAY_LIST", "PORT_ID", "BRIDGE", "BRIDGE_TYPE", "TUNNEL_TYPE",
    -- 城镇 / 需求 / 统计
    "TOWN_CONNECTION", "TOWN_INFO", "VALUES_MAP", "METADATA_MAP", "CARGO_TYPE",
    "TRANSPORTATION_STATS", "PERSON_CAPACITY",
    -- 车种（v3 解析成功但没遍历，v4 要遍历）
    "TRAIN", "RAIL_VEHICLE", "ROAD_VEHICLE", "SHIP", "AIRCRAFT",
}

-- 允许做实体遍历的组件（实体规模可控）。
-- 不在这里的 = 只记录「能否解析」，不数实体。
local WALK_LIST = {
    "MAP", "TERRAIN", "TERRAIN_TILE", "TERRAIN_TILE_BRUSH", "TERRAIN_TILE_HEIGHTMAP",
    "WATER_MESH", "GROUND_TEXTURE", "AUTO_GROUND_TEX",
    "CONSTRUCTION", "CONSTRUCTION_DESC", "STATIC_CONSTRUCTION_TEMPLATE",
    "DYNAMIC_CONSTRUCTION_TEMPLATE", "SIM_BUILDING", "TOWN_BUILDING",
    "TOWN_BUILDING_PARAMS", "BUILDING_TYPE", "MODULE_DESC", "LOT_LIST",
    "BASE_EDGE_STREET", "STREET_TYPE", "LANE_CONFIG", "RAILROAD_CROSSING",
    "RAILROAD_CROSSING_TYPE", "BASE_PARALLEL_STRIP",
    "TRANSPORT_NETWORK", "TRANSPORT_NODE", "TRANSPORT_EDGE", "TRANSPORT_NODE_DATA",
    "TRANSPORT_EDGE_DATA", "TP_NET_DATA", "TP_NET_LINK", "TRACK_TYPE", "EDGE_GEOMETRY",
    "RUNWAY_LIST", "PORT_ID", "BRIDGE", "BRIDGE_TYPE", "TUNNEL_TYPE",
    "TOWN", "TOWN_CONNECTION", "TOWN_INFO", "VALUES_MAP", "METADATA_MAP",
    "CARGO_TYPE", "PERSON_CAPACITY",
    "LINE", "STATION", "STATION_GROUP", "STATION_TERMINAL", "TRANSPORT_VEHICLE",
    "VEHICLE_DEPOT", "SIGNAL", "SIGNAL_LIST", "BASE_EDGE", "BASE_EDGE_TRACK",
    "BASE_NODE", "BASE_NODE_TRAFFIC_LIGHT", "NAME", "MOVE_PATH", "PATH", "PATH_POS",
    "PLAYER", "ACCOUNT", "GAME_TIME", "GAME_SPEED", "TICK_EPOCH", "TRANSPORT_HISTORY",
    -- v4 新增：五个车种（车总量 664，代价可控，但能直接分车种）
    "TRAIN", "RAIL_VEHICLE", "ROAD_VEHICLE", "SHIP", "AIRCRAFT",
}

-- ===== 3. 字段试探名单 ====================================================
-- TPF2 的组件实例是 userdata，pairs() 拿不到键 → 只能按名字逐个试读。
-- v4 的名单 = v3 的通用名 + 从游戏自带官方 mod 源码里挖出来的真实字段名
--            （mods/urbangames_campaign_mission_*，getEntity 返回值上的字段）。
local PROBE_KEYS = {
    -- v3 通用名
    "name", "id", "value", "type", "state", "owner", "group", "parent",
    "entity", "position", "pos", "transf", "transform", "rotation", "direction", "dir",
    "x", "y", "z", "size", "length", "width", "height", "volume", "area", "radius",
    "bbox", "min", "max", "level", "floor", "amount", "count", "capacity", "capacities",
    "config", "info", "desc", "metadata", "params", "items", "entries", "list", "models",
    "parts", "compartments", "cargo", "cargoLoad", "cargoWaiting", "itemsLoaded",
    "itemsUnloaded", "moreCapacity", "tasks", "slots", "platforms", "tracks", "links",
    "nodes", "edges", "town", "line", "station", "vehicle", "ground", "water", "mesh",
    "texture", "heightmap", "cargoTypes", "needs", "supply", "demand", "weight",
    "price", "cost", "maintenance", "lifespan", "runningCosts", "modelId", "model",
    "kind", "category", "stateTime", "arrivalTime", "departureTime", "waitingTime",
    "simulation", "sequence", "__doc__", "__name", "__index",
    -- v4 新增：从官方 mod 源码挖到的真实字段名
    "stops", "stopIndex", "vehicles", "carrier", "carriers", "depots",
    "stations", "stationGroup", "simBuildings", "stockList", "allCapacities",
    "itemsConsumed", "itemsProduced", "itemsTransported", "itemsWaiting",
    "fileName", "stageName", "delay", "track", "node0pos", "node1pos",
    "frequency", "revenue", "roadmoney", "speed", "curSpeed", "comp",
    "rangeGroups", "streetSegment", "parcels", "personCapacity", "typeIndex",
    "nextDepot", "cargoType", "cargoCapacity",
}

-- ===== 4. 工具 ============================================================
-- 枚举一个 table 的成员；pairs 不行就退到 metatable.__index。
local function safe_members(value, max_items)
    local out = { value_type = type(value), count = 0, enumerable = false, names = {} }
    if value == nil then out.value_type = "nil" return out end
    local limit = max_items or 400

    local ok = pcall(function()
        for key, member in pairs(value) do
            out.count = out.count + 1
            if #out.names < limit then
                out.names[#out.names + 1] = { name = tostring(key), type = type(member) }
            end
        end
    end)
    out.enumerable = ok and out.count > 0

    -- pairs() 失败或空 → 试 metatable.__index（Sol2 绑定的对象常把成员挂在这里）
    if out.count == 0 then
        local mt_ok, mt = pcall(getmetatable, value)
        if mt_ok and type(mt) == "table" then
            local idx = common.field(mt, "__index")
            if type(idx) == "table" then
                pcall(function()
                    for key, member in pairs(idx) do
                        out.count = out.count + 1
                        if #out.names < limit then
                            out.names[#out.names + 1] = { name = tostring(key), type = type(member), via = "__index" }
                        end
                    end
                end)
                out.via_metatable = true
            elseif type(idx) == "function" then
                out.index_is_function = true
            elseif idx ~= nil then
                out.index_type = type(idx)
            end
            local mt_name = common.field(mt, "__name")
            if type(mt_name) == "string" then out.metatable_name = mt_name end
        elseif not mt_ok then
            out.metatable_error = tostring(mt)
        end
    end
    table.sort(out.names, function(a, b) return a.name < b.name end)
    return out
end

local function resolve_component(name)
    local ok, value = pcall(function() return api.type.ComponentType[name] end)
    if not ok then return nil, tostring(value) end
    if value == nil then return nil, "nil" end
    return value, nil
end

-- 只保留非 nil 的字段（v3 的输出 99% 是 {"type":"nil"}，白占体积）
local function probe_non_nil(bag, keys)
    local fields, count = {}, 0
    if bag == nil then return { fields = fields, count = 0 } end
    for _, key in ipairs(keys) do
        local v = common.field(bag, key)
        if v ~= nil then
            local d = { type = type(v) }
            if type(v) == "number" or type(v) == "string" or type(v) == "boolean" then
                d.value = v
            end
            local n = common.array_count(v)
            if n ~= nil then d.length = n end
            fields[key] = d
            count = count + 1
        end
    end
    return { fields = fields, count = count }
end

-- 探测一个对象的 metatable：__name（C++ 类型名）+ __index 的键名
local function describe_metatable(value)
    local out = {}
    if value == nil then return out end
    local ok, mt = pcall(getmetatable, value)
    if not ok then out.error = tostring(mt) return out end
    out.metatable_type = type(mt)
    if mt == nil then return out end
    local mt_name = common.field(mt, "__name")
    if type(mt_name) == "string" then out.name = mt_name end
    local idx = common.field(mt, "__index")
    out.index_type = type(idx)
    if type(idx) == "table" then
        local keys = {}
        pcall(function() for k in pairs(idx) do keys[#keys + 1] = tostring(k) end end)
        table.sort(keys)
        out.index_key_count = #keys
        out.index_keys = {}
        for i, k in ipairs(keys) do
            if i > MT_KEY_LIMIT then break end
            out.index_keys[i] = k
        end
    elseif type(idx) == "function" then
        out.index_is_function = true
    end
    return out
end

-- ★ v4 核心：`game.interface.getEntity(id)` 的聚合表全字段枚举
--   这是从官方 mod 源码里挖出来的入口：getEntity 返回的是一张可 pairs() 的聚合表，
--   键是小驼峰组件名（stationGroup / simBuildings / vehicles / ...）。
local function describe_aggregate(entity_id)
    local out = { entity_id = entity_id }
    local gi = common.field(game, "interface")
    local get_entity = common.field(gi, "getEntity")
    if type(get_entity) ~= "function" then
        out.error = "game.interface.getEntity unavailable (" .. type(get_entity) .. ")"
        return out
    end
    local ok, agg = pcall(function() return gi.getEntity(entity_id) end)
    if not ok then out.error = tostring(agg) return out end
    if agg == nil then out.error = "getEntity returned nil" return out end

    out.value_type = type(agg)
    local keys = {}
    local pairs_ok = pcall(function()
        for k in pairs(agg) do keys[#keys + 1] = tostring(k) end
    end)
    out.pairs_ok = pairs_ok
    table.sort(keys)
    out.key_count = #keys
    out.fields = {}
    for i, k in ipairs(keys) do
        if i > AGG_KEY_LIMIT then break end
        local v = common.field(agg, k)
        local d = { type = type(v) }
        if type(v) == "number" or type(v) == "string" or type(v) == "boolean" then
            d.value = v
        end
        local n = common.array_count(v)
        if n ~= nil then d.length = n end
        out.fields[k] = d
    end
    return out
end

-- ===== 5. 组件遍历 ========================================================
local function sample_entity(entity, component_type)
    local item = { entity_id = common.entity_id(entity) }

    -- 5a. 组件本体（api.engine.getComponent）—— 只留非 nil
    local bag_ok, bag = pcall(api.engine.getComponent, entity, component_type)
    if bag_ok and bag ~= nil then
        local probed = probe_non_nil(bag, PROBE_KEYS)
        item.component_value_type = type(bag)
        item.component_field_count = probed.count
        item.component_fields = probed.fields
        item.instance_meta = describe_metatable(bag)
    else
        item.component_error = tostring(bag)
    end

    -- 5b. ★ 聚合实体（game.interface.getEntity）—— 全字段枚举
    item.aggregate = describe_aggregate(item.entity_id)

    return item
end

local function walk_component(name, walk)
    local component_type, resolve_error = resolve_component(name)
    local entry = {
        resolved = component_type ~= nil,
        resolve_error = resolve_error,
        value_type = type(component_type),
        walked = false,
    }
    if component_type == nil then return entry end
    entry.type_meta = describe_metatable(component_type)
    if not walk then return entry end

    local count, detail = 0, {}
    local ok, iterate_error = pcall(api.engine.forEachEntityWithComponent, function(entity)
        count = count + 1
        if count <= SAMPLE_LIMIT then
            local sample_ok, item = pcall(sample_entity, entity, component_type)
            if sample_ok and item then
                detail[#detail + 1] = item
            else
                detail[#detail + 1] = { entity_id = common.entity_id(entity), sample_error = tostring(item) }
            end
        end
    end, component_type)
    entry.walked = true
    entry.count = count
    entry.samples = detail
    entry.iterate_error = ok and nil or tostring(iterate_error)
    return entry
end

-- ===== 6. 主流程 ==========================================================
function M.probe()
    local report = {
        probe_kind = "READ_ONLY_WORLD_PROBE_V4",
        write_command_sent = false,
        note = "v4: 走 game.interface.getEntity 拿字段名；补 6 个缺口；补 5 车种 + TERRAIN_TILE；只留非 nil",
        sample_limit = SAMPLE_LIMIT,
        walk_budget = WALK_BUDGET,
    }

    -- 6a. api.type.ComponentType 本身（回归 v3 结论：pairs() 枚举为空）
    local component_type_table = common.field(api and api.type, "ComponentType")
    report.component_type_probe = {
        exists = component_type_table ~= nil,
        value_type = type(component_type_table),
        pairs_members = safe_members(component_type_table, 50),
    }

    -- 6b. 候选名单 = api.type 成员名推导 + 策展名单
    local type_names = {}
    pcall(function()
        for key in pairs(api.type or {}) do type_names[#type_names + 1] = tostring(key) end
    end)
    table.sort(type_names)
    report.api_type_member_count = #type_names

    local seen, candidates = {}, {}
    local function add(name)
        if type(name) ~= "string" or name == "" then return end
        if seen[name] then return end
        seen[name] = true
        candidates[#candidates + 1] = name
    end
    for _, type_name in ipairs(type_names) do add(upper_snake(type_name)) end
    for _, name in ipairs(CURATED) do add(name) end
    table.sort(candidates)
    report.candidate_count = #candidates

    -- 6c. 逐个试解析（只查名字，代价极小）
    local resolved_names, missing_names = {}, {}
    for _, name in ipairs(candidates) do
        local component_type, resolve_error = resolve_component(name)
        if component_type ~= nil then
            resolved_names[#resolved_names + 1] = name
        else
            missing_names[#missing_names + 1] = { name = name, error = resolve_error }
        end
    end
    report.component_names_resolved = resolved_names
    report.component_names_missing = missing_names
    report.component_names_resolved_count = #resolved_names

    -- 6d. 实体遍历（WALK_LIST 先走；其余只记录 resolved）
    report.component_walk = {}
    local total_walked = 0
    local walked_set = {}
    local budget_hit = false
    for _, name in ipairs(WALK_LIST) do
        local entry
        if total_walked < WALK_BUDGET then
            entry = walk_component(name, true)
        else
            budget_hit = true
            entry = walk_component(name, false)
        end
        walked_set[name] = true
        if entry.count then total_walked = total_walked + entry.count end
        report.component_walk[name] = entry
    end
    for _, name in ipairs(resolved_names) do
        if not walked_set[name] then
            report.component_walk[name] = walk_component(name, false)
        end
    end
    report.total_entities_walked = total_walked
    report.walk_budget_hit = budget_hit

    -- 6e. 注册表盘点（v3 那 12 张）
    local api_root = api
    local engine = common.field(api_root, "engine")
    report.registries = {
        ["api"] = safe_members(api_root, 80),
        ["api.type"] = safe_members(common.field(api_root, "type"), 250),
        ["api.util"] = safe_members(common.field(api_root, "util"), 150),
        ["api.engine"] = safe_members(engine, 120),
        ["api.engine.system"] = safe_members(common.field(engine, "system"), 120),
        ["api.engine.util"] = safe_members(common.field(engine, "util"), 120),
        ["api.engine.component"] = safe_members(common.field(engine, "component"), 250),
        ["api.res"] = safe_members(common.field(api_root, "res"), 200),
        ["api.cmd"] = safe_members(common.field(api_root, "cmd"), 80),
        ["api.cmd.make"] = safe_members(common.field(common.field(api_root, "cmd"), "make"), 120),
        ["game"] = safe_members(game, 80),
        ["game.interface"] = safe_members(common.field(game, "interface"), 120),
        ["game.config"] = safe_members(common.field(game, "config"), 120),
    }

    -- 6f. ★ 缺口 1/2/6：三个没展开过的命名空间
    report.extra_namespaces = {
        ["api.engine.transport"] = safe_members(common.field(engine, "transport"), 200),
        ["api.engine.terrain"] = safe_members(common.field(engine, "terrain"), 200),
        ["api.engine.system_raw"] = safe_members(common.field(engine, "system"), 200),
    }

    -- 6g. ★ 缺口 3：31 个 ECS 系统各自的方法表
    local system_table = common.field(engine, "system")
    local system_names = {}
    pcall(function()
        for k in pairs(system_table or {}) do system_names[#system_names + 1] = tostring(k) end
    end)
    table.sort(system_names)
    report.system_methods = {}
    for _, name in ipairs(system_names) do
        report.system_methods[name] = safe_members(common.field(system_table, name), 80)
    end
    report.system_count = #system_names

    -- 6h. ★ 缺口 4：15 张 api.res 静态目录各自的方法表
    local res_table = common.field(api_root, "res")
    local res_names = {}
    pcall(function()
        for k in pairs(res_table or {}) do res_names[#res_names + 1] = tostring(k) end
    end)
    table.sort(res_names)
    report.res_methods = {}
    for _, name in ipairs(res_names) do
        report.res_methods[name] = safe_members(common.field(res_table, name), 80)
    end
    report.res_count = #res_names

    -- 6i. 自检：getEntity 对几个已知 id 是否真的可用
    local probe_ids = {}
    for _, name in ipairs({ "LINE", "STATION", "TRANSPORT_VEHICLE", "TOWN", "SIM_BUILDING" }) do
        local entry = report.component_walk[name]
        if entry and entry.samples and entry.samples[1] and entry.samples[1].entity_id then
            probe_ids[#probe_ids + 1] = { name = name, id = entry.samples[1].entity_id }
        end
    end
    report.get_entity_selfcheck = probe_ids

    -- 6j. 环境快照（1 个实体，代价极小，用于确认时机）
    local time_ok, game_time = pcall(function()
        return common.field(common.field(game, "interface"), "getGameTime")
    end)
    if time_ok and type(game_time) == "function" then
        local ok, value = pcall(function() return game.interface.getGameTime() end)
        report.game_time = ok and value or tostring(value)
    end

    return report
end

return M
