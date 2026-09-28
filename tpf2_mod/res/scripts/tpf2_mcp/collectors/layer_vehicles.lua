-- 车辆图层采集器（只读，动态）
--
-- 数据源：TRANSPORT_VEHICLE 组件。
--
-- 读法要点（2026-09-28 修正）：组件视图里没有 position / name / speed，
-- 只有 carrier / config / line / state / stopIndex。所以位置走 BOUNDING_VOLUME
-- 的包围盒中心（rail_network.lua 的 bounds_for()）。
--
-- carrier 在组件视图里是**数字**，而 game.interface.getEntity 的聚合表里是字符串。
-- 数字到名称的映射按实测对照（VEHICLE_DEPOT carrier=0 对应"汽车车场"= ROAD；
-- TRANSPORT_VEHICLE carrier=1 的聚合表视图是 RAIL）。映射若不对，从产物里的
-- by_carrier_raw 能直接看出真实取值分布。
--
-- 与既有 telemetry 的关系：collectors/operational_telemetry.lua 的 vehicles_live
-- section 也在取车辆位置，但它是**命令驱动**的（外部 Python 服务每 1.5 秒发一条
-- 命令，正是 bridge 邮箱争锁的根源）。本文件走自驱，先独立存在；等抢锁治理完成
-- 后再考虑合并，避免同时改两处。

local common = require "tpf2_mcp/collectors/common"
local field_probe = require "tpf2_mcp/collectors/field_probe"

local M = {}

local VEHICLE_LIMIT = 2000

local CARRIER_NAMES = { [0] = "ROAD", [1] = "RAIL", [2] = "WATER", [3] = "AIR" }

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

local function bounds_for(entity, errors)
    local volume = common.safe_get_component(entity, "BOUNDING_VOLUME", errors)
    local bbox = common.field(volume, "bbox")
    local minimum = vec(common.field(bbox, "min")) or vec(common.field(bbox, "bbMin"))
    local maximum = vec(common.field(bbox, "max")) or vec(common.field(bbox, "bbMax"))
    if not minimum or not maximum then return nil, nil end
    return {
        x = (minimum.x + maximum.x) / 2,
        y = (minimum.y + maximum.y) / 2,
        z = (minimum.z + maximum.z) / 2,
    }, { min = minimum, max = maximum }
end

local function number_or_nil(value)
    if type(value) == "number" then return value end
    return nil
end

local function carrier_name(value)
    if type(value) == "number" then return CARRIER_NAMES[value] or ("CARRIER_" .. tostring(value)) end
    if type(value) == "string" and value ~= "" then return value end
    return "UNKNOWN"
end

function M.collect()
    local errors = {}
    local points = {}
    local by_carrier = {}
    local by_carrier_raw = {}
    local skipped = 0
    local no_bounds = 0
    local truncated = false
    local probe = nil

    local ok, scanned_or_error = common.safe_for_each_entity("TRANSPORT_VEHICLE", function(entity)
        if #points >= VEHICLE_LIMIT then truncated = true return end
        local vehicle = common.safe_get_component(entity, "TRANSPORT_VEHICLE", errors)
        if vehicle == nil then
            skipped = skipped + 1
            return
        end
        if probe == nil then
            probe = { vehicle = field_probe.describe(vehicle) }
        end
        local raw_carrier = common.field(vehicle, "carrier")
        if type(raw_carrier) == "number" then
            by_carrier_raw[tostring(raw_carrier)] = (by_carrier_raw[tostring(raw_carrier)] or 0) + 1
        else
            local key = tostring(raw_carrier)
            by_carrier_raw[key] = (by_carrier_raw[key] or 0) + 1
        end

        local center = bounds_for(entity, errors)
        if center == nil then
            no_bounds = no_bounds + 1
            return
        end
        local name = carrier_name(raw_carrier)
        by_carrier[name] = (by_carrier[name] or 0) + 1

        points[#points + 1] = {
            entity_id = common.entity_id(entity),
            position = center,
            carrier = name,
            carrier_raw = raw_carrier,
            line = number_or_nil(common.field(vehicle, "line")),
            state = number_or_nil(common.field(vehicle, "state")),
            stop_index = number_or_nil(common.field(vehicle, "stopIndex")),
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
            no_bounds = no_bounds,
        },
        by_carrier = by_carrier,
        by_carrier_raw = by_carrier_raw,
        field_probe = probe,
        points = points,
        errors = errors,
    }
end

return M
