local M = {}

function M.clock()
    if os and type(os.clock) == "function" then
        local ok, value = pcall(os.clock)
        if ok and type(value) == "number" then return value end
    end
    return 0
end

-- ⚠️ nil 必须短路成 nil。
-- 老写法 `tonumber(tostring(entity)) or tostring(entity)` 对 nil 会返回**字符串 "nil"**
-- （`tonumber("nil")` 是 nil，于是走 `tostring(nil)` = "nil"）—— 于是
-- `if construction_id ~= nil then ... end` 恒成立，引擎收到字符串会报
-- "expected number, received string"（2026-09-30 实测的错误来源）。
-- 只加 nil 短路，其余输入的行为**一字不变**。
function M.entity_id(entity)
    if entity == nil then return nil end
    return tonumber(tostring(entity)) or tostring(entity)
end

-- 边结构类型：0 = 地面、1 = 桥、2 = 隧道。
--
-- 判据来自游戏自己的代码（res/scripts/selectortooltip.lua:70-88）：
--     local bridgeType = 1
--     local tunnelType = 2
--     local edgeType = baseEdge.type
--     if edgeType == bridgeType then ... api.res.bridgeTypeRep.get(typeIndex).name
--     elseif edgeType == tunnelType then ... api.res.tunnelTypeRep.get(typeIndex).name
-- 玩家把鼠标悬在桥上/隧道上时看到的名字，就是这么来的。
--
-- 公路与铁路共用 BASE_EDGE 这张表（BASE_EDGE_STREET / BASE_EDGE_TRACK 的字段完全相同），
-- 所以同一个字段对两者都有效：公路的桥、隧道、下穿也能分开。
--
-- 未知取值不硬塞成 GROUND —— 宁可显示成 TYPE_7 让人看见，也不要悄悄画错。
function M.structure_of(edge_type)
    if type(edge_type) ~= "number" then return "UNKNOWN" end
    if edge_type == 0 then return "GROUND" end
    if edge_type == 1 then return "BRIDGE" end
    if edge_type == 2 then return "TUNNEL" end
    return "TYPE_" .. tostring(edge_type)
end

-- 运输方式。`TRANSPORT_VEHICLE.carrier` 在**组件视图里是数字**（聚合表里才是字符串
-- "RAIL"），映射由 2026-09-28 本存档 664 辆车实测反推：
--     carrier_raw 分布     →  0:595   1:28   2:3   3:20   4:18
--     同存档聚合表计数     →          TRAIN=28      AIRCRAFT=20   SHIP=18
--     ⇒  0=ROAD  1=RAIL  3=AIR  4=WATER
-- carrier=2 的 3 辆尚未定性（不是 SHIP，数量对不上），**刻意留空** ——
-- 硬塞进 WATER 会让这 3 辆车在地图上显示成错误的颜色。
M.CARRIER_NAMES = { [0] = "ROAD", [1] = "RAIL", [3] = "AIR", [4] = "WATER" }

-- 数字或字符串形式的 carrier 都归一成上面的名字；认不出返回 nil（不猜）。
function M.carrier_name(value)
    if type(value) == "number" then return M.CARRIER_NAMES[value] end
    if type(value) == "string" then
        local upper = string.upper(value)
        if upper == "ROAD" or upper == "RAIL" or upper == "AIR" or upper == "WATER" then return upper end
    end
    return nil
end

-- 统计表里票数最多的键；并列或空表返回 nil。
function M.majority_key(tally)
    local best, best_count, tied = nil, 0, false
    for key, count in pairs(tally or {}) do
        if count > best_count then best, best_count, tied = key, count, false
        elseif count == best_count then tied = true end
    end
    if tied then return nil end
    return best
end

function M.component_type(name)
    local ok, value = pcall(function() return api.type.ComponentType[name] end)
    if not ok or value == nil then return nil, "component type unavailable: " .. tostring(name) end
    return value
end

