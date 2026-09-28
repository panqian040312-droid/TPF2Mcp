-- 产业图层采集器（只读）
--
-- 数据源：SIM_BUILDING 组件。
--
-- 读法要点（2026-09-28 修正）：`SIM_BUILDING` 的**组件视图**里没有 position，
-- 只有 level / stockList。所以位置必须走 BOUNDING_VOLUME 的包围盒中心
-- （rail_network.lua 的 bounds_for() 已在 STATION/TOWN 上验证可用）。
-- 之前直接读 building.position 导致 131 个产业全被跳过。
--
-- 名字同样不在组件视图里；先用 field_probe 把真实字段名探出来再说，
-- 本版先输出位置 / 等级 / 库存关联，名字留空。

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

-- 照 rail_network.lua 的 bounds_for()：用 BOUNDING_VOLUME 的包围盒中心当位置。
-- 读不到就是 nil，由调用方的 no_bounds 计数报告规模（不往 errors 里堆）。
local function bounds_for(entity)
    local volume = component_access.get(entity, "BOUNDING_VOLUME")
    local bbox = common.field(volume, "bbox")
    local minimum = vec(common.field(bbox, "min")) or vec(common.field(bbox, "bbMin"))
    local maximum = vec(common.field(bbox, "max")) or vec(common.field(bbox, "bbMax"))
    if not minimum or not maximum then return nil end
    return {
        x = (minimum.x + maximum.x) / 2,
        y = (minimum.y + maximum.y) / 2,
        z = (minimum.z + maximum.z) / 2,
    }
end

local function number_or_nil(value)
    if type(value) == "number" then return value end
    return nil
end

function M.collect()
    local errors = {}
    local points = {}
    local skipped = 0
    local no_bounds = 0
    local probe = nil
    local building_missing = false

    local ok, scanned_or_error = common.safe_for_each_entity("SIM_BUILDING", function(entity)
        local building = component_access.get(entity, "SIM_BUILDING")
        if building == nil then
            skipped = skipped + 1
            if not building_missing then
                building_missing = true
                errors[#errors + 1] = { component = "SIM_BUILDING",
                                        note = "unavailable; further occurrences only counted in skipped" }
            end
            return
        end
        if probe == nil then
            probe = { building = field_probe.describe(building) }
        end
        local center = bounds_for(entity)
        if center == nil then
            no_bounds = no_bounds + 1
            return
        end
        points[#points + 1] = {
            entity_id = common.entity_id(entity),
            position = center,
            level = number_or_nil(common.field(building, "level")),
            upgrade_progress = number_or_nil(common.field(building, "upgradeProgress")),
            stock_list = number_or_nil(common.field(building, "stockList")),
            consumed_count = common.array_count(common.field(building, "itemsConsumed")),
            produced_count = common.array_count(common.field(building, "itemsProduced")),
            shipped_count = common.array_count(common.field(building, "itemsShipped")),
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

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "POINT",
        counts = {
            total = #points,
            points = #points,
            scanned = scanned_or_error,
            skipped = skipped,
            no_bounds = no_bounds,
        },
        field_probe = probe,
        points = points,
        errors = errors,
    }
end

return M
