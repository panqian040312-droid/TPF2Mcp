-- 图层：道路交通（NPC 车流 + 路段路况）
--
-- 用户诉求（2026-09-30）：「像高德地图一样，每 5 分钟采样一次，把路况用颜色区分出来，
--   放大才显示，可以开可以关，静态显示」——**不要逐辆渲染 NPC 车**，有聚合数据就够。
--
-- 所以本层只输出**每条路段的聚合**：多少车、平均多快、堵不堵。
-- 前端据此把路段涂成 绿/黄/橙/红（高德那套配色），**一个逐辆车的点都不画**。
--
-- 数据从哪来（文档 + 我们自己的 world-probe.json 双向核对过）：
--   · `ROAD_VEHICLE`（=67）本存档 **10,710 个实体**，但它不是空壳车 —— 是
--     **一个人 + 一辆车同一个实体**（TPF2 是个体模拟）。样本实测字段：
--       name="Zinaida Morozov" / type="SIM_PERSON" / destinations·moveModes·travelTimes 各长 3
--       / modelIdCar / modelIdPerson / lastMoveMode / speed / targetOrAtEntity
--     ⇒ "NPC 车流"就是能逐个读的居民出行。
--   · 车辆当前在哪条路上：`MOVE_PATH.path.edges[pathPos.edgeIndex]`。
--     ⚠️ 它给的是 **TRANSPORT_NETWORK 的边下标**（每张网自己从 0 编），
--        而前端要的是 **BASE_EDGE 实体 id**（layer-road.json 用的就是它）。
--        两张 id 之间的换算表**没有文档**，只能现场建：拿 `TRANSPORT_NETWORK.edges` 的元素，
--        逐个候选字段去验证"它是不是真挂 BASE_EDGE 组件"。建一次缓存整个游戏会话
--        （路是静态的，不会每次变），失败也会如实报出来而不是当成"路上没车"。
--
-- ⚠️ 本文件写出来的时候**游戏是关的，一次都没跑过**。所以：所有引擎读取都裹 pcall；
--    结构类结论一律带 `diagnostics`（映射表命中率、失败原因分布、出行方式分布），
--    下一轮照实测改，不猜。
--
-- 节流：**自己按挂钟节流**（每 SAMPLE_INTERVAL_SECONDS 秒采一次，默认 300 = 5 分钟）。
--   为什么不用注册表的 `every` 来定节奏：那是按 update 帧数算的，而帧率取决于机器和负载，
--   换算不出"5 分钟"。注册表那边把 every 设成"勤检查"（很轻，只读一次 os.time），
--   真正是否采样由这里的闸门决定；不到点就把上一次的产物原样返回（文件内容不变）。
--
-- 只读：不发写命令，不改游戏状态。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

local SAMPLE_INTERVAL_SECONDS = 300   -- 采样间隔（挂钟秒）。用户要的"每 5 分钟"。
local RETRY_INTERVAL_SECONDS = 90      -- 上一次一辆车都没定位到时的重试间隔（调试期别让人干等）
local VEHICLE_LIMIT = 30000           -- 本存档 10,710 辆；给足余量
local NETWORK_MAP_LIMIT = 4           -- 最多给几张传输网建"下标 → 实体"表
local SEGMENT_LIMIT = 6000            -- 产物里最多写多少条路段（按车数排序截断）
local ERROR_LIMIT = 30

-- 车辆定位：路径位置与边 id 可能在哪些键下（按可能性排序，逐个试）
local PATHPOS_KEYS = { "pathPos", "pos", "position" }
local EDGEID_KEYS = { "edgeId", "edge", "id" }
local EDGE_ENTITY_KEYS = { "entity", "edgeEntity", "baseEdge", "base_edge", "entity_id", "id" }

local TRANSPORT_MODE_NAME = {
    [0] = "PERSON", [1] = "CARGO", [2] = "CAR", [3] = "BUS", [4] = "TRUCK", [5] = "TRAM",
    [6] = "ELECTRIC_TRAM", [7] = "TRAIN", [8] = "ELECTRIC_TRAIN", [9] = "AIRCRAFT",
    [10] = "SHIP", [11] = "SMALL_AIRCRAFT", [12] = "SMALL_SHIP",
}

