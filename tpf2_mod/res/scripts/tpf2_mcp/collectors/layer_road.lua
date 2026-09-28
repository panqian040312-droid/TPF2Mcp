-- 公路网图层采集器（只读）
--
-- 数据源与读法（2026-09-28 修正）：
--   * 遍历组件用 BASE_EDGE_STREET —— 不能用"遍历 BASE_EDGE 再看 track 字段"，
--     因为 `track` 只存在于 game.interface.getEntity 的聚合表，组件视图里读不到。
--   * 几何读法与 collectors/rail_network.lua 完全一致：
--       getComponent(e,"BASE_EDGE")  → node0 / node1 / tangent0 / tangent1
--       getComponent(node,"BASE_NODE").position → 端点坐标（带缓存）
--     注意：node0pos / node1pos 那种"端点坐标直读"只存在于聚合表，组件视图没有。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"
local field_probe = require "tpf2_mcp/collectors/field_probe"

local M = {}

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

local function text(value)
    if type(value) == "string" and value ~= "" then return value end
    return nil
end

-- 端点节点坐标读取器（照 rail_network.lua 的 base_node()，带去重缓存）。
-- 读不到时只记一条样例错误 —— 否则 9793 个节点会把 errors 撑爆。
local function node_reader(errors, cache)
    local reported = false
    return function(raw)
        local id = common.entity_id(raw)
        if id == nil then return nil, nil end
        local cached = cache[id]
        if cached ~= nil then
            if cached == false then return nil, id end
            return cached, id
        end
        local node = component_access.get(raw, "BASE_NODE")
        if node == nil and not reported then
            reported = true
            errors[#errors + 1] = { component = "BASE_NODE",
                                    note = "unavailable; further occurrences only counted in skipped" }
        end
        local position = vec(common.field(node, "position")) or vec(common.field(node, "pos"))
        cache[id] = position or false
        return position, id
    end
end

function M.collect()
    local errors = {}
    local edges, nodes = {}, {}
    local node_cache = {}
    local street_types = {}
    local structures = {}
    local skipped = 0
    local probe = nil
    local base_missing = false
    local read_node = node_reader(errors, node_cache)

    local ok, scanned_or_error = common.safe_for_each_entity("BASE_EDGE_STREET", function(edge_entity)
        local base = component_access.get(edge_entity, "BASE_EDGE")
        if base == nil then
            skipped = skipped + 1
            if not base_missing then
                base_missing = true
                errors[#errors + 1] = { component = "BASE_EDGE",
                                        note = "unavailable on street edge; further occurrences only counted in skipped" }
            end
            return
        end
        if probe == nil then
            -- 只对第一个实体做字段普查：开销可忽略，但能一次性看清真实字段名
            probe = {
                base = field_probe.describe(base),
                street = field_probe.describe(component_access.get(edge_entity, "BASE_EDGE_STREET"), 16),
            }
        end

        local raw0, raw1 = common.field(base, "node0"), common.field(base, "node1")
        local position0, id0 = read_node(raw0)
        local position1, id1 = read_node(raw1)
        if id0 == nil or id1 == nil or position0 == nil or position1 == nil then
            skipped = skipped + 1
            return
        end
        nodes[id0] = nodes[id0] or { entity_id = id0, position = position0 }
        nodes[id1] = nodes[id1] or { entity_id = id1, position = position1 }

        local street_type = text(common.field(base, "streetType"))
        if street_type ~= nil then
            street_types[street_type] = (street_types[street_type] or 0) + 1
        end

        -- 结构类型：0 地面 / 1 桥 / 2 隧道（+ 保留其余取值，避免把未知值硬塞成地面）
        local edge_type = common.field(base, "type")
        local structure = common.structure_of(edge_type)
        structures[structure] = (structures[structure] or 0) + 1

        edges[#edges + 1] = {
            entity_id = common.entity_id(edge_entity),
            node0 = id0,
            node1 = id1,
            tangent0 = vec(common.field(base, "tangent0")),
            tangent1 = vec(common.field(base, "tangent1")),
            street_type = street_type,
            has_bus = common.field(base, "hasBus") == true,
            has_tram = common.field(base, "hasTram") == true,
            structure = structure,
            structure_index = (type(edge_type) == "number" and edge_type) or nil,
        }
    end, errors)

    if not ok then
        return {
            status = "ERROR",
            source_status = "ENGINE_OBSERVED",
            error = tostring(scanned_or_error),
            errors = errors,
        }
    end

    local ordered = {}
    for _, node in pairs(nodes) do ordered[#ordered + 1] = node end
    table.sort(ordered, function(a, b) return a.entity_id < b.entity_id end)

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "EDGE_GRAPH",
        counts = {
            total = #edges,
            edges = #edges,
            nodes = #ordered,
            scanned = scanned_or_error,
            skipped = skipped,
            street_types = #street_types,
        },
        street_types = street_types,
        structures = structures,
        field_probe = probe,
        nodes = ordered,
        edges = edges,
        errors = errors,
    }
end

return M
