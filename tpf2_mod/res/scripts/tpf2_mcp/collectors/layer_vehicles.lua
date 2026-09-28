-- 车辆图层采集器（只读，动态）
--
-- 数据源：TRANSPORT_VEHICLE 组件。
--
-- 读法要点（2026-09-28 修正）：组件视图里没有 position / name / speed，
-- 只有 carrier / config / line / state / stopIndex。所以位置走 BOUNDING_VOLUME
-- 的包围盒中心（rail_network.lua 的 bounds_for()）。
--
-- carrier 在组件视图里是**数字**，而 game.interface.getEntity 的聚合表里是字符串。
-- 数字到名称的映射由 2026-09-28 本存档实测反推（见 CARRIER_NAMES 处的推导），
-- 不是照抄某处的枚举表 —— 猜错的代价是地图上出现颜色错误的车辆。
--
-- 与既有 telemetry 的关系：collectors/operational_telemetry.lua 的 vehicles_live
-- section 也在取车辆位置，但它是**命令驱动**的（外部 Python 服务每 1.5 秒发一条
-- 命令，正是 bridge 邮箱争锁的根源）。本文件走自驱，先独立存在；等抢锁治理完成
-- 后再考虑合并，避免同时改两处。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"
local field_probe = require "tpf2_mcp/collectors/field_probe"

local M = {}

local VEHICLE_LIMIT = 2000

-- carrier 的数字→名称映射放在 common（layer_lines 也要用同一份，避免两处各写一遍漂移）。
-- 推导过程见 common.CARRIER_NAMES 处的注释。
local function carrier_name(value)
    return common.carrier_name(value) or ("CARRIER_" .. tostring(value))
end

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

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

-- 车辆位置。优先 BOUNDING_VOLUME 的包围盒中心；拿不到时退回
-- `game.interface.getEntity(id).position`。
--
-- 🔴 为什么必须有这条回退（2026-09-29 实测）：**28 辆列车全部没有包围盒**，
-- 于是地图上一辆列车都不显示，连带所有铁路线路都显示成"没有车"。
-- 而 TRANSPORT_VEHICLE 的**聚合表视图**里有 position —— 正好补上这个缺口。
local function position_for(entity)
    local center = bounds_for(entity)
    if center ~= nil then return center, "bounds" end
    local ok, view = pcall(function()
        return game.interface.getEntity(common.entity_id(entity))
    end)
    if ok and view ~= nil then
        local position = vec(common.field(view, "position"))
        if position ~= nil then return position, "entity" end
    end
    return nil, nil
end

local function number_or_nil(value)
    if type(value) == "number" then return value end
    return nil
end

function M.collect()
    local errors = {}
    local points = {}
    local by_carrier = {}
    local by_carrier_raw = {}
    local by_source = {}
    local skipped = 0
    local no_bounds = 0
    local truncated = false
    local probe = nil
    local vehicle_missing = false

    local ok, scanned_or_error = common.safe_for_each_entity("TRANSPORT_VEHICLE", function(entity)
        if #points >= VEHICLE_LIMIT then truncated = true return end
        local vehicle = component_access.get(entity, "TRANSPORT_VEHICLE")
        if vehicle == nil then
            skipped = skipped + 1
            if not vehicle_missing then
                vehicle_missing = true
                errors[#errors + 1] = { component = "TRANSPORT_VEHICLE",
                                        note = "unavailable; further occurrences only counted in skipped" }
            end
            return
        end
        if probe == nil then
            probe = { vehicle = field_probe.describe(vehicle) }
        end
        local raw_carrier = common.field(vehicle, "carrier")
        local raw_key = tostring(raw_carrier)
        by_carrier_raw[raw_key] = (by_carrier_raw[raw_key] or 0) + 1

        local center, source = position_for(entity)
        if center == nil then
            no_bounds = no_bounds + 1
            return
        end
        by_source[source] = (by_source[source] or 0) + 1
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
        by_position_source = by_source,
        field_probe = probe,
        points = points,
        errors = errors,
    }
end

return M
