-- 全方式线路图层（只读，静态）
--
-- 与 collectors/rail_network.lua 的分工：那个只采**纯铁路**线路 —— 它靠 BASE_EDGE_TRACK
-- 的节点给站台定位，非铁路站台的节点不在那份表里，于是整条线被判成"非铁路"丢掉。
-- 所以 140 条线里只有 16 条进了铁路图。本采集器**不依赖铁路节点**：站台位置直接走
-- 它自己的 vehicleNodeId → BASE_NODE，因此公路（5262 条）、水运、航空线一并采到。
--
-- 每条线带两个分类维度，正好对应地图上"单独或叠加观看"的需求：
--   carrier（种类）RAIL / ROAD / WATER / AIR
--   cargo  （职能）PASSENGER / FREIGHT / MIXED
--
-- carrier 怎么判：**优先看跑在这条线上的车辆**（每辆车都有 carrier）；这条线还没配车时，
-- 退回看它停靠的站台是什么类型（CONSTRUCTION.fileName 的前缀）。两者都判不出就 UNKNOWN ——
-- 不猜，宁可地图上显示"未分类"也不要画错。
--
-- cargo 怎么判：看这条线停靠的站台是不是货运站台（STATION.cargo）。
--   全是货运站台 → FREIGHT；全是客运站台 → PASSENGER；两者都有 → MIXED。
--   一个站台都查不到 → UNKNOWN。
--   （TPF2 里线路本身不标客货，是站台分的，所以只能这么聚合。）

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

local LINE_LIMIT = 400
local STOP_LIMIT = 200       -- 单条线最多记多少个停靠点（防止环线把 payload 撑爆）

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

local function bounds_center(entity)
    local volume = component_access.get(entity, "BOUNDING_VOLUME")
    local bbox = common.field(volume, "bbox")
    local minimum = vec(common.field(bbox, "min")) or vec(common.field(bbox, "bbMin"))
    local maximum = vec(common.field(bbox, "max")) or vec(common.field(bbox, "bbMax"))
    if not minimum or not maximum then return nil end
    return { x = (minimum.x + maximum.x) / 2, y = (minimum.y + maximum.y) / 2,
             z = (minimum.z + maximum.z) / 2 }
end

-- 站台位置。terminal.vehicleNodeId.entity 是一个 BASE_NODE —— 铁路、公路、水运、航空
-- 站台都有这个节点，所以这里能通吃；rail_network.lua 之所以只拿到铁路站台，是因为它
-- 把这个节点拿去查"铁路节点表"了，查不到就丢。
local function terminal_position(terminal)
    local node_entity = common.field(common.field(terminal, "vehicleNodeId"), "entity")
    if node_entity == nil then return nil end
    local node = component_access.get(node_entity, "BASE_NODE")
    return vec(common.field(node, "position")) or vec(common.field(node, "pos"))
end

-- 站台类型 → 运输方式。构造文件名形如 station/rail/modular_station/modular_station.con。
-- 认不出的文件名会被原样记进 diagnostics.construction_files，部署后一眼就能看出真实命名规则，
-- 不必再来一轮探针。
local FILE_HINTS = {
    { "rail", "RAIL" }, { "train", "RAIL" }, { "track", "RAIL" },
    { "street", "ROAD" }, { "road", "ROAD" }, { "bus", "ROAD" }, { "tram", "ROAD" },
    { "ship", "WATER" }, { "water", "WATER" }, { "boat", "WATER" }, { "harbour", "WATER" }, { "harbor", "WATER" },
    { "air", "AIR" }, { "plane", "AIR" }, { "runway", "AIR" }, { "airport", "AIR" },
}

local function carrier_from_file(file_name)
    if type(file_name) ~= "string" then return nil end
    local lower = string.lower(file_name)
    for index = 1, #FILE_HINTS do
        if string.find(lower, FILE_HINTS[index][1], 1, true) then return FILE_HINTS[index][2] end
    end
    return nil
end

local function count_up(tally, key)
    if key == nil then return end
    tally[key] = (tally[key] or 0) + 1
end

