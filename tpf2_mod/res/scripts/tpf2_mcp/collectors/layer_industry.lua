-- 产业图层采集器（只读）
--
-- 数据源：SIM_BUILDING 组件。v4 世界探针（2026-09-28）实测字段：
--   id / position / name / level / stockList / itemsConsumed / itemsProduced /
--   itemsShipped / itemsConsumedVehicleUsed / upgradeProgress / type
-- 本存档实测只有 131 个，可一次采完，无需分帧。
--
-- 数量很小，所以这里连 items* 那几个表的长度也一并带上，供前端判断"有没有在出货"。

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

local function text(value)
    if type(value) == "string" then return value end
    if type(value) == "number" then return tostring(value) end
    return nil
end

local function number_or_nil(value)
    if type(value) == "number" then return value end
    return nil
end

function M.collect()
    local errors = {}
    local points = {}
    local skipped = 0

    local ok, scanned_or_error = common.safe_for_each_entity("SIM_BUILDING", function(entity)
        local building = common.safe_get_component(entity, "SIM_BUILDING", errors)
        if building == nil then
            skipped = skipped + 1
            return
        end
        local position = vec(common.field(building, "position"))
        if position == nil then
            skipped = skipped + 1
            return
        end
        points[#points + 1] = {
            entity_id = common.entity_id(entity),
            position = position,
            name = text(common.field(building, "name")),
            level = number_or_nil(common.field(building, "level")),
            upgrade_progress = number_or_nil(common.field(building, "upgradeProgress")),
            stock_list = text(common.field(building, "stockList")),
            -- 只是数组长度，不展开内容（内容是"按货物种类"的表，等确认真实结构再说）
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
        },
        points = points,
        errors = errors,
    }
end

return M
