-- 车站互通站群图层（只读，静态）
--
-- 数据源：`api.engine.system.catchmentAreaSystem.getStation2stationsAndDistancesMap()`
-- 这是引擎自己的"车站辐射"表 —— 车站 → 与之**步行可互通**的车站及距离。
-- TPF2 里乘客能在辐射区重叠的车站之间换乘，所以这张表就是"互通"的权威定义，
-- 不需要（也不应该）自己按距离阈值猜。
--
-- 输出两样东西：
--   clusters —— 连通分量。互通关系是传递的（A↔B、B↔C ⇒ A、B、C 连成一片），
--               所以要用并查集把所有互相连通的站归成一个站群。用户在图上看到的
--               "连成一片"就是这个。
--   stations —— 每个车站的坐标 + 所属站群 id + 候车人数，供前端标记与聚合客流。
--
-- ⚠ 这张表的结构没有文档，probing 只能确认方法存在。所以本采集器**自带结构诊断**
--   （catchment_probe）：把 map 的类型、可枚举性、前几个键值的形状原样写进产物。
--   万一解析方式不对，从产物一眼就能看出真实结构，不必再重启一次游戏探一轮。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

local MAX_LINKS = 4000          -- 互通边上限（防止结构异常时把 payload 撑爆）
local MAX_STATIONS = 1200
local PROBE_KEYS = 4

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

-- 并查集：互通是传递关系，站群就是连通分量
local function make_union_find()
    local parent = {}
    local function find(value)
        local root = value
        while parent[root] ~= nil and parent[root] ~= root do root = parent[root] end
        -- 路径压缩
        local walk = value
        while parent[walk] ~= nil and parent[walk] ~= walk do
            local next_hop = parent[walk]
            parent[walk] = root
            walk = next_hop
        end
        return root
    end
    return {
        add = function(value) if parent[value] == nil then parent[value] = value end end,
        find = find,
        union = function(a, b)
            local root_a, root_b = find(a), find(b)
            if root_a ~= root_b then parent[root_a] = root_b end
        end,
    }
end

-- 从一行键值里抽出"另一个车站"和"距离"。
-- value 可能是：
--   * 数组：{ {station=..., distance=...}, ... }
--   * 映射：{ [otherStation] = distance }
--   * 数组：{ {otherStation, distance}, ... }（裸数组对）
-- 三种都试，认不出就返回 nil（不猜）。
local function parse_link_entry(key, value)
    if value == nil then return nil end
    local station = common.field(value, "station") or common.field(value, "target")
        or common.field(value, "other") or common.field(value, "to")
        or common.field(value, "entity") or common.field(value, "stationId")
    local distance = common.field(value, "distance") or common.field(value, "dist")
        or common.field(value, "length") or common.field(value, "cost")
    if station ~= nil then
        return common.entity_id(station), (type(distance) == "number" and distance or nil)
    end
    -- 裸数组对 {otherStation, distance}
    local first, second = common.field(value, 1), common.field(value, 2)
    if first ~= nil and type(second) == "number" then
        return common.entity_id(first), second
    end
    return nil
end

local function describe(value, depth)
    if value == nil then return "nil" end
    local kind = type(value)
    if kind == "number" or kind == "string" or kind == "boolean" then return kind .. "=" .. tostring(value) end
    if depth <= 0 then return kind end
    local count = common.array_count(value)
    return kind .. (count ~= nil and ("[" .. tostring(count) .. "]") or "")
end

