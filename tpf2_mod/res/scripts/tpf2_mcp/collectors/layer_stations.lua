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
-- 取某点的地形高度（米）。参数形式按游戏源码里的用法逐个试，写法照抄 layer_terrain.lua。
-- 🔴 地下站判定必须用「在站台上直接采样」的结果，不能拿地形层的网格插值代替：
--    那张网格 170 m 一格，落在山谷里的站会被相邻格点的山坡拉高，
--    实测 24 个普通站因此被算成"地下 3~17 m"（2026-09-29 用户报的，这个存档一个地下站都没有）。
local function sample_height(fn, x, y)
    local ok, value = pcall(fn, { x, y })
    if ok and type(value) == "number" then return value end
    ok, value = pcall(fn, { x = x, y = y })
    if ok and type(value) == "number" then return value end
    ok, value = pcall(fn, { x, y, 0 })
    if ok and type(value) == "number" then return value end
    return nil
end

local function get_height_function()
    local ok, fn = pcall(function() return game.interface.getHeight end)
    if ok and type(fn) == "function" then return fn end
    return nil
end

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
    local height_fn = get_height_function()

    -- 车站 → 建筑 的映射（与 rail_network.lua 同一个接口）。
    -- 有了它才能知道每座车站**是什么交通方式**：游戏的建筑就是按
    -- `station/<类型>/...` 分目录的（本体纹理目录同样是 air / harbor / rail / road / train / water），
    -- 所以前端只看文件路径就能分辨火车站、汽车站、码头、机场 —— 局部视图里要列"附近交通枢纽"就靠它。
    local station_to_construction = nil
    local map_ok, map_or_error = pcall(function()
        return api.engine.system.streetConnectorSystem.getStation2ConstructionMap()
    end)
    if map_ok then
        station_to_construction = map_or_error
    else
        errors[#errors + 1] = { component = "STATION_TO_CONSTRUCTION_MAP", error = tostring(map_or_error) }
    end

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
        -- 站台的真实几何：把每个站台的发车节点坐标都收下来。
        -- 为什么需要：局部视图要像火车站那样显示**具体形状** —— 码头是一排泊位、
        -- 汽车站是一排车位。只给一个中心点就只能画个符号，看不出站场长什么样。
        -- 顺带也给 center 兜底（原先那段"拿第一个站台位置当中心"的逻辑合并到这里）。
        local platforms = {}
        for _, station_entity in ipairs(common.sequence_values(common.field(group, "stations"))) do
            local station = component_access.get(station_entity, "STATION")
            local cargo = common.field(station, "cargo")
            for _, terminal in ipairs(common.sequence_values(common.field(station, "terminals"))) do
                local node_entity = common.field(common.field(terminal, "vehicleNodeId"), "entity")
                local node = node_entity ~= nil and component_access.get(node_entity, "BASE_NODE") or nil
                local position = vec(common.field(node, "position")) or vec(common.field(node, "pos"))
                if position ~= nil then
                    platforms[#platforms + 1] = { x = position.x, y = position.y, z = position.z, cargo = cargo }
                    if center == nil then center = position end
                end
            end
        end
        local cargo_any = false
        -- 子车站（STATION 实体）的 id。互通表用的就是这套 id，不是 STATION_GROUP 的 id
        -- （2026-09-29 实测：35 个铁路站的 child_station_id 有 28 个能在互通表命中，
        --  同一批站的 group id 命中 0 个 —— 两套编号范围重叠但零交集）。
        local child_ids = {}
        -- 本车站用到的建筑文件（去重）。前端据此判断这是什么站：
        -- station/rail|train → 火车站、station/road → 汽车站、station/air → 机场、
        -- station/harbor|water → 码头。「附近交通枢纽」就是靠它分类的。
        local construction_files = {}
        local seen_files = {}
        -- 每座**子车站**一条：建筑文件 + 它自己的客货属性。
        -- 为什么不能只留一个 cargo 布尔值：一座站群常常同时有客运站台和货运站台
        -- （火车站旁边就是货场、码头同时跑客船和货船），压成一个布尔值就把
        -- "公路货运 / 公路客运 / 海运货运 / 海运客运"这四种区别全抹掉了。
        -- 有了 (交通方式 × 客货) 这个二维信息，前端才能像游戏那样分别标出来。
        local services = {}
        for _, station_entity in ipairs(common.sequence_values(common.field(group, "stations"))) do
            local child_id = common.entity_id(station_entity)
            if child_id ~= nil then child_ids[#child_ids + 1] = child_id end
            local station = component_access.get(station_entity, "STATION")
            local cargo = station ~= nil and common.field(station, "cargo") == true
            if cargo then cargo_any = true end
            -- 车站承载能力（客运 / 货运，单位见游戏内站台窗口）。
            -- 出处：官方 API `type.Station.pool : Pool { edges, moreCapacity }`；
            -- `.con` 侧由 `modulesutil.getStationPoolCapacities`（res/scripts/modulesutil.lua:19）
            -- 把「该站所有模块的 metadata.moreCapacity 之和」写进 pool.moreCapacity：
            --   铁路 / 汽车站 / 码头 → 各自 .con 的 updateFn 显式写；
            --   机场 → modulesutil.makeAutoTerminals 里写（四类站都有）。
            -- 2026-09-30：这是**唯一**能一次性拿到全部车站容量的字段
            -- （按模块目录求和需要每座站的模块清单，探针只采了首例）。
            local pool = common.field(station, "pool")
            local capacity = pool ~= nil and common.field(pool, "moreCapacity") or nil
            if type(capacity) ~= "number" then capacity = nil end
            local file = nil
            if station_to_construction ~= nil then
                local raw_construction_id = common.field(station_to_construction, station_entity)
                    or common.field(station_to_construction, child_id)
                local construction_id = common.entity_id(raw_construction_id)
                if construction_id ~= nil then
                    local construction = component_access.get(construction_id, "CONSTRUCTION")
                    file = common.field(construction, "fileName")
                    if type(file) == "string" and not seen_files[file] then
                        seen_files[file] = true
                        construction_files[#construction_files + 1] = file
                    end
                end
            end
            services[#services + 1] = {
                entity_id = child_id,
                file = type(file) == "string" and file or nil,
                cargo = cargo,
                capacity = capacity,
            }
        end
        -- 地表高度 / 埋深：在车站中点直接采样。
        -- 前端拿 depth_m 判地下站（>= 3 m 才算），比让它自己插值可靠得多。
        local surface_z = nil
        if center ~= nil and height_fn ~= nil then
            surface_z = sample_height(height_fn, center.x, center.y)
        end
        -- 站群口径的容量合计：把同一 cargo 标志的子车站容量加总。
        -- ⚠️ 这是**加法**不是取最大：一座站群里每个 (交通方式 × 客货) 子车站各有一个 pool，
        -- 它们物理上分散在不同建筑里，候车也分别排队，所以加总才是站群能承接的总量。
        local capacity_passenger = nil
        local capacity_cargo = nil
        for _, s in ipairs(services) do
            if s.capacity ~= nil then
                if s.cargo then
                    capacity_cargo = (capacity_cargo or 0) + s.capacity
                else
                    capacity_passenger = (capacity_passenger or 0) + s.capacity
                end
            end
        end
        stations[group_id] = {
            entity_id = group_id,
            child_ids = child_ids,
            name = name or ("Station " .. tostring(group_id)),
            position = center,
            surface_z = surface_z,
            depth_m = (surface_z ~= nil and center ~= nil) and (surface_z - center.z) or nil,
            cargo = cargo_any,
            construction_files = construction_files,
            capacity_passenger = capacity_passenger,
            capacity_cargo = capacity_cargo,
            services = services,
            platforms = platforms,
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

    -- ②.5 决定每个站群拿哪个 id 去参与并查集。
    -- 🔴 互通表（catchmentAreaSystem）的键是「子车站 STATION 实体」的 id，不是
    --    STATION_GROUP 的 id。2026-09-29 实测：35 个铁路站的 child_station_id 里
    --    28 个能命中互通表，而 group id 命中 0 个 —— 两套编号范围重叠但交集为空。
    --    用 group id 建并查集，结果就是 1497 条边却 328 个孤群。
    --    没命中互通表的站（孤站，互通表本来就不列）退回自己的 group id，自成一群。
    local catchment_key_set = {}
    for _, entry in ipairs(top_entries) do
        local id = common.entity_id(entry.key)
        if id == nil and type(entry.key) == "number" then id = entry.key end
        if id ~= nil then catchment_key_set[id] = true end
    end
    local key_matched, key_fallback = 0, 0
    for _, station in pairs(stations) do
        local chosen = nil
        for _, child_id in ipairs(station.child_ids or {}) do
            if catchment_key_set[child_id] then
                -- 一个站群的多个子车站同属一片，先互相连起来
                if chosen == nil then chosen = child_id else union_find.union(chosen, child_id) end
            end
        end
        if chosen ~= nil then
            station.key_id = chosen
            key_matched = key_matched + 1
        else
            station.key_id = station.entity_id
            key_fallback = key_fallback + 1
        end
    end
    diagnostics.cluster_key_matched = key_matched
    diagnostics.cluster_key_fallback = key_fallback

    -- ③ 分组成站群。注意 catchment 表可能只包含"有互通关系的站"，
    --    没出现在表里的站各自成一个独立站群（互通表不列孤站）。
    local clusters_by_root = {}
    for _, station in pairs(stations) do
        union_find.add(station.key_id)
    end
    for _, station in pairs(stations) do
        local root = union_find.find(station.key_id)
        clusters_by_root[root] = clusters_by_root[root] or {}
        clusters_by_root[root][#clusters_by_root[root] + 1] = station
    end

    local clusters = {}
    for root, members in pairs(clusters_by_root) do
        local member_ids = {}
        for _, member in ipairs(members) do member_ids[#member_ids + 1] = member.entity_id end
        table.sort(member_ids)
        local sum_x, sum_y, count = 0, 0, 0
        local min_x, max_x, min_y, max_y = nil, nil, nil, nil
        for _, member in ipairs(members) do
            local position = member.position
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
                surface_z = station.surface_z,
                depth_m = station.depth_m,
                cargo = station.cargo,
                -- 🔴 下面这四个**必须在这里再列一次**：payload 发出去的是这个 station_list，
                --    不是上面那个 `stations[group_id]` 内部表。2026-09-29 踩过：
                --    只往内部表里加字段 → 数据其实采到了（errors 为空、探针都在跑），
                --    却在最后一步被静默裁掉，前端永远收不到（表现是"改了没生效"）。
                --    以后给车站加字段，**两处都要加**。
                child_ids = station.child_ids,
                construction_files = station.construction_files,
                services = station.services,
                platforms = station.platforms,
                cluster = common.entity_id(union_find.find(station.key_id or station.entity_id)),
            }
        end
    end
    table.sort(station_list, function(a, b) return a.entity_id < b.entity_id end)

    local multi = 0
    for _, cluster in ipairs(clusters) do
        if cluster.member_count > 1 then multi = multi + 1 end
    end

    -- ---- 联通关系探针（2026-09-29）----
    -- 游戏里**选中车站**会把"与它联通"的产业 / 货场高亮成浅白色。判定这些关系的接口都在
    -- `stationSystem` 下（getStation2TownMap / getStation2edgesMap / getPersonNodeId2StationTerminalsMap
    -- / getTown2StationsMap），但返回结构没有文档。先把几条样本塞进诊断看清键值长什么样，
    -- 再写正式采集 —— 改一次 Lua 就要重启一次游戏，先探明比猜着写好。
    local function dump_shape(value, depth)
        if value == nil then return "nil" end
        local kind = type(value)
        if kind ~= "table" and kind ~= "userdata" then return kind .. "=" .. tostring(value) end
        if depth <= 0 then return kind end
        local pieces = {}
        local count = common.array_count(value)
        if count ~= nil then pieces[#pieces + 1] = "#" .. tostring(count) end
        local taken = 0
        local ok = pcall(function()
            for key, item in pairs(value) do
                if taken >= 4 then pieces[#pieces + 1] = "..." break end
                taken = taken + 1
                pieces[#pieces + 1] = tostring(key) .. ":" .. dump_shape(item, depth - 1)
            end
        end)
        if not ok then pieces[#pieces + 1] = "<pairs failed>" end
        return "{" .. table.concat(pieces, ", ") .. "}"
    end
    local link_probe = {}
    local function probe_map(label, fn)
        local ok, value = pcall(fn)
        if not ok then
            link_probe[label] = { error = tostring(value) }
            return
        end
        link_probe[label] = { shape = dump_shape(value, 3) }
    end
    local station_system = api.engine.system.stationSystem
    if station_system ~= nil then
        probe_map("station2town", function() return station_system.getStation2TownMap() end)
        probe_map("station2edges", function() return station_system.getStation2edgesMap() end)
        probe_map("personNode2terminals", function() return station_system.getPersonNodeId2StationTerminalsMap() end)
        probe_map("town2stations", function() return station_system.getTown2StationsMap() end)
    else
        link_probe.station_system = "unavailable"
    end
    probe_map("station2construction", function()
        return api.engine.system.streetConnectorSystem.getStation2ConstructionMap()
    end)
    diagnostics.link_probe = link_probe

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
