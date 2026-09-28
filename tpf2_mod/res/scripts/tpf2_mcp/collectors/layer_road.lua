-- 公路网图层采集器（只读）
--
-- 数据源：BASE_EDGE 组件。v4 世界探针（2026-09-28）实测确认：
--   BASE_EDGE 10444 = BASE_EDGE_TRACK 5182 (track=true) + BASE_EDGE_STREET 5262 (track=false)
--   两类字段完全相同：id / node0 / node1 / node0pos / node1pos / node0tangent /
--   node1tangent / track / streetType / hasBus / hasTram
--   → 公路不需要另写一套几何读法，按 track 分流即可。
--
-- 几何取自 BASE_EDGE 自身的 node0pos / node1pos，不必再遍历 BASE_NODE 取坐标；
-- 但仍生成去重后的 nodes 表，好让前端复用铁路那套 edgePath（Hermite 切线）画法。

local common = require "tpf2_mcp/collectors/common"

local M = {}

local function vec(value)
    if value == nil then return nil end
    local position = {
        x = common.field(value, "x"),
        y = common.field(value, "y"),
        z = common.field(value, "z"),
    }
    if position.x == nil or position.y == nil then return nil end
    if position.z == nil then position.z = 0 end
    return position
end

function M.collect()
    local errors = {}
    local edges = {}
    local nodes = {}
    local street_types = {}
    local skipped = 0

    local ok, scanned_or_error = common.safe_for_each_entity("BASE_EDGE", function(entity)
        local base = common.safe_get_component(entity, "BASE_EDGE", errors)
        if base == nil then
            skipped = skipped + 1
            return
        end
        -- 只要公路：track == true 的是铁路，跳过
        if common.field(base, "track") == true then return end

        local raw0 = common.field(base, "node0")
        local raw1 = common.field(base, "node1")
        local position0 = vec(common.field(base, "node0pos"))
        local position1 = vec(common.field(base, "node1pos"))
        if raw0 == nil or raw1 == nil or position0 == nil or position1 == nil then
            skipped = skipped + 1
            return
        end
        local id0 = common.entity_id(raw0)
        local id1 = common.entity_id(raw1)
        if nodes[id0] == nil then nodes[id0] = { entity_id = id0, position = position0 } end
        if nodes[id1] == nil then nodes[id1] = { entity_id = id1, position = position1 } end

        local raw_street_type = common.field(base, "streetType")
        local street_type = nil
        if type(raw_street_type) == "string" and raw_street_type ~= "" then
            street_type = raw_street_type
            street_types[street_type] = (street_types[street_type] or 0) + 1
        end

        edges[#edges + 1] = {
            entity_id = common.entity_id(entity),
            node0 = id0,
            node1 = id1,
            tangent0 = vec(common.field(base, "node0tangent")),
            tangent1 = vec(common.field(base, "node1tangent")),
            street_type = street_type,
            has_bus = common.field(base, "hasBus") == true,
            has_tram = common.field(base, "hasTram") == true,
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

    local sorted_nodes = {}
    for _, node in pairs(nodes) do sorted_nodes[#sorted_nodes + 1] = node end

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "EDGE_GRAPH",
        counts = {
            total = #edges,
            edges = #edges,
            nodes = #sorted_nodes,
            scanned = scanned_or_error,
            skipped = skipped,
            street_types = #street_types,
        },
        street_types = street_types,
        nodes = sorted_nodes,
        edges = edges,
        errors = errors,
    }
end

return M
