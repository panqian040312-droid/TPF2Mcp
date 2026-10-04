-- 水运 / 航空"航路"探针 v2（只读）
--
-- ── 为什么有 v2 ─────────────────────────────────────────────────────────
-- v1 试调 `shipMoveSystem.getShipInfo` 等接口，全部回报 `available: false,
-- member_type: "table"`，我就据此写了"Lua 侧取不到航路"的结论。
-- 后来复查发现 **判据本身是错的**：v1 的 `probe_method` 要求 `type(fn) == "function"`，
-- 而这些绑定在 Lua 侧看是 **table**（Sol2 常把可调用对象做成带 `__call` 的 table）
-- → **一次都没真正调用过**。所以 v2 改成：
--   **不管什么类型都试着调用**（pcall），并把失败原文留下；同时把成员自己的
--   成员表和 metatable 情况记下来，好判断到底该怎么调。
--
-- ── v2 做四件事 ─────────────────────────────────────────────────────────
-- ① 六个 system 的成员：逐个**试调**（无参 / 实体 / 实体id），既看能不能调，也看返回结构
-- ② 那些"是 table 的成员"自己长什么样：成员名 + metatable 的 `__index` / `__call`
-- ③ `api.type` 里与水运/航空有关的 15 个类型（ShipInfo / MovePathAircraft / PathPos /
--    WaterMesh / RunwayList / TpNetData …）：枚举成员 + 试调 → 很可能直接给出**字段名清单**
-- ④ 拿一艘船、一架飞机，对 MOVE_PATH / MOVE_PATH_AIRCRAFT / SHIP / AIRCRAFT /
--    TRANSPORT_NETWORK / TP_NET_LINK / RUNWAY_LIST 等组件**按候选字段名扫一遍**，
--    看哪个字段真的存在（船机现在连 speed 都读不到，说明字段名还没找对）
--
-- ⚠️ 输出量控制：一律只记长度 + 前几项形状，绝不把路径点数组整个写进去。

local common = require "tpf2_mcp/collectors/common"

local M = {}

local MAX_MEMBER_NAMES = 60
local MAX_ITEMS = 8
local MAX_SCAN = 3000
local MAX_ATTEMPT_TEXT = 200