-- 会话级缓存：路网静态，这些不用每次重算
local edge_maps = {}        -- network_entity → { map = {下标 → BASE_EDGE}, hit_key = ... }
local maps_built = {}       -- network_entity → true（建过就别再建，除非失效）
local edge_meta = {}        -- BASE_EDGE 实体 → { street_type, has_bus, has_tram }（静态）
local discovery = nil       -- 首次采样时的结构探测结果（组件清单/字段形状），之后复用
local last_payload = nil
local last_sample_time = 0
local last_sample_game_time = nil

local function push_error(errors, entry)
    if #errors < ERROR_LIMIT then errors[#errors + 1] = entry end
end

local function call(fn)
    local ok, value = pcall(fn)
    if ok then return value end
    return nil
end

-- 🔴 2026-09-30 首次实测教训（本层第一次跑就撞上，两条都记进 common.lua 了）：
--   ① `component["字段名"]`（getter 路径）对 `ROAD_VEHICLE` **一个字段都读不到**
--      （speed / lastMoveMode / moveModes / modelIdCar … 全是 nil），而 `pairs(component)` 有值
--      —— 和 town 层那次正好相反（那次是 getter 给空壳、pairs 才有）。
--   ② `pairs(api.type.ComponentType)` 在本机**枚举不出任何东西** → "实体挂了哪些组件"这个
--      探针返回空数组。要问它只能按硬编码的组件名清单逐个试。
--   ⇒ 统一走 common 里的 `flatten` / `pick` / `components_of`，别再各写一套。
local flatten = common.flatten
local pick = common.pick