function M.safe_get_component(entity, component_name, errors)
    local component_type, type_error = M.component_type(component_name)
    if not component_type then
        errors[#errors + 1] = { entity_id = M.entity_id(entity), component = component_name, error = type_error }
        return nil
    end
    local ok, value = pcall(api.engine.getComponent, entity, component_type)
    if not ok then
        errors[#errors + 1] = { entity_id = M.entity_id(entity), component = component_name, error = tostring(value) }
        return nil
    end
    return value
end

function M.safe_for_each_entity(component_name, callback, errors)
    local component_type, type_error = M.component_type(component_name)
    if not component_type then return false, type_error end
    local count = 0
    local ok, iterate_error = pcall(api.engine.forEachEntityWithComponent, function(entity)
        count = count + 1
        local entity_ok, entity_error = pcall(callback, entity)
        if not entity_ok then
            errors[#errors + 1] = { entity_id = M.entity_id(entity), component = component_name, error = tostring(entity_error) }
        end
    end, component_type)
    if not ok then return false, tostring(iterate_error) end
    return true, count
end

function M.safe_collect(collector_name, collect_fn)
    local started = M.clock()
    local ok, entities, errors = pcall(collect_fn)
    local duration_ms = (M.clock() - started) * 1000
    if not ok then
        return {}, { ok = false, count = 0, duration_ms = duration_ms, error = tostring(entities) }
    end
    return entities, { ok = #errors == 0, count = #entities, duration_ms = duration_ms, errors = errors }
end

function M.name_from_component(component)
    if component == nil then return nil end
    if type(component) == "string" then return component end
    -- TPF2 components are userdata in the live game state. Field access must
    -- be protected just like ordinary table access.
    local name_ok, name = pcall(function() return component.name end)
    if name_ok and type(name) == "string" then return name end
    local value_ok, value = pcall(function() return component.value end)
    if value_ok and type(value) == "string" then return value end
    return nil
end

function M.field(value, key)
    if value == nil then return nil end
    local ok, result = pcall(function() return value[key] end)
    if ok then return result end
    return nil
end

function M.array_count(value)
    if value == nil then return nil end
    -- Engine collections may be userdata rather than ordinary Lua tables.
    -- Their length metamethod is safe to query under pcall.
    local ok, count = pcall(function() return #value end)
    if ok and type(count) == "number" then return count end
    return nil
end

function M.sequence_values(value)
    local count = M.array_count(value)
    if not count then return {} end
    -- Engine repository arrays may be zero based while still exposing a Lua
    -- length. Prefer 0..count-1 when that full range is populated.
    local zero = M.field(value, 0)
    local one_past_zero_range = M.field(value, count)
    local start_index = zero ~= nil and one_past_zero_range == nil and 0 or 1
    local result = {}
    for index = start_index, start_index + count - 1 do
        local item = M.field(value, index)
        if item ~= nil then result[#result + 1] = item end
    end
    return result
end

function M.safe_type(value)
    return type(value)
end

function M.probe_fields(value, keys)
    local result = { value_type = type(value) }
    for _, key in ipairs(keys) do
        local field = M.field(value, key)
        local detail = { type = type(field) }
        if type(field) == "number" or type(field) == "string" or type(field) == "boolean" then detail.value = field end
        local count = M.array_count(field)
        if count ~= nil then detail.length = count end
        result[tostring(key)] = detail
    end
    return result
end

-- ─────────────────────────────────────────────────────────────────────────────
-- 组件清单与"两条取值路"（2026-09-30 晚，被两个探针同时撞出来的坑）
--
-- ① **`pairs(api.type.ComponentType)` 在本机枚举不出任何东西** —— 路况层和经济探针
--    都写了"列出这个实体挂了哪些组件"，两个都返回空数组。要问这个问题，只能照下面
--    这张常量表逐个 `getComponent` 试。
-- ② **组件的字段读取有两条路，可能各自单独失效**：
--    · `component["字段"]`（getter）—— `ROAD_VEHICLE` 的字段在这条路上**全 nil**；
--    · `pairs(component)`         —— `TOWN.name/position` 在这条路上才拿得到。
--    还有第三条：`game.interface.getEntity(id)` 的**聚合表**（`TOWN.position`、
--    `BASE_EDGE_STREET.streetType` 都只在那里）。取字段一律"getter → pairs"，
--    个别字段还要补 interface。
-- ─────────────────────────────────────────────────────────────────────────────
M.COMPONENT_NAMES = {
    "ACCOUNT", "AIRCRAFT", "ANIMAL", "ASSET_GROUP", "ASSET_GROUP_AUTOREMOVE", "AUDIO_EMITTER",
    "BASE_EDGE", "BASE_EDGE_STREET", "BASE_EDGE_TRACK", "BASE_NODE", "BASE_NODE_TRAFFIC_LIGHT",
    "BASE_PARALLEL_STRIP", "BOUNDING_VOLUME", "BRIDGE", "BUILD_COST", "COLLIDER_LIST", "COLOR",
    "CONSTRUCTION", "EMISSION_GRID", "FIELD", "GAME_SPEED", "GAME_TIME", "LINE", "LOG_BOOK",
    "LOT_LIST", "MAINTENANCE_COST", "MODEL_INSTANCE_LIST", "MODEL_PERSON", "MOVE_PATH",
    "MOVE_PATH_AIRCRAFT", "NAME", "PARCEL", "PARTICLE_SYSTEM", "PERSON_CAPACITY", "PLAYER",
    "PLAYER_OWNED", "RAIL_VEHICLE", "RAILROAD_CROSSING", "ROAD_VEHICLE", "RUNWAY_LIST", "SCAFFOLD",
    "SHAPE_LIST", "SHIP", "SIGNAL_LIST", "SIM_BUILDING", "SIM_CARGO", "SIM_CARGO_AT_TERMINAL",
    "SIM_ENTITY_AT_BUILDING", "SIM_ENTITY_AT_STOCK", "SIM_ENTITY_AT_TERMINAL",
    "SIM_ENTITY_AT_VEHICLE", "SIM_ENTITY_IDLE", "SIM_ENTITY_MOVING", "SIM_PERSON",
    "SIM_PERSON_AT_TERMINAL", "SIM_PERSON_AT_VEHICLE", "STATION", "STATION_GROUP", "STOCK_LIST",
    "TERRAIN", "TERRAIN_ALIGNMENT_LIST", "TERRAIN_TILE", "TERRAIN_TILE_BRUSH",
    "TERRAIN_TILE_HEIGHTMAP", "TICK_EPOCH", "TOWN", "TOWN_BUILDING", "TOWN_CONNECTION", "TRAIN",
    "TRANSPORT_HISTORY", "TRANSPORT_NETWORK", "TRANSPORT_VEHICLE", "TP_NET_LINK", "VEHICLE_DEPOT",
    "VEHICLE_ORDER", "WATER_MESH", "WORLD",
}

-- 一个实体挂了哪些组件（逐个试）。实体为 nil 时返回 nil。
function M.components_of(entity)
    if entity == nil then return nil end
    local names = {}
    for index = 1, #M.COMPONENT_NAMES do
        local name = M.COMPONENT_NAMES[index]
        if M.safe_get_component(entity, name, {}) ~= nil then names[#names + 1] = name end
    end
    return names
end

-- 把引擎组件（userdata）摊成普通 table。失败返回空表。
function M.flatten(value)
    local out = {}
    if value == nil then return out end
    pcall(function()
        for key, item in pairs(value) do out[key] = item end
    end)
    return out
end

-- 读字段：**先 getter，再 pairs 兜底**。两条都拿不到才是 nil。
function M.pick(value, key)
    local direct = M.field(value, key)
    if direct ~= nil then return direct end
    return M.flatten(value)[key]
end

return M
