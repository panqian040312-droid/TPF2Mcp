-- 车辆图层采集器（只读，动态）
--
-- 数据源：TRANSPORT_VEHICLE 组件。v4 世界探针（2026-09-28）实测字段：
--   id / name / carrier / position / speed / line / state / stopIndex /
--   depot / capacities / cargoLoad / allCapacities / vehicles
--
-- 关键点：`carrier` 是车种判据 —— RAIL / ROAD / WATER / AIR。
-- 此前所有车在地图上都画成同一种；有了这个字段就能分四色。
--
-- 注意与既有 telemetry 的关系：`collectors/operational_telemetry.lua` 的
-- vehicles_live section 也在取车辆实时位置，但它是**命令驱动**的（外部 Python
-- 服务每 1.5 秒发一条命令，正是 bridge 邮箱争锁的根源）。本文件走自驱，
-- 阶段一先独立存在；等抢锁治理完成后再考虑合并，避免同时改两处。

local common = require "tpf2_mcp/collectors/common"

local M = {}

local VEHICLE_LIMIT = 2000

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

local function number_or_nil(value)
    if type(value) == "number" then return value end
    return nil
end

local function text(value)
    if type(value) == "string" then return value end
    if type(value) == "number" then return tostring(value) end
    return nil
end

function M.collect()
    local errors = {}
    local points = {}
    local by_carrier = {}
    local skipped = 0
    local truncated = false

    local ok, scanned_or_error = common.safe_for_each_entity("TRANSPORT_VEHICLE", function(entity)
        if #points >= VEHICLE_LIMIT then truncated = true return end
        local vehicle = common.safe_get_component(entity, "TRANSPORT_VEHICLE", errors)
        if vehicle == nil then
            skipped = skipped + 1
            return
        end
        local position = vec(common.field(vehicle, "position"))
        if position == nil then
            skipped = skipped + 1
            return
        end
        local carrier = text(common.field(vehicle, "carrier")) or "UNKNOWN"
        by_carrier[carrier] = (by_carrier[carrier] or 0) + 1

        points[#points + 1] = {
            entity_id = common.entity_id(entity),
            position = position,
            name = text(common.field(vehicle, "name")),
            carrier = carrier,
            line = number_or_nil(common.field(vehicle, "line")) or text(common.field(vehicle, "line")),
            state = text(common.field(vehicle, "state")),
            stop_index = number_or_nil(common.field(vehicle, "stopIndex")),
            speed = number_or_nil(common.field(vehicle, "speed")),
            -- 编组节数：列车/船舶/飞机的 vehicles 数组长度
            unit_count = common.array_count(common.field(vehicle, "vehicles")),
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
        truncated = truncated,
        counts = {
            total = #points,
            points = #points,
            scanned = scanned_or_error,
            skipped = skipped,
        },
        by_carrier = by_carrier,
        points = points,
        errors = errors,
    }
end

return M