-- 引擎集合可能是 userdata、可能 0 基。**先走 getter 拿长度，拿不到再靠 pairs 数**。
local function each_index(value, limit, fn)
    local count = common.array_count(value)
    if count == nil then
        -- pairs 兜底（有些容器 # 不可用）
        local items = {}
        pcall(function() for _, item in pairs(value) do items[#items + 1] = item end end)
        count = #items
        for index = 1, math.min(count, limit) do fn(items[index], index) end
        return math.min(count, limit), count
    end
    local start = 1
    if common.field(value, 0) ~= nil and common.field(value, count) == nil then start = 0 end
    local emitted = 0
    for index = start, start + count - 1 do
        if emitted >= limit then break end
        local item = common.field(value, index)
        if item ~= nil then
            emitted = emitted + 1
            fn(item, index)
        end
    end
    return emitted, count
end

local function present_components(entity)
    local ok, names = pcall(common.components_of, entity)
    if not ok then return nil end
    return names
end

local function first_number(value, keys)
    if value == nil then return nil, nil end
    for _, key in ipairs(keys) do
        local candidate = pick(value, key)
        local as_number = tonumber(tostring(candidate))
        if as_number ~= nil then return as_number, key end
    end
    return nil, nil
end

local function keys_of(value)
    if value == nil then return nil end
    local list = {}
    for key, item in pairs(flatten(value)) do list[#list + 1] = key .. ":" .. type(item) end
    table.sort(list)
    return list
end

-- 读路段的静态属性（street_type / 有没有公交电车）。读一次就缓存 —— 路不会一直变。
local function meta_of(base_edge)
    local cached = edge_meta[base_edge]
    if cached ~= nil then return cached end
    local street = component_access.get(base_edge, "BASE_EDGE_STREET")
    local value = {
        street_type = pick(street, "streetType"),
        has_bus = pick(street, "hasBus") == true,
        has_tram = pick(street, "hasTram") == true,
    }
    if value.street_type == nil and street == nil then value = { missing = true } end
    edge_meta[base_edge] = value
    return value
end

-- 某张传输网的「边下标 → BASE_EDGE 实体」表。
-- 没有文档，靠"候选字段必须真是 BASE_EDGE"来验证。**无论成不成，都把首元素的字段形状报出去** ——
-- 第一次实测就吃了"读法不对"的亏（`edges` 只读出 4~26 条，其实是字段路径不对）。
local function build_edge_index_map(network_entity)
    local network = component_access.get(network_entity, "TRANSPORT_NETWORK")
    local edges = pick(network, "edges")
    if edges == nil then
        return { seen = 0, hit = 0, reason = "no_edges_field", network_keys = keys_of(network) }
    end
    local map, hit_key, seen, hit = {}, nil, 0, 0
    local first_keys, first_candidates = nil, nil
    each_index(edges, 20000, function(element, index)
        seen = seen + 1
        if first_keys == nil then
            first_keys = keys_of(element)
            first_candidates = {}
            for _, key in ipairs(EDGE_ENTITY_KEYS) do
                local candidate = pick(element, key)
                first_candidates[key] = candidate ~= nil and tostring(candidate) or nil
            end
        end
        local candidate, key = first_number(element, EDGE_ENTITY_KEYS)
        if candidate ~= nil and component_access.get(candidate, "BASE_EDGE") ~= nil then
            map[index] = candidate
            hit = hit + 1
            hit_key = hit_key or key
        end
    end)
    return {
        map = hit > 0 and map or nil,
        hit_key = hit_key, seen = seen, hit = hit,
        first_element_keys = first_keys, first_candidates = first_candidates,
    }
end

local function edge_map_for(network_entity)
    local entry = edge_maps[network_entity]
    if entry ~= nil then return entry end
    if maps_built[network_entity] then return nil end
    local built = 0
    for _ in pairs(maps_built) do built = built + 1 end
    if built >= NETWORK_MAP_LIMIT then
        maps_built[network_entity] = true
        return nil
    end
    local report = build_edge_index_map(network_entity)
    maps_built[network_entity] = true
    edge_maps[network_entity] = report
    return report
end

-- 读实体的**聚合表**：`game.interface.getEntity(id)`。这是唯一能读到车辆运行字段的路 ——
-- 组件本体（api.engine.getComponent）是 userdata，同一辆车的可读字段数是 **0**。
local function aggregate_of(entity)
    if entity == nil then return nil end
    local id = common.entity_id(entity)
    if id == nil then return nil end
    local ok, value = pcall(function() return game.interface.getEntity(id) end)
    if not ok then return nil end
    return value
end

local GRID_SIZE = 500        -- 空间网格边长（米）。地图约 1.5 万米见方 → 30×30 格
local MAX_MATCH_M = 90       -- 匹配半径（米）：城市路网够密，90 米内必有所属路段

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

-- 车辆的世界坐标：BOUNDING_VOLUME 的 bbox 中心。读法照抄 layer_vehicles（已验证可行）。
local function vehicle_center(entity)
    local volume = component_access.get(entity, "BOUNDING_VOLUME")
    local bbox = common.field(volume, "bbox")
    local mn = vec(common.field(bbox, "min")) or vec(common.field(bbox, "bbMin"))
    local mx = vec(common.field(bbox, "max")) or vec(common.field(bbox, "bbMax"))
    if mn == nil or mx == nil then return nil end
    return { x = (mn.x + mx.x) / 2, y = (mn.y + mx.y) / 2 }
end

local function point_segment_distance(px, py, x0, y0, x1, y1)
    local dx, dy = x1 - x0, y1 - y0
    local length_sq = dx * dx + dy * dy
    if length_sq <= 0 then
        local ex, ey = px - x0, py - y0
        return math.sqrt(ex * ex + ey * ey)
    end
    local t = ((px - x0) * dx + (py - y0) * dy) / length_sq
    if t < 0 then t = 0 elseif t > 1 then t = 1 end
    local qx, qy = x0 + t * dx, y0 + t * dy
    local ex, ey = px - qx, py - qy
    return math.sqrt(ex * ex + ey * ey)
end

-- 全部路段的几何 + 空间网格索引。返回 { edges, skipped, nearest=fn }
-- 几何读法照抄 layer_road：遍历 BASE_EDGE_STREET → BASE_EDGE(node0/node1) → BASE_NODE.position
local function build_street_index(errors)
    local node_cache, edges, grid = {}, {}, {}
    local skipped, node_reported = 0, false

    local function node_position(raw)
        local id = common.entity_id(raw)
        if id == nil then return nil end
        local cached = node_cache[id]
        if cached ~= nil then
            if cached == false then return nil end
            return cached
        end
        local node = component_access.get(raw, "BASE_NODE")
        if node == nil and not node_reported then
            node_reported = true
            errors[#errors + 1] = { component = "BASE_NODE", note = "unavailable; counted in skipped" }
        end
        local position = vec(common.field(node, "position")) or vec(common.field(node, "pos"))
        node_cache[id] = position or false
        return position
    end

    common.safe_for_each_entity("BASE_EDGE_STREET", function(edge_entity)
        local base = component_access.get(edge_entity, "BASE_EDGE")
        if base == nil then skipped = skipped + 1 return end
        local a = node_position(common.field(base, "node0"))
        local b = node_position(common.field(base, "node1"))
        if a == nil or b == nil then skipped = skipped + 1 return end

        local index = #edges + 1
        edges[index] = { id = common.entity_id(edge_entity), x0 = a.x, y0 = a.y, x1 = b.x, y1 = b.y }

        -- 长边会跨格，两端和中点都要挂 —— 只挂中点会让贴着格子边界的车找不到它
        local seen = {}
        local function attach(x, y)
            local key = math.floor(x / GRID_SIZE) .. "_" .. math.floor(y / GRID_SIZE)
            if seen[key] then return end
            seen[key] = true
            local cell = grid[key]
            if cell == nil then cell = {}; grid[key] = cell end
            cell[#cell + 1] = index
        end
        attach(a.x, a.y)
        attach(b.x, b.y)
        attach((a.x + b.x) / 2, (a.y + b.y) / 2)
    end, errors)

    -- 最近路段：查所在格 + 8 个邻格（车贴着格子边界时，属边在隔壁）
    local function nearest(x, y)
        local cx, cy = math.floor(x / GRID_SIZE), math.floor(y / GRID_SIZE)
        local best_id, best_dist = nil, nil
        for ox = -1, 1 do
            for oy = -1, 1 do
                local cell = grid[(cx + ox) .. "_" .. (cy + oy)]
                if cell ~= nil then
                    for i = 1, #cell do
                        local edge = edges[cell[i]]
                        local dist = point_segment_distance(x, y, edge.x0, edge.y0, edge.x1, edge.y1)
                        if best_dist == nil or dist < best_dist then best_id, best_dist = edge.id, dist end
                    end
                end
            end
        end
        if best_id == nil then return nil, nil, "no_edge_in_cell" end
        if best_dist ~= nil and best_dist > MAX_MATCH_M then return nil, best_dist, "too_far" end
        return best_id, best_dist, nil
    end

    return { edges = edges, skipped = skipped, nearest = nearest }
end

-- 车辆定位：**坐标匹配**（2026-10-02 换的方案）。
--
-- 原来走「传输网边下标 → BASE_EDGE 实体」的映射，但那条链的形状始终没探明：
--   `pick(network, "edges")` 只读出 4~26 条（真实路网近万条）、边元素本身 keys 全空
--   （userdata，pairs 枚举不出）、官方文档里也没有这个映射 —— 再挖是拿轮次换运气。
-- 改用几何法：**车辆包围盒中心 ↔ 最近的路段线段**。坐标来源与 layer_vehicles 一致
-- （BOUNDING_VOLUME → bbox 中心），那条路已验证可行。半径外的车丢弃并计数，宁可漏不可错配。
--
-- 返回 base_edge_id, 匹配距离(米), 网络实体(旧路才有), 失败原因
local function locate_vehicle(entity, street_index)
    -- 新路：坐标匹配
    if street_index ~= nil then
        local center = vehicle_center(entity)
        if center == nil then return nil, nil, nil, "no_position" end
        local found, distance, fail = street_index.nearest(center.x, center.y)
        if found ~= nil then return found, distance, nil, nil end
        if fail ~= nil then return nil, distance, nil, fail end
    end

    -- 旧路（id 映射）保留在后面当对照：目前一条都定位不到，但不删 —— 哪天把 edges 的形状摸清了还能回来用
    local move_path = component_access.get(entity, "MOVE_PATH")
    if move_path == nil then return nil, nil, nil, "no_move_path" end
    local edges = pick(pick(move_path, "path"), "edges")
    if edges == nil then return nil, nil, nil, "no_path_edges" end

    local dyn = pick(move_path, "dyn")
    local path_pos = nil
    for _, key in ipairs(PATHPOS_KEYS) do
        path_pos = pick(dyn, key)
        if path_pos == nil then path_pos = pick(move_path, key) end
        if path_pos ~= nil then break end
    end
    if path_pos == nil then return nil, nil, nil, "no_path_pos" end

    local edge_index = pick(path_pos, "edgeIndex")
    if type(edge_index) ~= "number" then return nil, nil, nil, "no_edge_index" end

    local count = common.array_count(edges) or 0
    local start = 1
    if common.field(edges, 0) ~= nil and common.field(edges, count) == nil then start = 0 end
    local element = common.field(edges, start + edge_index)
    if element == nil then return nil, nil, nil, "edge_index_out_of_range" end

    local edge_id = nil
    for _, key in ipairs(EDGEID_KEYS) do
        edge_id = pick(element, key)
        if edge_id ~= nil then break end
    end
    if edge_id == nil then return nil, nil, nil, "no_edge_id" end

    local network_entity = first_number(edge_id, { "entity", "network", "tn" })
    local index = first_number(edge_id, { "index", "edgeIndex", "i" })

    -- 情况一：边元素里直接就是 BASE_EDGE 实体 id（最省事）
    local direct = first_number(element, EDGE_ENTITY_KEYS)
    if direct ~= nil and component_access.get(direct, "BASE_EDGE") ~= nil then
        return direct, network_entity, index, nil
    end
    -- 情况二：查那张现场建的表
    if network_entity ~= nil and index ~= nil then
        local entry = edge_map_for(network_entity)
        if entry ~= nil and entry.map ~= nil then
            local found = entry.map[index]
            if found ~= nil then return found, network_entity, index, nil end
            return nil, network_entity, index, "index_not_in_map"
        end
        return nil, network_entity, index, "edge_map_unavailable"
    end
    return nil, network_entity, index, "no_network_or_index"
end

-- 定位失败时的结构深挖：把「一辆车的 路径 → 边 → 网络」这条链上的对象全摊开。
-- 第一次实测就是靠这类自报信息才看清"字段得读 pairs"——宁可产物大一点，也别让我瞎猜。
local function probe_vehicle_structure(entity)
    local move_path = component_access.get(entity, "MOVE_PATH")
    local path = pick(move_path, "path")
    local edges = pick(path, "edges")
    local first_element = common.field(edges, 1) or common.field(edges, 0)
    local edge_id = first_element and pick(first_element, "edgeId") or nil
    local network_entity = edge_id and first_number(edge_id, { "entity", "network", "tn" }) or nil
    local network = network_entity and component_access.get(network_entity, "TRANSPORT_NETWORK") or nil
    local network_edges = pick(network, "edges")
    local candidates = nil
    if first_element ~= nil then
        candidates = {}
        for _, key in ipairs(EDGE_ENTITY_KEYS) do
            local candidate = pick(first_element, key)
            candidates[key] = candidate ~= nil and tostring(candidate) or nil
        end
    end
    return {
        entity_id = common.entity_id(entity),
        present_components = present_components(entity),
        move_path_keys = keys_of(move_path),
        path_keys = keys_of(path),
        path_edges_count = common.array_count(edges),
        first_element_keys = keys_of(first_element),
        first_element_candidates = candidates,
        edge_id_keys = keys_of(edge_id),
        edge_id_entity = network_entity,
        network_keys = keys_of(network),
        network_edges_count = common.array_count(network_edges),
        network_first_element_keys = keys_of(common.field(network_edges, 1) or common.field(network_edges, 0)),
    }
end

-- 加权重分位（Lua 版）。values = { {speed, weight}, ... }
local function percentile(values, fraction)
    if #values == 0 then return nil end
    table.sort(values, function(a, b) return a[1] < b[1] end)
    local total = 0
    for i = 1, #values do total = total + values[i][2] end
    if total <= 0 then return nil end
    local target = total * fraction
    local running = 0
    for i = 1, #values do
        running = running + values[i][2]
        if running >= target then return values[i][1] end
    end
    return values[#values][1]
end

local function game_time_now()
    local world = call(function() return api.engine.util.getWorld() end)
    local player = call(function() return api.engine.util.getPlayer() end)
    local component = (world and component_access.get(world, "GAME_TIME"))
        or (player and component_access.get(player, "GAME_TIME"))
    return common.field(component, "gameTime")
end

local function wall_clock()
    return (os and os.time and os.time()) or 0
end

-- 采一次。这是本层的真正工作函数。
local function sample()
    local errors = {}
    local started = common.clock()
    local out = {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "TRAFFIC",      -- 只有"每条边的指标"，没有几何 —— 几何由前端从公路层取
        counts = {},
        errors = errors,
    }

    out.game_time = game_time_now()

    local move_mode_tally, sub_mode_tally = {}, {}
    local buckets = { stopped = 0, slow = 0, normal = 0, fast = 0 }
    local seen, located, unlocated = 0, 0, 0
    local fail_reasons = {}
    local traffic = {}      -- base_edge → { n, sum_speed, stopped, moving }
    local first_entity = nil
    -- 路段几何 + 空间网格（每次采样建一次。路是静态的，但采集器本身无状态）
    local street_index = build_street_index(errors)
    local match_distances = {}   -- 匹配距离直方（10 米一档）：看 90 米这个阈值合不合适

    common.safe_for_each_entity("ROAD_VEHICLE", function(entity)
        if seen >= VEHICLE_LIMIT then return end
        seen = seen + 1
        if first_entity == nil then first_entity = entity end

        -- 🔴 字段从**聚合表**读（2026-10-02 定论）：组件本体是 userdata —— getter 给 nil、
        --    pairs 也枚举不出键（同一辆车可读字段数 = 0）；而 game.interface.getEntity 给的
        --    聚合表是普通 table，同一辆车有 17 个字段（speed=2.07 / lastMoveMode=1 / moveModes len=3 …）。
        local vehicle_view = aggregate_of(entity)
        local speed = pick(vehicle_view, "speed")

        local mode = pick(vehicle_view, "lastMoveMode")
        local mode_key = TRANSPORT_MODE_NAME[mode] or ("MODE_" .. tostring(mode))
        move_mode_tally[mode_key] = (move_mode_tally[mode_key] or 0) + 1
        each_index(pick(vehicle_view, "moveModes"), 3, function(value)
            local each_key = TRANSPORT_MODE_NAME[value] or ("MODE_" .. tostring(value))
            sub_mode_tally[each_key] = (sub_mode_tally[each_key] or 0) + 1
        end)

        if type(speed) == "number" then
            local kmh = speed * 3.6
            if kmh < 0.5 then buckets.stopped = buckets.stopped + 1
            elseif kmh < 15 then buckets.slow = buckets.slow + 1
            elseif kmh < 45 then buckets.normal = buckets.normal + 1
            else buckets.fast = buckets.fast + 1 end
        end

        -- 结构探测只在第一次采样做（问清"一辆 NPC 车挂了哪些组件、字段怎么读"）
        if discovery == nil then
            discovery = { vehicle_example = probe_vehicle_structure(entity) }
        end

        local base_edge, match_distance, network_entity, reason = locate_vehicle(entity, street_index)
        if base_edge ~= nil then
            located = located + 1
            if type(match_distance) == "number" then
                local bucket = math.floor(match_distance / 10) * 10
                match_distances[bucket] = (match_distances[bucket] or 0) + 1
            end
            local entry = traffic[base_edge]
            if entry == nil then entry = { n = 0, sum = 0, stopped = 0, moving = 0 }; traffic[base_edge] = entry end
            entry.n = entry.n + 1
            if type(speed) == "number" then
                entry.sum = entry.sum + speed
                if speed * 3.6 < 0.5 then entry.stopped = entry.stopped + 1 else entry.moving = entry.moving + 1 end
            end
        else
            unlocated = unlocated + 1
            fail_reasons[reason or "unknown"] = (fail_reasons[reason or "unknown"] or 0) + 1
            if out.first_unlocated == nil then
                out.first_unlocated = {
                    entity_id = common.entity_id(entity), reason = reason,
                    match_distance = match_distance, network_entity = network_entity,
                }
            end
        end
    end, errors)

    -- ===== 组装路段清单 + 自标定"畅通速度" =====
    -- 游戏不给限速，所以拿**同一条路型上实测车速的 85 分位**当畅通速度 —— 数据自己标定，
    -- 不依赖任何文档里没有的参数。拥堵指数 = 1 − 实测/畅通，越接近 1 越堵。
    local per_type = {}
    local rows = {}
    for base_edge, entry in pairs(traffic) do
        if entry.n > 0 then
            local average = entry.sum / entry.n
            local meta = meta_of(base_edge)
            local street_type = meta.street_type or "(unknown)"
            per_type[street_type] = per_type[street_type] or {}
            table.insert(per_type[street_type], { average, entry.n })
            rows[#rows + 1] = {
                edge_id = base_edge, n = entry.n, avg_speed_ms = average,
                stopped = entry.stopped, moving = entry.moving,
                street_type = meta.street_type or nil,
                has_bus = meta.has_bus or nil, has_tram = meta.has_tram or nil,
            }
        end
    end

    local free_flow = {}
    local all = {}
    for street_type, values in pairs(per_type) do
        free_flow[street_type] = percentile(values, 0.85)
        for i = 1, #values do all[#all + 1] = values[i] end
    end
    local global_ff = percentile(all, 0.85)

    -- 分档（**未标定**：跑通有数据后按实测分布重定）
    local WARN_AT, ALARM_AT, MIN_VEHICLES = 0.30, 0.55, 2
    local by_level = { ALARM = 0, WARN = 0, OK = 0 }
    for i = 1, #rows do
        local row = rows[i]
        local ff = free_flow[row.street_type or "(unknown)"] or global_ff
        row.level = "OK"
        row.congestion = nil
        if ff and ff > 0.5 and row.avg_speed_ms then
            local value = 1.0 - row.avg_speed_ms / ff
            if value < 0 then value = 0 end
            if value > 1 then value = 1 end
            row.congestion = value
            if row.n >= MIN_VEHICLES then
                if value >= ALARM_AT then row.level = "ALARM"
                elseif value >= WARN_AT then row.level = "WARN" end
            end
        end
        by_level[row.level] = by_level[row.level] + 1
        row.avg_kmh = row.avg_speed_ms * 3.6
        row.ff_kmh = ff and (ff * 3.6) or nil
        row.avg_speed_ms = nil
    end

    table.sort(rows, function(a, b)
        local ac, bc = a.congestion or -1, b.congestion or -1
        if ac ~= bc then return ac > bc end
        return a.n > b.n
    end)
    local truncated = false
    if #rows > SEGMENT_LIMIT then
        local trimmed = {}
        for i = 1, SEGMENT_LIMIT do trimmed[i] = rows[i] end
        rows = trimmed
        truncated = true
    end

    local map_report = {}
    for network_entity, entry in pairs(edge_maps) do
        local mapped = 0
        if entry.map ~= nil then for _ in pairs(entry.map) do mapped = mapped + 1 end end
        map_report[#map_report + 1] = {
            network_entity = network_entity, hit_field = entry.hit_key,
            edges_seen = entry.seen, edges_hit = entry.hit, mapped = mapped,
            reason = entry.reason, network_keys = entry.network_keys,
            first_element_keys = entry.first_element_keys, first_candidates = entry.first_candidates,
        }
    end
    table.sort(map_report, function(a, b) return (a.edges_seen or 0) > (b.edges_seen or 0) end)

    -- 一辆都没定位到：把整条链的结构摊开报出来（下次不用猜该读哪个字段）
    if located == 0 and first_entity ~= nil then
        out.structure_dump = probe_vehicle_structure(first_entity)
        out.structure_dump.edge_index_maps = map_report
    end

    local transport_seen = 0
    common.safe_for_each_entity("TRANSPORT_VEHICLE", function() transport_seen = transport_seen + 1 end, errors)

    out.sampled_at = wall_clock()
    out.sample_interval_seconds = SAMPLE_INTERVAL_SECONDS
    out.thresholds = { warn = WARN_AT, alarm = ALARM_AT, min_vehicles = MIN_VEHICLES }
    out.calibration = {
        method = "按 street_type 取实测车速的 85 分位当畅通速度（游戏不给限速）",
        free_flow_kmh = (function()
            local result = {}
            for street_type, value in pairs(free_flow) do
                result[street_type] = value and (value * 3.6) or nil
            end
            return result
        end)(),
        global_free_flow_kmh = global_ff and (global_ff * 3.6) or nil,
        thresh_uncalibrated = true,
    }
    out.vehicles = {
        seen = seen, located = located, unlocated = unlocated,
        fail_reasons = fail_reasons,
        move_mode = move_mode_tally,       -- lastMoveMode 分布（枚举含义待实测确认）
        move_modes_all = sub_mode_tally,
        speed_kmh_buckets = buckets,
    }
    out.diagnostics = {
        note = "「传输网边下标 → BASE_EDGE 实体」的表是现场建的（没有文档）：命中字段与命中率见下；"
            .. "定位失败的分布见 vehicles.fail_reasons",
        edge_index_map = map_report,
        vehicle_components = discovery and discovery.vehicle_example or nil,
        -- 新方案（坐标匹配）的自检：路段索引建了多少条、车与路的匹配距离分布
        -- —— 阈值 90 米合不合适，看这张直方图就知道（大量落在 80~90 说明该放宽）。
        street_index = {
            edges = #street_index.edges,
            skipped = street_index.skipped,
            match_distance_histogram = match_distances,
        },
    }
    out.segments = { truncated = truncated, items = rows }
    out.summary = {
        road_vehicles = seen,
        located = located,
        unlocated = unlocated,
        segments_with_traffic = #rows,
        alarm = by_level.ALARM,
        warn = by_level.WARN,
        ok = by_level.OK,
        player_transport_vehicles = transport_seen,
    }
    out.counts = {
        total = #rows,
        alarm = by_level.ALARM,
        warn = by_level.WARN,
        road_vehicles = seen,
        located = located,
    }
    out.duration_ms = (common.clock() - started) * 1000
    return out
end

function M.collect()
    local now = wall_clock()
    -- 节奏：正常 5 分钟一次；**上一次一辆车都没定位到时改成 90 秒** —— 那种情况说明读法或映射表有问题，
    -- 让人干等 5 分钟才看到下一次结果太折磨。一旦采到数据就自动回到 5 分钟。
    local interval = SAMPLE_INTERVAL_SECONDS
    if last_payload ~= nil then
        local located = ((last_payload.summary or {}).located) or 0
        if located == 0 then interval = RETRY_INTERVAL_SECONDS end
    end
    -- 不到点：把上一次的产物原样交回去（内容不变，前端不会因为 mtime 变了就重画）
    if last_payload ~= nil and now > 0 and (now - last_sample_time) < interval then
        return last_payload
    end
    local ok, payload = pcall(sample)
    if not ok then
        return {
            status = "ERROR",
            source_status = "ENGINE_OBSERVED",
            geometry_kind = "TRAFFIC",
            error = tostring(payload),
            counts = { total = 0 },
        }
    end
    if now > 0 then last_sample_time = now end
    last_sample_game_time = payload.game_time
    last_payload = payload
    return payload
end

-- 供外部/诊断用：上一次采样到现在过了多久
function M.last_sample_age()
    if last_sample_time == 0 then return nil end
    return wall_clock() - last_sample_time
end

return M