function M.collect()
    local errors = {}
    local diagnostics = { catchment_probe = {}, stations_seen = 0, links = 0, clusters = 0 }

    -- ① 车站位置（站台自己的 vehicleNodeId → BASE_NODE，四种站台通用）
    local stations = {}
    local station_entity_by_id = {}
    common.safe_for_each_entity("STATION_GROUP", function(entity)
        local group_id = common.entity_id(entity)
        local group = component_access.get(entity, "STATION_GROUP")
        if group_id == nil or group == nil then return end
        if diagnostics.stations_seen >= MAX_STATIONS then return end
        diagnostics.stations_seen = diagnostics.stations_seen + 1

        local name = common.name_from_component(component_access.get(entity, "NAME"))
        local center = bounds_center(entity)
        -- 没拿到包围盒就用第一个站台的位置兜底
        if center == nil then
            for _, station_entity in ipairs(common.sequence_values(common.field(group, "stations"))) do
                local station = component_access.get(station_entity, "STATION")
                for _, terminal in ipairs(common.sequence_values(common.field(station, "terminals"))) do
                    local node_entity = common.field(common.field(terminal, "vehicleNodeId"), "entity")
                    local node = node_entity ~= nil and component_access.get(node_entity, "BASE_NODE") or nil
                    center = vec(common.field(node, "position")) or vec(common.field(node, "pos"))
                    if center ~= nil then break end
                end
                if center ~= nil then break end
            end
        end
        local cargo_any = false
        for _, station_entity in ipairs(common.sequence_values(common.field(group, "stations"))) do
            local station = component_access.get(station_entity, "STATION")
            if station ~= nil and common.field(station, "cargo") == true then cargo_any = true break end
        end
        stations[group_id] = {
            entity_id = group_id,
            name = name or ("Station " .. tostring(group_id)),
            position = center,
            cargo = cargo_any,
        }
        station_entity_by_id[group_id] = entity
    end, {})

    -- ② 互通表
    local map_ok, map_or_error = pcall(function()
        return api.engine.system.catchmentAreaSystem.getStation2stationsAndDistancesMap()
    end)
    if not map_ok then
        return {
            status = "ERROR",
            source_status = "ENGINE_OBSERVED",
            geometry_kind = "STATION_CLUSTER",
            error = "catchmentAreaSystem unavailable: " .. tostring(map_or_error),
            errors = { { component = "catchmentAreaSystem", error = tostring(map_or_error) } },
        }
    end
    local catchment = map_or_error

    diagnostics.map_type = type(catchment)
    diagnostics.map_length = common.array_count(catchment)
    local probe_samples = {}

    -- 把顶层键值都收集出来（同时兼容 table 与 userdata）
    local top_entries = {}
    local pairs_ok, pairs_error = pcall(function()
        for key, value in pairs(catchment) do
            top_entries[#top_entries + 1] = { key = key, value = value }
            if #top_entries >= MAX_STATIONS then break end
        end
    end)
    diagnostics.pairs_ok = pairs_ok
    if not pairs_ok then diagnostics.pairs_error = tostring(pairs_error) end

    -- pairs 不通就试长度 + 整数索引
    if #top_entries == 0 and diagnostics.map_length ~= nil and diagnostics.map_length > 0 then
        for index = 0, math.min(diagnostics.map_length, MAX_STATIONS) - 1 do
            local value = common.field(catchment, index) or common.field(catchment, index + 1)
            if value ~= nil then top_entries[#top_entries + 1] = { key = index, value = value } end
        end
        diagnostics.indexed_fallback = #top_entries
    end

    local union_find = make_union_find()
    local links = {}
    for entry_index = 1, #top_entries do
        local key = top_entries[entry_index].key
        local value = top_entries[entry_index].value
        local from_id = common.entity_id(key) or common.entity_id(common.field(key, "entity"))
        if entry_index <= PROBE_KEYS then
            local inner_count = common.array_count(value)
            local sample_keys = {}
            local inner_ok = pcall(function()
                local n = 0
                for inner_key, inner_value in pairs(value) do
                    sample_keys[#sample_keys + 1] = tostring(inner_key) .. " → " .. describe(inner_value, 1)
                    n = n + 1
                    if n >= 3 then break end
                end
            end)
            probe_samples[#probe_samples + 1] = {
                key = describe(key, 0),
                value = describe(value, 1),
                inner_count = inner_count,
                inner_keys = sample_keys,
                inner_pairs_ok = inner_ok,
            }
        end
        if from_id ~= nil then
            union_find.add(from_id)
            -- 🔴 解析顺序很关键（2026-09-29 真实产物踩过）：
            -- 实测结构是 map[station][otherStation] = distance（诊断里的 inner_keys 证实：
            -- "92901 → number=0"、"112895 → number=0.257"…）。
            -- 必须**先按"目标集合"解析**，集合为空才退回"value 本身是一个目标"。
            -- 反过来先试 direct 会中招：这种 userdata 的整数索引恰好取值（第 1 个元素），
            -- 于是被误判成"单个目标"，整个集合被跳过 —— 结果就是 1825 条边却 0 个连通分量。
            local inner = {}
            pcall(function()
                for inner_key, inner_value in pairs(value) do
                    inner[#inner + 1] = { key = inner_key, value = inner_value }
                    if #inner >= MAX_STATIONS then break end
                end
            end)
            if #inner == 0 then
                local count = common.array_count(value)
                if count ~= nil and count > 0 then
                    for index = 0, math.min(count, MAX_STATIONS) - 1 do
                        local item = common.field(value, index) or common.field(value, index + 1)
                        if item ~= nil then inner[#inner + 1] = { key = index, value = item } end
                    end
                end
            end
            if #inner == 0 then
                local direct_to, direct_distance = parse_link_entry(from_id, value)
                if direct_to ~= nil then
                    union_find.add(direct_to)
                    union_find.union(from_id, direct_to)
                    if #links < MAX_LINKS then
                        links[#links + 1] = { a = from_id, b = direct_to, distance = direct_distance }
                        diagnostics.links = diagnostics.links + 1
                    end
                end
            else
                for inner_index = 1, #inner do
                    local to_id, distance = parse_link_entry(inner[inner_index].key, inner[inner_index].value)
                    -- 映射形式：键就是目标站，值是距离
                    if to_id == nil and type(inner[inner_index].value) == "number" then
                        to_id = common.entity_id(inner[inner_index].key)
                        distance = inner[inner_index].value
                    end
                    -- 跳过自环（表里每个站都有一条到自己的 0 距离记录）
                    if to_id ~= nil and to_id ~= from_id then
                        union_find.add(to_id)
                        union_find.union(from_id, to_id)
                        if #links < MAX_LINKS then
                            links[#links + 1] = { a = from_id, b = to_id, distance = distance }
                            diagnostics.links = diagnostics.links + 1
                        end
                    end
                end
            end
        end
    end
    diagnostics.map_entries = #top_entries
    diagnostics.catchment_probe = { samples = probe_samples, map_type = diagnostics.map_type,
                                    map_length = diagnostics.map_length, pairs_ok = pairs_ok }

    -- ③ 分组成站群。注意 catchment 表可能只包含"有互通关系的站"，
    --    没出现在表里的站各自成一个独立站群（互通表不列孤站）。
    local clusters_by_root = {}
    for _, station in pairs(stations) do
        union_find.add(station.entity_id)
    end
    for _, station in pairs(stations) do
        local root = union_find.find(station.entity_id)
        clusters_by_root[root] = clusters_by_root[root] or {}
        clusters_by_root[root][#clusters_by_root[root] + 1] = station.entity_id
    end

    local clusters = {}
    for root, member_ids in pairs(clusters_by_root) do
        table.sort(member_ids)
        local sum_x, sum_y, count = 0, 0, 0
        local min_x, max_x, min_y, max_y = nil, nil, nil, nil
        for _, member_id in ipairs(member_ids) do
            local position = stations[member_id] and stations[member_id].position
            if position ~= nil then
                sum_x, sum_y, count = sum_x + position.x, sum_y + position.y, count + 1
                min_x = min_x == nil and position.x or math.min(min_x, position.x)
                max_x = max_x == nil and position.x or math.max(max_x, position.x)
                min_y = min_y == nil and position.y or math.min(min_y, position.y)
                max_y = max_y == nil and position.y or math.max(max_y, position.y)
            end
        end
        clusters[#clusters + 1] = {
            root = common.entity_id(root) or root,
            member_ids = member_ids,
            member_count = #member_ids,
            center = count > 0 and { x = sum_x / count, y = sum_y / count, z = 0 } or nil,
            -- 站群跨度：越大说明这个"一片"越分散，前端可以据此决定要不要画连线
            span_m = (min_x ~= nil) and math.max(max_x - min_x, max_y - min_y) or nil,
        }
        diagnostics.clusters = diagnostics.clusters + 1
    end
    table.sort(clusters, function(a, b) return a.member_count > b.member_count end)

    local station_list = {}
    for _, station in pairs(stations) do
        if station.position ~= nil then
            station_list[#station_list + 1] = {
                entity_id = station.entity_id,
                name = station.name,
                position = station.position,
                cargo = station.cargo,
                cluster = common.entity_id(union_find.find(station.entity_id)),
            }
        end
    end
    table.sort(station_list, function(a, b) return a.entity_id < b.entity_id end)

    local multi = 0
    for _, cluster in ipairs(clusters) do
        if cluster.member_count > 1 then multi = multi + 1 end
    end

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "STATION_CLUSTER",
        counts = {
            total = #station_list,
            stations = #station_list,
            clusters = #clusters,
            linked_clusters = multi,
            links = #links,
            largest_cluster = clusters[1] and clusters[1].member_count or 0,
        },
        clusters = clusters,
        stations = station_list,
        links = links,
        diagnostics = diagnostics,
        errors = errors,
    }
end

return M
