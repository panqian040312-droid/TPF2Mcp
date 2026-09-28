-- 组件字段可用性诊断（只读）
--
-- 为什么需要它：`api.engine.getComponent(entity, "X")` 拿到的组件视图，字段名与
-- `game.interface.getEntity(id)` 的聚合表**完全不同**。2026-09-28 第一次跑图层
-- 采集时，我拿聚合表的字段名（node0pos / position / streetType）去读组件视图，
-- 结果每个实体都在读字段那步失败、全部被跳过（10444 个边全 skip，文件只有 293 B）。
--
-- 教训：组件视图的字段只能**试读**确认。组件的 metatable.__index 是函数
-- （instance_meta.index_is_function = true），没法枚举键，所以只能拿候选名单挨个试。
--
-- 本模块把"试读一批候选名"的结果打包进图层文件，随采集一起输出。这样即使读法
-- 又猜错了，也能从产物里直接看出正确字段名，不必再改一次 Lua 重启一次游戏
-- （TPF2 只在启动时读 mod Lua，每次改代码都要重启，代价很高）。

local common = require "tpf2_mcp/collectors/common"

local M = {}

-- 候选字段名 = rail_network.lua 已实证可用的 + world_probe 的通用名单 + 常见命名猜测
local CANDIDATES = {
    -- rail_network.lua 实证：BASE_EDGE / BASE_NODE / BOUNDING_VOLUME / LINE / STATION 上可读
    "node0", "node1", "tangent0", "tangent1", "trackType", "catenary",
    "position", "pos", "bbox", "min", "max", "bbMin", "bbMax",
    "terminals", "stops", "name", "depot", "stopsCount", "vehicleNodeId",
    -- 交通网络
    "track", "streetType", "hasBus", "hasTram", "typeIndex", "laneConfig", "oneWay",
    "speedLimit", "length", "width", "index", "edge", "edges", "nodes", "segment",
    -- 车辆
    "carrier", "line", "state", "stopIndex", "config", "capacities", "allCapacities",
    "cargoLoad", "cargoCapacity", "vehicles", "speed", "curSpeed", "loadingSpeed",
    -- 建筑 / 产业 / 城镇
    "level", "stockList", "itemsConsumed", "itemsProduced", "itemsShipped", "itemsTransported",
    "itemsWaiting", "personCapacity", "height", "depth", "parcels", "town", "townBuildings",
    "simBuildings", "stations", "fileName", "upgradeProgress", "production", "level2",
    -- 车站 / 线路
    "stationGroup", "cargo", "carriers", "cargoWaiting", "itemsLoaded", "itemsUnloaded",
    "waitingTime", "frequency", "rate", "waiting", "onboard",
    -- 其它常见
    "id", "type", "value", "size", "direction", "rotation", "dir", "transf",
    "station", "stationIndex", "townId", "group", "parent", "stateTime",
}

-- 试读一个组件对象，返回命中的字段（只保留能读出来、且不是 nil 的）。
-- 每个键都用 common.field 包了 pcall，读不出来就跳过，不会打断采集。
function M.describe(value, limit)
    local out = { value_type = type(value) }
    if value == nil then return out end
    local fields = {}
    local count = 0
    for _, key in ipairs(CANDIDATES) do
        if count >= (limit or 30) then break end
        local read = common.field(value, key)
        if read ~= nil then
            local kind = type(read)
            local entry = { type = kind }
            if kind == "number" or kind == "string" or kind == "boolean" then
                entry.value = read
            end
            local length = common.array_count(read)
            if length ~= nil then entry.length = length end
            fields[key] = entry
            count = count + 1
        end
    end
    out.field_count = count
    out.fields = fields
    return out
end

return M