-- 枚举一个值上能看到的成员（pairs → metatable.__index 两条路都试）。
local function safe_members(value, limit)
    local out = { value_type = type(value), count = 0, enumerable = false, names = {} }
    if value == nil then out.value_type = "nil" return out end
    local cap = limit or MAX_MEMBER_NAMES

    pcall(function()
        for key, member in pairs(value) do
            out.count = out.count + 1
            if out.count > MAX_SCAN then break end
            if #out.names < cap then
                out.names[#out.names + 1] = { name = tostring(key), type = type(member) }
            end
        end
    end)
    out.enumerable = out.count > 0

    if out.count == 0 then
        local mt_ok, mt = pcall(getmetatable, value)
        if mt_ok and type(mt) == "table" then
            local idx = common.field(mt, "__index")
            if type(idx) == "table" then
                pcall(function()
                    for key, member in pairs(idx) do
                        out.count = out.count + 1
                        if out.count > MAX_SCAN then break end
                        if #out.names < cap then
                            out.names[#out.names + 1] = { name = tostring(key), type = type(member), via = "__index" }
                        end
                    end
                end)
                out.via_metatable = true
            elseif type(idx) == "function" then
                out.index_is_function = true
            end
        end
    end
    return out
end

-- 描述返回值形状。深度受限：userdata 只到"类型 + 一层成员"。
local function shape(value, depth)
    local value_type = type(value)
    if value_type == "userdata" then
        local entry = safe_members(value, MAX_MEMBER_NAMES)
        entry.kind = "userdata"
        return entry
    end
    if value_type ~= "table" then
        local entry = { kind = value_type }
        if value_type == "number" or value_type == "string" or value_type == "boolean" then entry.value = value end
        return entry
    end
    local out = { kind = "table", array_len = common.array_count(value), count = 0 }
    local items = {}
    pcall(function()
        for key, member in pairs(value) do
            out.count = out.count + 1
            if out.count > MAX_SCAN then break end
            if #items < MAX_ITEMS and depth > 0 then
                items[#items + 1] = { key = tostring(key), shape = shape(member, depth - 1) }
            end
        end
    end)
    if #items > 0 then out.items = items end
    return out
end

-- 一个成员自己长什么样：成员名 + metatable 的 __index / __call 情况。
-- 目的：判断"这是个可调用对象，还只是个描述表"。
local function describe_member(value)
    if value == nil then return { value_type = "nil" } end
    local out = safe_members(value, MAX_MEMBER_NAMES)
    local mt_ok, mt = pcall(getmetatable, value)
    if mt_ok and type(mt) == "table" then
        out.has_metatable = true
        local call = common.field(mt, "__call")
        if call ~= nil then out.metatable_call_type = type(call) end
        local idx = common.field(mt, "__index")
        if idx ~= nil then out.metatable_index_type = type(idx) end
    end
    return out
end

-- ★ v2 的关键：**不管什么类型都试调**。含 nil 的参数一律跳过
-- （`table.unpack({nil})` 会变成"0 个参数"，那不叫"用实体调"）。
local function probe_call_value(value, variants)
    if value == nil then return { available = false, value_type = "nil" } end

    local out = describe_member(value)
    out.attempts = {}
    local tried = {}
    for _, variant in ipairs(variants) do
        local has_nil = false
        for index = 1, #variant.args do
            if variant.args[index] == nil then has_nil = true end
        end
        if not has_nil and not tried[variant.label] then
            tried[variant.label] = true
            local ok, result = pcall(value, table.unpack(variant.args))
            if ok then
                out.winning_signature = variant.label
                out.result = shape(result, 2)
                out.callable = true
                return out
            end
            local text = tostring(result)
            if #text > MAX_ATTEMPT_TEXT then text = string.sub(text, 1, MAX_ATTEMPT_TEXT) end
            out.attempts[#out.attempts + 1] = { signature = variant.label, error = text }
        end
    end
    if #out.attempts == 0 then out.attempts = nil end
    if out.callable == nil then out.callable = false end
    return out
end

-- 遍历式接口（forEach 这类）：同样不要求 type == "function"。
local function probe_for_each(container)
    local value = common.field(container, "forEach")
    if value == nil then return { available = false, value_type = "nil" } end
    local out = describe_member(value)
    out.attempts = {}
    local calls, first = 0, nil
    local ok, result = pcall(value, function(a, b)
        calls = calls + 1
        if first == nil then
            first = {
                arg1_type = type(a), arg1_id = common.entity_id(a),
                arg2_type = type(b), arg2_id = common.entity_id(b),
            }
        end
    end)
    out.callable = ok
    out.ok = ok
    if not ok then
        local text = tostring(result)
        if #text > MAX_ATTEMPT_TEXT then text = string.sub(text, 1, MAX_ATTEMPT_TEXT) end
        out.attempts[#out.attempts + 1] = { signature = "(callback)", error = text }
    end
    out.callback_calls = calls
    out.first_callback_args = first
    return out
end

-- 从 TRANSPORT_VEHICLE 里挑一艘船、一架飞机（判据：带 SHIP / AIRCRAFT 组件）。
local function pick_vehicle_targets(errors)
    local targets = { ship = nil, aircraft = nil }
    local counts = { ship = 0, aircraft = 0 }
    local ok, reason = common.safe_for_each_entity("TRANSPORT_VEHICLE", function(entity)
        local ship = common.safe_get_component(entity, "SHIP", errors)
        if ship ~= nil then
            counts.ship = counts.ship + 1
            if targets.ship == nil then
                targets.ship = { entity = entity, entity_id = common.entity_id(entity) }
            end
        end
        local aircraft = common.safe_get_component(entity, "AIRCRAFT", errors)
        if aircraft ~= nil then
            counts.aircraft = counts.aircraft + 1
            if targets.aircraft == nil then
                targets.aircraft = { entity = entity, entity_id = common.entity_id(entity) }
            end
        end
    end, errors)
    if not ok then errors[#errors + 1] = { component = "TRANSPORT_VEHICLE.route_probe", error = tostring(reason) } end
    targets.counts = counts
    return targets
end

-- ④ 组件字段候选名：**尽量宽**。船/飞机现在连 `speed` 都读不到，
--    说明我们还没找对字段名 —— 这一步就是把名字试出来。
local COMPONENT_FIELD_CANDIDATES = {
    "path", "movePath", "route", "routes", "routeId", "routesId",
    "edge", "edgeId", "edgePos", "edgeIndex", "edges", "edgeIds",
    "node", "nodeId", "nodes", "nodeIds", "nextNode", "prevNode", "startNode", "endNode",
    "targetNode", "targetNodeId", "fromNode", "toNode",
    "lane", "laneId", "laneIds", "lanes", "link", "linkId", "links", "linkEntities",
    "network", "networkId", "net", "netId", "tpNet", "tpNetId", "transportNetwork",
    "pathPos", "pathIndex", "position", "positions", "pos", "points", "waypoints",
    "index", "offset", "distance", "length", "count", "size", "progress",
    "current", "front", "back", "dir", "direction", "speed", "velocity", "state", "reserved",
    "runway", "runways", "runwayList", "runwayId", "berth", "berths", "dock", "docks", "harbor",
    "airport", "station", "stations", "stationIds", "stopIndex", "line", "lineId", "vehicle",
    "water", "waterMesh", "mesh", "area", "region",
}

local COMPONENT_NAMES = {
    "MOVE_PATH", "MOVE_PATH_AIRCRAFT", "SHIP", "AIRCRAFT",
    "TRANSPORT_NETWORK", "TP_NET_LINK", "RUNWAY_LIST",
    "SIM_ENTITY_MOVING", "BASE_NODE", "MODEL_INSTANCE_LIST",
}

local function scan_components(entity, errors)
    local out = {}
    for _, name in ipairs(COMPONENT_NAMES) do
        local value = common.safe_get_component(entity, name, errors)
        if value ~= nil then
            local entry = common.probe_fields(value, COMPONENT_FIELD_CANDIDATES)
            entry.members = safe_members(value, 24)
            out[name] = entry
        else
            out[name] = { value_type = "nil" }
        end
    end
    return out
end

-- ③ api.type 里与水运/航空有关的类型。
local TYPE_NAMES = {
    "Ship", "ShipInfo", "Aircraft", "AircraftInfo",
    "MovePath", "MovePathAircraft", "Path", "PathPos", "PathPosData", "ExtPath",
    "RunwayList", "TpNetData", "TpNetLink", "TpNetLinkProposal", "WaterMesh",
}

local function probe_api_types(entity, entity_id)
    local root = common.field(api, "type")
    local out = { root_type = type(root), types = {} }
    for _, name in ipairs(TYPE_NAMES) do
        local value = common.field(root, name)
        if value == nil then
            out.types[name] = { value_type = "nil" }
        else
            local entry = describe_member(value)
            entry.call = probe_call_value(value, {
                { label = "()", args = {} },
                { label = "(entity)", args = { entity } },
                { label = "(entity_id)", args = { entity_id } },
            })
            out.types[name] = entry
        end
    end
    return out
end

-- 读组件时用的"静默错误表"：读不到只是返回 nil，不该往 errors 里堆噪音
local SILENT = setmetatable({}, { __index = function() return true end })

-- dump 一个值的前 limit 个字段（键名 / 类型 / 值）。
-- 为什么需要它：现有的 scan_components 只报"这个组件能不能读"（resolved / value_type / walked），
-- 报**不出内容**。而用户要的"飞机航道 / 跑到占用 / 排队"恰恰是**字段内容**
-- （AIRCRAFT.reservedLandingRunway、reservedTo 等），所以必须能把内容打出来。
local function dump_fields(value, limit)
    if value == nil then return { type = "nil" } end
    local kind = type(value)
    if kind == "number" or kind == "string" or kind == "boolean" then
        return { type = kind, value = value }
    end
    local out = { type = kind, items = {}, count = 0 }
    pcall(function()
        local n = 0
        for key, item in pairs(value) do
            n = n + 1
            out.count = n
            if #out.items >= limit then break end
            local item_kind = type(item)
            if item_kind == "number" or item_kind == "string" or item_kind == "boolean" then
                out.items[#out.items + 1] = { key = tostring(key), type = item_kind, value = item }
            else
                out.items[#out.items + 1] = { key = tostring(key), type = item_kind, text = tostring(item) }
            end
        end
    end)
    -- 有些 userdata 只支持 1..#v 的序列访问
    if out.count == 0 then
        pcall(function()
            local len = #value
            if len and len > 0 then
                out.count = len
                for i = 1, math.min(len, limit) do
                    out.items[#out.items + 1] = { key = tostring(i), type = type(value[i]), text = tostring(value[i]) }
                end
            end
        end)
    end
    return out
end

-- 用 forEach 回调拿"第一个实体"。
-- 🔴 为什么非得这样拿（2026-09-30 排错结论）：
--   上一轮（v2）isReserved / getAirCraftInfo / getShipInfo **全部失败**，
--   错误是 "expected userdata, received no value" —— 看着像签名不对，其实不是：
--   传进去的 entity 是 **nil**（pick_vehicle_targets 用 getEntity(id) 取实体那步没成功，
--   于是 {entity} 成了空表 → "received no value"）。
--   而 forEach 的回调**确实**拿到有效 userdata（见 first_callback_args 里的 arg2_type）。
--   ⇒ forEach 是这里唯一确定可用的句柄来源，不要再用 getEntity(id) 去凑。
local function first_from_for_each(container)
    local got = nil
    pcall(function()
        local fn = common.field(container, "forEach")
        if fn == nil then return end
        fn(function(id, entity)
            if got == nil then got = { id = id, entity = entity } end
        end)
    end)
    return got
end

function M.collect()
    local started = common.clock()
    local errors = {}
    local result = {
        schema_version = 2,
        probe_kind = "READ_ONLY_ROUTE_DISCOVERY",
        source_status = "ENGINE_OBSERVED_DIAGNOSTIC",
        generated_at = os and os.time and os.time() or 0,
        errors = errors,
        write_command_sent = false,
        note = "v2: 不管成员是什么类型都试调（v1 只认 function，导致一次都没调成）",
    }

    local engine = api and api.engine
    local system = common.field(engine, "system")
    result.system_type = type(system)
    result.system_names = {}
    pcall(function()
        for key in pairs(system or {}) do
            if #result.system_names < 80 then result.system_names[#result.system_names + 1] = tostring(key) end
        end
    end)
    table.sort(result.system_names)

    -- ① 样本车辆
    local targets = pick_vehicle_targets(errors)
    local ship_entity = targets.ship and targets.ship.entity
    local aircraft_entity = targets.aircraft and targets.aircraft.entity
    local ship_id = targets.ship and targets.ship.entity_id
    local aircraft_id = targets.aircraft and targets.aircraft.entity_id
    result.ship_sample_entity_id = ship_id
    result.aircraft_sample_entity_id = aircraft_id
    result.vehicle_counts = targets.counts

    -- ② 六个 system：成员逐个试调
    local function system_report(key, list)
        local container = common.field(system, key)
        local entry = { system_available = container ~= nil, system_members = safe_members(container, 20) }
        for _, item in ipairs(list) do
            entry[item[1]] = probe_call_value(common.field(container, item[2]), item[3])
        end
        return entry
    end

    local function variants_for(entity, entity_id)
        return {
            { label = "()", args = {} },
            { label = "(entity)", args = { entity } },
            { label = "(entity_id)", args = { entity_id } },
        }
    end

    result.ship_move_system = system_report("shipMoveSystem", {
        { "get_ship_info", "getShipInfo", variants_for(ship_entity, ship_id) },
    })
    result.ship_move_system.for_each = probe_for_each(common.field(system, "shipMoveSystem"))

    result.aircraft_move_system = system_report("aircraftMoveSystem", {
        { "get_aircraft_info", "getAirCraftInfo", variants_for(aircraft_entity, aircraft_id) },
        { "is_reserved", "isReserved", variants_for(aircraft_entity, aircraft_id) },
    })
    result.aircraft_move_system.for_each = probe_for_each(common.field(system, "aircraftMoveSystem"))

    result.runway_system = system_report("runwaySystem", {
        { "landing_node_id_map", "getLandingNodeIdMap", { { label = "()", args = {} } } },
        { "takeoff_node_id_map", "getTakeoffNodeIdMap", { { label = "()", args = {} } } },
    })

    result.transport_network_system = system_report("transportNetworkSystem", {
        { "tp_net_data", "getTpNetData", { { label = "()", args = {} } } },
        { "intersections", "getIntersections", { { label = "()", args = {} } } },
    })

    result.tp_net_link_system = system_report("tpNetLinkSystem", {
        { "link_entities", "getLinkEntities", { { label = "()", args = {} } } },
        { "edge_id_2_link_entities", "getEdgeId2linkEntities", { { label = "()", args = {} } } },
    })

    result.river_system = system_report("riverSystem", {
        { "water_mesh_entities", "getWaterMeshEntities", { { label = "()", args = {} } } },
    })

    -- ③ api.type 相关类型
    result.api_types = probe_api_types(ship_entity or aircraft_entity, ship_id or aircraft_id)

    -- ④ 组件字段扫描（船 / 飞机各一份）
    result.ship_components = ship_entity and scan_components(ship_entity, errors) or nil
    result.aircraft_components = aircraft_entity and scan_components(aircraft_entity, errors) or nil

    -- ⑤ 用 forEach 拿到的**有效句柄**重试（v2 就是死在这一步，见 first_from_for_each 的说明），
    --    并顺手把组件**内容**打出来 —— 用户 2026-09-30 问的"飞机/船舶航道摸清了吗、
    --    机场吞吐上限"答案就在这几个组件里：
    --      AIRCRAFT.reservedLandingRunway / reservedTo（跑道是否已被预留 + 预留到路径第几条边）
    --      MOVE_PATH_AIRCRAFT（飞机的实际航路 = 边序列）
    --      SHIP / MOVE_PATH（船的同理）
    local retry = { note = "v3: 用 forEach 的有效句柄重试（v2 传进去的 entity 是 nil）" }

    local aircraft_container = common.field(system, "aircraftMoveSystem")
    local ship_container = common.field(system, "shipMoveSystem")
    local aircraft_handle = first_from_for_each(aircraft_container)
    local ship_handle = first_from_for_each(ship_container)

    if aircraft_handle ~= nil then
        local variants = variants_for(aircraft_handle.entity, aircraft_handle.id)
        retry.aircraft = {
            id = aircraft_handle.id,
            entity_type = type(aircraft_handle.entity),
            is_reserved = probe_call_value(common.field(aircraft_container, "isReserved"), variants),
            aircraft_info = probe_call_value(common.field(aircraft_container, "getAirCraftInfo"), variants),
            component_aircraft = dump_fields(common.safe_get_component(aircraft_handle.entity, "AIRCRAFT", SILENT), 24),
            component_move_path = dump_fields(common.safe_get_component(aircraft_handle.entity, "MOVE_PATH_AIRCRAFT", SILENT), 24),
            component_moving = dump_fields(common.safe_get_component(aircraft_handle.entity, "SIM_ENTITY_MOVING", SILENT), 16),
        }
    end

    if ship_handle ~= nil then
        local variants = variants_for(ship_handle.entity, ship_handle.id)
        retry.ship = {
            id = ship_handle.id,
            entity_type = type(ship_handle.entity),
            ship_info = probe_call_value(common.field(ship_container, "getShipInfo"), variants),
            component_ship = dump_fields(common.safe_get_component(ship_handle.entity, "SHIP", SILENT), 24),
            component_move_path = dump_fields(common.safe_get_component(ship_handle.entity, "MOVE_PATH", SILENT), 24),
            component_moving = dump_fields(common.safe_get_component(ship_handle.entity, "SIM_ENTITY_MOVING", SILENT), 16),
        }
    end

    result.retry_with_valid_handle = retry

    -- ⑥ 跑道节点映射的**内容**（v2 只知道各有 128 条，不知道里面装什么）。
    --    这是"机场吞吐"的关键：起飞 / 降落各有一套"节点 → ?"的表，
    --    而 AIRCRAFT.reservedTo 说的"预留到路径第几条边"要跟它对齐才能算出排队。
    local runway_maps = {}
    pcall(function()
        local runway_system = common.field(system, "runwaySystem")
        for _, method in ipairs({ "getTakeoffNodeIdMap", "getLandingNodeIdMap" }) do
            local fn = common.field(runway_system, method)
            if fn == nil then
                runway_maps[method] = { error = "method unavailable" }
            else
                local ok, value = pcall(function() return fn() end)
                if not ok then
                    runway_maps[method] = { error = tostring(value) }
                elseif value == nil then
                    runway_maps[method] = { error = "nil" }
                else
                    local entry = { type = type(value), count = common.array_count(value) or -1, sample = {} }
                    pcall(function()
                        local n = 0
                        for key, item in pairs(value) do
                            n = n + 1
                            if n > 8 then break end
                            entry.sample[#entry.sample + 1] = {
                                key = tostring(key), key_type = type(key),
                                value = tostring(item), value_type = type(item),
                            }
                        end
                    end)
                    runway_maps[method] = entry
                end
            end
        end
    end)
    result.runway_maps = runway_maps

    -- ⑦ tp_net_link 的内容（v2 已知 2363 条，这里看键值形态 —— 边→链路实体是画航路的基础）
    pcall(function()
        local container = common.field(system, "tpNetLinkSystem")
        local fn = common.field(container, "getEdgeId2linkEntities")
        if fn ~= nil then
            local ok, value = pcall(function() return fn() end)
            if ok and value ~= nil then result.tp_net_link_sample = dump_fields(value, 8) end
        end
    end)

    result.duration_ms = (common.clock() - started) * 1000
    return result
end

return M