function M.collect()
    local errors = {}
    local diagnostics = { construction_files = {}, station_groups = 0, vehicles = 0,
                          lines_seen = 0, lines_kept = 0 }

    -- ① 车站：有哪些站台、是不是货运站台、站台类型是什么
    local station_to_construction = nil
    local map_ok, map_value = pcall(function()
        return api.engine.system.streetConnectorSystem.getStation2ConstructionMap()
    end)
    if map_ok then station_to_construction = map_value end

    -- group_id → { cargo, carrier }（carrier 是该站台类型的多数派）
    local station_kind = {}
    common.safe_for_each_entity("STATION_GROUP", function(entity)
        local group_id = common.entity_id(entity)
        local group = component_access.get(entity, "STATION_GROUP")
        if group_id == nil or group == nil then return end
        diagnostics.station_groups = diagnostics.station_groups + 1
        local cargo_any = false
        local kind_tally = {}
        for _, station_entity in ipairs(common.sequence_values(common.field(group, "stations"))) do
            local station = component_access.get(station_entity, "STATION")
            if station ~= nil then
                if common.field(station, "cargo") == true then cargo_any = true end
                if station_to_construction ~= nil then
                    local raw = common.field(station_to_construction, station_entity)
                        or common.field(station_to_construction, common.entity_id(station_entity))
                    local construction = raw ~= nil and component_access.get(raw, "CONSTRUCTION") or nil
                    local file_name = common.field(construction, "fileName")
                    if type(file_name) == "string" then
                        count_up(diagnostics.construction_files, file_name)
                        count_up(kind_tally, carrier_from_file(file_name))
                    end
                end
            end
        end
        station_kind[group_id] = { cargo = cargo_any, carrier = common.majority_key(kind_tally) }
    end, {})

    -- ② 车辆 → 这条线算什么种类
    local line_vehicles = {}   -- line_id → { count, tally }
    common.safe_for_each_entity("TRANSPORT_VEHICLE", function(entity)
        local vehicle = component_access.get(entity, "TRANSPORT_VEHICLE")
        if vehicle == nil then return end
        diagnostics.vehicles = diagnostics.vehicles + 1
        local line_id = common.entity_id(common.field(vehicle, "line"))
        local carrier = common.carrier_name(common.field(vehicle, "carrier"))
        if line_id == nil or carrier == nil then return end
        local entry = line_vehicles[line_id]
        if entry == nil then entry = { count = 0, tally = {} }; line_vehicles[line_id] = entry end
        entry.count = entry.count + 1
        count_up(entry.tally, carrier)
    end, {})

    -- ③ 线路：停靠点位置 + 两个分类维度
    local terminal_cache = {}   -- "group:station:terminal" → position
    local lines = {}
    local carrier_tally, cargo_tally = {}, {}

    common.safe_for_each_entity("LINE", function(entity)
        local line_id = common.entity_id(entity)
        local component = component_access.get(entity, "LINE")
        if line_id == nil or component == nil then return end
        diagnostics.lines_seen = diagnostics.lines_seen + 1
        if #lines >= LINE_LIMIT then return end

        -- 线路颜色 = **游戏里那条线的真实颜色**，不是我们自己分配的。
        -- 出处（官方 API）：通用实体组件 `Color`（"Specifies the color of an entity"，字段 `color: Vec3f`，
        -- 组件枚举里是 `COLOR = 64`）；`Line` 类自身也带 `color: Vec3f`。
        -- 两条路都试，哪条通就用哪条；都拿不到留 nil —— 前端退回自己的调色板，**绝不猜颜色**。
        local line_color = vec(common.field(component, "color"))
        if line_color == nil then
            line_color = vec(common.field(component_access.get(entity, "COLOR"), "color"))
        end

        local points, stops_out, cargo_true, cargo_false = {}, {}, 0, 0
        local kind_tally = {}
        for _, stop in ipairs(common.sequence_values(common.field(component, "stops"))) do
            local group_entity = common.field(stop, "stationGroup")
            local group_id = common.entity_id(group_entity)
            local station_index = common.field(stop, "station") or 0
            local terminal_index = common.field(stop, "terminal") or 0
            if type(station_index) ~= "number" then station_index = 0 end
            if type(terminal_index) ~= "number" then terminal_index = 0 end

            local key = tostring(group_id) .. ":" .. tostring(station_index) .. ":" .. tostring(terminal_index)
            local position = terminal_cache[key]
            if position == nil then
                local group = component_access.get(group_entity, "STATION_GROUP")
                local stations = common.sequence_values(common.field(group, "stations"))
                local station = component_access.get(stations[station_index + 1], "STATION")
                local terminals = common.sequence_values(common.field(station, "terminals"))
                position = terminal_position(terminals[terminal_index + 1])
                -- 站台级定位失败时**回退到车站包围盒中心**。
                -- 实测（2026-09-29）：站台自己的 vehicleNodeId → BASE_NODE 这条路
                -- 只对铁路站台有效，公路/水运/航空站台拿不到节点，于是 140 条线只留下 16 条。
                -- 而 BOUNDING_VOLUME 这条路径在 station 图层里对全部 328 个车站都成功。
                if position == nil then
                    position = bounds_center(group_entity)
                    diagnostics.terminal_fallback = (diagnostics.terminal_fallback or 0) + 1
                end
                position = position or false
                terminal_cache[key] = position
            end
            local pos_ok = position ~= false and position ~= nil
            if pos_ok and #points < STOP_LIMIT then
                points[#points + 1] = position
            end

            -- ★ 站点序列（严格对齐，2026-09-30 新增）：坐标有没有取到都按**真实下标**记一条。
            -- 为什么必须另开一份：上面的 points 会**跳过**取不到坐标的站，下标因此错位；
            -- 而 cargo 侧的 lineStop0 / lineStop1 是 Line.stops 的真实下标 —— 拿错位的 points
            -- 去索引，会把货画到隔壁站上去。所以这里 index 就是真实下标（0 起）。
            -- （0 起还是 1 起：本文件里 Stop.station 是按 `stations[station_index + 1]` 用的，
            --   即 0 起；lineStopN 同源的可能性大，部署后用实测取值范围再确认一次。）
            if #stops_out < STOP_LIMIT then
                stops_out[#stops_out + 1] = {
                    index = #stops_out,
                    group_id = group_id,
                    station_index = station_index,
                    terminal_index = terminal_index,
                    x = pos_ok and position.x or nil,
                    y = pos_ok and position.y or nil,
                    z = pos_ok and position.z or nil,
                }
            end

            local kind = station_kind[group_id]
            if kind ~= nil then
                if kind.cargo then cargo_true = cargo_true + 1 else cargo_false = cargo_false + 1 end
                count_up(kind_tally, kind.carrier)
            end
        end
        if #points < 2 then return end

        local entry = line_vehicles[line_id]
        local carrier = (entry ~= nil and common.majority_key(entry.tally)) or common.majority_key(kind_tally) or "UNKNOWN"
        local cargo
        if cargo_true > 0 and cargo_false > 0 then cargo = "MIXED"
        elseif cargo_true > 0 then cargo = "FREIGHT"
        elseif cargo_false > 0 then cargo = "PASSENGER"
        else cargo = "UNKNOWN" end

        lines[#lines + 1] = {
            entity_id = line_id,
            name = common.name_from_component(component_access.get(entity, "NAME"))
                or ("Line " .. tostring(line_id)),
            carrier = carrier,
            cargo = cargo,
            color = line_color ~= nil and { r = line_color.x, g = line_color.y, b = line_color.z } or nil,
            vehicle_count = entry ~= nil and entry.count or 0,
            stop_count = #points,
            points = points,
            -- 站点序列：真实下标对齐 + 带车站 id（group_id / station_index / terminal_index）。
            -- ⚠️ points 只有坐标且会跳站，**不要**拿它去索引 cargo 侧的 lineStopN，用 stops。
            stop_total = #stops_out,
            stops = stops_out,
        }
        diagnostics.lines_kept = diagnostics.lines_kept + 1
        count_up(carrier_tally, carrier)
        count_up(cargo_tally, cargo)
    end, {})

    table.sort(lines, function(a, b) return a.entity_id < b.entity_id end)

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "ROUTE",
        counts = {
            total = #lines,
            lines = #lines,
            stops = diagnostics.lines_seen,
            station_groups = diagnostics.station_groups,
            vehicles = diagnostics.vehicles,
            lines_seen = diagnostics.lines_seen,
        },
        by_carrier = carrier_tally,
        by_cargo = cargo_tally,
        diagnostics = diagnostics,
        lines = lines,
        errors = errors,
    }
end

return M
