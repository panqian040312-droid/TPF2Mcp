-- One-shot, read-only export of the complete physical railway graph, rail
-- stations and line stop sequences. Kept outside the normal world snapshot so
-- a large map is never rebuilt on the two-second snapshot cadence.
local common = require "tpf2_mcp/collectors/common"

local M = {}
local gui_track_resources = {}

function M.set_track_resources(entries)
    gui_track_resources = {}
    for _, entry in ipairs(entries or {}) do
        if type(entry) == "table" and type(entry.track_type) == "number" and type(entry.file_name) == "string" then
            gui_track_resources[entry.track_type] = { file_name = entry.file_name, speed_limit_mps = entry.speed_limit_mps }
        end
    end
end

local function entity_id(value)
    if value == nil then return nil end
    return tonumber(tostring(value)) or (type(value) == "number" and value or nil)
end

local function number(value)
    return type(value) == "number" and value or nil
end

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

local function position_from_node(value)
    return vec(common.field(value, "position"))
        or vec(common.field(value, "pos"))
        or vec(common.field(common.field(value, "data"), "position"))
        or vec(common.field(common.field(value, "data"), "pos"))
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

local function collect_tracks(errors)
    local nodes, edges, node_cache, track_resource_cache = {}, {}, {}, {}
    local track_resources_loaded = false
    local function load_track_resources()
        if track_resources_loaded then return end
        track_resources_loaded = true
        for index, detail in pairs(gui_track_resources) do track_resource_cache[index] = detail end
        if next(track_resource_cache) ~= nil then return end
        local repository = api and api.res and api.res.trackTypeRep
        local get_all = common.field(repository, "getAll")
        if get_all == nil then return end
        local ok, values = pcall(function() return get_all() end)
        if not ok or values == nil then return end
        for raw_index, file_name in pairs(values) do
            local index = tonumber(raw_index)
            if index ~= nil and type(file_name) == "string" then
                local detail, speed_limit = nil, nil
                local get = common.field(repository, "get")
                if get ~= nil then
                    local detail_ok, value = pcall(function() return get(index) end)
                    if detail_ok then detail = value end
                end
                if detail ~= nil and type(detail.speedLimit) == "number" then speed_limit = detail.speedLimit end
                track_resource_cache[index] = { file_name = file_name, speed_limit_mps = speed_limit }
            end
        end
    end
    local function track_resource(track_type)
        if type(track_type) ~= "number" then return nil end
        load_track_resources()
        if track_resource_cache[track_type] ~= nil then return track_resource_cache[track_type] or nil end
        track_resource_cache[track_type] = false
        return nil
    end
    local function base_node(raw)
        local id = entity_id(raw)
        if id == nil then return nil end
        if node_cache[id] ~= nil then return node_cache[id] or nil end
        local position = position_from_node(common.safe_get_component(raw, "BASE_NODE", errors))
        node_cache[id] = position or false
        return position
    end
    local ok, reason = common.safe_for_each_entity("BASE_EDGE_TRACK", function(edge_entity)
        local base = common.safe_get_component(edge_entity, "BASE_EDGE", errors)
        local track = common.safe_get_component(edge_entity, "BASE_EDGE_TRACK", errors)
        if base == nil or track == nil then return end
        local raw0, raw1 = common.field(base, "node0"), common.field(base, "node1")
        local id0, id1 = entity_id(raw0), entity_id(raw1)
        local p0, p1 = base_node(raw0), base_node(raw1)
        if id0 == nil or id1 == nil or p0 == nil or p1 == nil then return end
        nodes[id0], nodes[id1] = { entity_id = id0, position = p0 }, { entity_id = id1, position = p1 }
        local track_type = number(common.field(track, "trackType"))
        local track_resource_detail = track_resource(track_type)
        local track_resource_file = type(track_resource_detail) == "table" and track_resource_detail.file_name or nil
        local lower_resource_file = type(track_resource_file) == "string" and string.lower(track_resource_file) or ""
        edges[#edges + 1] = {
            entity_id = entity_id(edge_entity), node0 = id0, node1 = id1,
            tangent0 = vec(common.field(base, "tangent0")),
            tangent1 = vec(common.field(base, "tangent1")),
            track_type = track_type,
            track_resource_file = track_resource_file,
            speed_limit_mps = type(track_resource_detail) == "table" and track_resource_detail.speed_limit_mps or nil,
            freestyle_station_track = string.find(lower_resource_file, "lollo_freestyle_train_station", 1, true) ~= nil,
            catenary = common.field(track, "catenary"),
            -- 边结构：GROUND / BRIDGE / TUNNEL。注意这和上面的 track_type 是两回事 ——
            -- track_type 是轨道型号（用来算限速），这个才是"这段是不是在桥/隧道里"。
            -- 判据见 common.structure_of 的注释（游戏自己在 selectortooltip.lua 里就这么判）。
            structure = common.structure_of(common.field(base, "type")),
            structure_index = number(common.field(base, "typeIndex")),
        }
    end, errors)
    if not ok then errors[#errors + 1] = { component = "BASE_EDGE_TRACK", error = tostring(reason) } end
    local ordered_nodes = {}
    for _, node in pairs(nodes) do ordered_nodes[#ordered_nodes + 1] = node end
    table.sort(ordered_nodes, function(a, b) return a.entity_id < b.entity_id end)
    table.sort(edges, function(a, b) return a.entity_id < b.entity_id end)
    return ordered_nodes, edges, nodes
end

local function terminal_key(group_id, station_index, terminal_index)
    return tostring(group_id) .. ":" .. tostring(station_index) .. ":" .. tostring(terminal_index)
end

local function alternative_terminals(stop)
    local result = {}
    for _, value in ipairs(common.sequence_values(common.field(stop, "alternativeTerminals"))) do
        local station_index = number(common.field(value, "station"))
        local terminal_index = number(common.field(value, "terminal"))
        if station_index ~= nil and terminal_index ~= nil then
            result[#result + 1] = { station_index = station_index, terminal_index = terminal_index }
        end
    end
    return result
end

-- 取某点的地形高度（米）。参数形式按游戏源码里的用法逐个试，写法同 layer_terrain.lua。
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

local function collect_stations(track_nodes, track_tangents, errors)
    -- 🔴 车站处的地表高度必须**在站点上直接采样**。前端就是用它判"地下站"的
    -- （埋深 = 地表 - 站台高度，>= 3 m 才算）。别让前端去插地形网格 ——
    -- 那张网格 170 m 一格，落在山谷里的站会被相邻格点的山坡拉高，
    -- 实测 24 个普通站因此被误标成"地下 3~17 m"（2026-09-29 用户报的：
    -- 这个存档一个地下站都没有，唯一那个在另一个存档的 Hanoï）。
    local height_fn = get_height_function()
    local stations, terminal_lookup = {}, {}
    local station_to_construction = nil
    local map_ok, map_or_error = pcall(function()
        return api.engine.system.streetConnectorSystem.getStation2ConstructionMap()
    end)
    if map_ok then
        station_to_construction = map_or_error
    else
        errors[#errors + 1] = { component = "STATION_TO_CONSTRUCTION_MAP", error = tostring(map_or_error) }
    end
    local ok, reason = common.safe_for_each_entity("STATION_GROUP", function(group_entity)
        local group_id = entity_id(group_entity)
        local group = common.safe_get_component(group_entity, "STATION_GROUP", errors)
        if group_id == nil or group == nil then return end
        local center, bounds = bounds_for(group_entity, errors)
        local terminals, child_ids, construction_ids, construction_files = {}, {}, {}, {}
        local seen_construction_ids, seen_construction_files = {}, {}
        for station_offset, station_entity in ipairs(common.sequence_values(common.field(group, "stations"))) do
            local station_index = station_offset - 1
            local station = common.safe_get_component(station_entity, "STATION", errors)
            local station_entity_id = entity_id(station_entity)
            child_ids[#child_ids + 1] = station_entity_id
            local construction_id, construction_file = nil, nil
            if station_to_construction ~= nil then
                local raw_construction_id = common.field(station_to_construction, station_entity)
                    or common.field(station_to_construction, station_entity_id)
                construction_id = entity_id(raw_construction_id)
                if construction_id ~= nil then
                    local construction = common.safe_get_component(construction_id, "CONSTRUCTION", errors)
                    construction_file = common.field(construction, "fileName")
                    if not seen_construction_ids[construction_id] then
                        construction_ids[#construction_ids + 1] = construction_id
                        seen_construction_ids[construction_id] = true
                    end
                    if type(construction_file) == "string" and not seen_construction_files[construction_file] then
                        construction_files[#construction_files + 1] = construction_file
                        seen_construction_files[construction_file] = true
                    end
                end
            end
            for terminal_offset, terminal in ipairs(common.sequence_values(common.field(station, "terminals"))) do
                local terminal_index = terminal_offset - 1
                local vehicle_node = common.field(terminal, "vehicleNodeId")
                local node_id = entity_id(common.field(vehicle_node, "entity"))
                local node = node_id and track_nodes[node_id] or nil
                if node then
                    local item = {
                        station_index = station_index, terminal_index = terminal_index,
                        station_entity_id = station_entity_id, node_id = node_id,
                        position = node.position, cargo = common.field(station, "cargo"),
                        tag = common.field(terminal, "tag"),
                        construction_entity_id = construction_id,
                        construction_file = type(construction_file) == "string" and construction_file or nil,
                        -- 该站台所在轨道边的切向：用来定"铁路走向"（周围地形要沿垂直方向看）
                        tangent = track_tangents ~= nil and track_tangents[node_id] or nil,
                    }
                    terminals[#terminals + 1] = item
                    terminal_lookup[terminal_key(group_id, station_index, terminal_index)] = item
                end
            end
        end
        if #terminals == 0 then return end
        table.sort(construction_ids)
        table.sort(construction_files)
        if center == nil then
            local sx, sy, sz = 0, 0, 0
            for _, terminal in ipairs(terminals) do
                sx, sy, sz = sx + terminal.position.x, sy + terminal.position.y, sz + terminal.position.z
            end
            center = { x = sx / #terminals, y = sy / #terminals, z = sz / #terminals }
        end
        -- 铁路走向（水平单位向量）。站台是长条形：**沿铁路方向地形变化小、垂直方向变化大**，
        -- 所以采周围地形要沿这个方向的**垂线**去采（用户 2026-09-29 指出：均匀圆环把大半
        -- 采样点浪费在"本来就不怎么变"的纵向上）。取该站第一个带切向的站台。
        local axis = nil
        for _, terminal in ipairs(terminals) do
            local tangent = terminal.tangent
            if tangent ~= nil then
                local tx, ty = tangent.x, tangent.y
                local magnitude = math.sqrt(tx * tx + ty * ty)
                if magnitude > 1e-6 then
                    axis = { x = tx / magnitude, y = ty / magnitude }
                    break
                end
            end
        end
        local surface_z = nil
        if center ~= nil and height_fn ~= nil then
            surface_z = sample_height(height_fn, center.x, center.y)
        end
        stations[#stations + 1] = {
            entity_id = group_id,
            name = common.name_from_component(common.safe_get_component(group_entity, "NAME", errors)) or ("Station " .. tostring(group_id)),
            center = center, bounds = bounds, child_station_ids = child_ids,
            construction_entity_ids = construction_ids, construction_files = construction_files,
            axis = axis,
            surface_z = surface_z,
            depth_m = (surface_z ~= nil and center ~= nil) and (surface_z - center.z) or nil,
            terminals = terminals,
        }
    end, errors)
    if not ok then errors[#errors + 1] = { component = "STATION_GROUP", error = tostring(reason) } end
    table.sort(stations, function(a, b) return a.entity_id < b.entity_id end)
    return stations, terminal_lookup
end

-- 采站台周围的**横向 / 纵向地形剖面**。
--
-- 用户（2026-09-29）给了两件事：
--   ① 第三条判据：原版站（下凹 / 上凸）周围高程是**连续变化**的（地形被游戏改造过，
--      有平滑过渡坡）；mod 建的地下站没有这个特征 —— 周围都是**实心土**。
--   ② 采样方式：**站台是长方形的 —— 沿铁路方向变化小、垂直铁路方向变化大**。
--      所以均匀圆环是错的：大半采样点落在"本来就不怎么变"的纵向上。
--
--   ③ 原版站台及其周围地形是**上凸或下凹的梯台**（是分级的平台 + 陡坎，不是平滑斜面）。
--   ④ **必须把"地下站"和"山谷中的车站"分开** —— 两者都表现为"站台比周围低"，
--      但山谷站是露天的自然低地、上空什么都没有；地下站上面盖着东西。
--      **要综合判断，不能凭某一项数据下结论。**
--
-- 四类站在横向剖面上的预期形态（⚠️ **目前是推断**，等真实数据验证后再定阈值）：
--   上凸梯台：中心地表 ≈ 站台高 → 平台 → 陡坎**下降**
--   下凹梯台：中心地表 ≈ 站台高 → 平台 → 陡坎**上升**
--   山谷车站：中心地表 ≈ 站台高 → **平滑连续上升**（没有平台、没有陡坎）
--   地下车站：中心地表**远高于**站台 → 剖面**近乎平坦**（上方是实心土，没有开口）
--
-- ⇒ 改成沿 station.axis 的两条剖面：
--   * lateral（垂直铁路方向）—— **主证据**，两侧各 5 个距离
--   * longitudinal（沿铁路方向）—— **对照**，两侧各 2 个距离，用来验证"纵向变化小"
--   轴取站台轨道边的切向（`station.axis`）；万一拿不到就退回 x 轴，并记 has_axis=false。
--
-- ⚠️ 现成的 170 m 地形网格**分不出这个特征**（实测存档2：地下站周围极差 17.8 m，
--    而几个地面站是 6.3 / 12.5 / 48.8 m，毫无区分度）→ 必须在站点周围自己采。
--
-- 🔴 这一版**只记录原始数值，不下结论**：定性判据要变成阈值，必须先看到真实分布
--    （上一个"手上没有正例就把阈值定了"的亏已经吃过一次：NEAR=10 漏掉了真地下站）。
local function annotate_surroundings(stations, height_fn, errors)
    if height_fn == nil then return nil end
    -- 垂直铁路方向**等间隔密采**。
    -- 用户（2026-09-29）：原版站台周围是"上凸/下凹的**梯台**"（平台 + 陡坎），
    -- 地下站则是埋在地下的**方盒子**（地表近似一条平线）。判"梯台"看的是剖面**形状**，
    -- 而翻倍间距（3,6,10,16,25,40,70）只能看出"总体升高/降低"，描不出台阶。
    local LATERAL = {}
    for distance = 4, 80, 4 do LATERAL[#LATERAL + 1] = distance end   -- 20 个点/侧
    local LONGITUDINAL = { 5, 20 }          -- 沿铁路方向（米），两侧都采（对照）
    -- 环向粗采样：看**各方向的起伏分布**。
    -- 用户（2026-09-29）：「山谷站也有可能会在某个方向出现垂直切面」—— 只看一条横向剖面会被它带偏：
    -- 山谷站靠山那一侧陡得像切面，看上去和"地下站上方被切开"没区别。
    -- 所以还要知道"**是不是只有某一个方向陡**"：只有一侧陡 → 山谷 / 靠山；各方向都平 → 才像地下站。
    local COMPASS = 12                       -- 12 个方向（每 30°）
    local COMPASS_RADII = { 20, 50, 90 }     -- 3 个半径
    local samples = 0
    for _, station in ipairs(stations) do
        local center = station.center
        if center ~= nil then
            local ax = station.axis ~= nil and station.axis.x or 1
            local ay = station.axis ~= nil and station.axis.y or 0
            local px, py = -ay, ax                    -- 铁路走向的左垂线
            local function trace(offsets, ux, uy)
                local profile = {}
                for _, distance in ipairs(offsets) do
                    for _, sign in ipairs({ 1, -1 }) do
                        local value = sample_height(height_fn,
                            center.x + ux * distance * sign, center.y + uy * distance * sign)
                        profile[#profile + 1] = {
                            offset_m = distance * sign,
                            height_m = value ~= nil and math.floor(value * 10 + 0.5) / 10 or nil,
                        }
                        if value ~= nil then samples = samples + 1 end
                    end
                end
                return profile
            end
            -- 环向：12 个方向 × 3 个半径，用来判断"是不是只有一个方向陡"
            local compass = {}
            for index = 0, COMPASS - 1 do
                local angle = index * 2 * math.pi / COMPASS
                local ux, uy = math.cos(angle), math.sin(angle)
                for _, radius in ipairs(COMPASS_RADII) do
                    local value = sample_height(height_fn,
                        center.x + ux * radius, center.y + uy * radius)
                    compass[#compass + 1] = {
                        angle_deg = math.floor(index * (360 / COMPASS) + 0.5),
                        distance_m = radius,
                        height_m = value ~= nil and math.floor(value * 10 + 0.5) / 10 or nil,
                    }
                    if value ~= nil then samples = samples + 1 end
                end
            end
            station.surroundings = {
                has_axis = station.axis ~= nil,
                lateral = trace(LATERAL, px, py),           -- 垂直铁路方向（主）
                longitudinal = trace(LONGITUDINAL, ax, ay), -- 沿铁路方向（对照）
                compass = compass,                          -- 环向：各方向起伏的分布
            }
        end
    end
    return { samples = samples, lateral_offsets = #LATERAL, longitudinal_offsets = #LONGITUDINAL,
             compass_directions = COMPASS, compass_radii = #COMPASS_RADII }
end
--
-- 给每个车站标注"正上方有没有贴地的公路"。
--
-- 为什么要这个：光看"站台比地表低多少"分不开两类东西 ——
--   * 真地下站：站台埋在地下，**上面盖着地面道路/建筑**
--   * 下凹式地面站：站台只是沉在凹地里，**上空是空的**，或者只有很高的桥
-- （判据是用户 2026-09-29 给的：「地下站一般上面还有东西比如建筑和公路且高度贴近地面，
--   如果只是向下凹的地上站一般上空没有东西或者高度很高的桥梁」）
--
-- 所以地下站 = 埋深 > 3 m **且** overhead 有值。
-- 桥和隧道不算：`BASE_EDGE.type` 0 = 地面 / 1 = 桥 / 2 = 隧道，正好把用户说的
-- "很高的桥梁"那种情况排掉 —— 桥虽然也在上方，但它离地面高，站台只是从下面穿过。
--
-- 只查公路。建筑那一路（SIM_BUILDING 在组件视图里没有 position，得走包围盒；
-- CONSTRUCTION 又混着站台自己的模块）先不做，等真需要再说。
local function annotate_overhead(stations, errors)
    local CELL = 50          -- 网格桶边长（米），避免 35 站 × 上万点全表比对
    -- 平面距离阈值（米）。**40 不是拍脑袋**：2026-09-29 在存档2（565 站）上实测，
    -- 唯一的真地下站 Hanoi中央车站（z = −8.04）上方那条地面路在 **33.8 m** 外 ——
    -- 原来定的 10 m 会把它整个漏掉。放宽到 40/50/60 m 都只命中它一个、不多出误报，
    -- 因为真正的门槛是下面的"路要比站台高 3 m"：地面站旁边的路与它同高，天然不满足。
    local NEAR = 40
    local CLEAR = 3          -- 高于站台这么多才叫"盖在上面"
    if errors == nil then errors = {} end

    local buckets = {}
    local street_points = 0
    local ok, reason = common.safe_for_each_entity("BASE_EDGE_STREET", function(edge_entity)
        local base = common.safe_get_component(edge_entity, "BASE_EDGE", errors)
        if base == nil then return end
        -- 用 common.structure_of 而不是自己比数字：判据与游戏自己的 selectortooltip.lua 一致。
        -- 只认 GROUND（真地面道路）；桥和隧道一律跳过 —— 站台在桥底下穿过，
        -- 正是用户说的"高度很高的桥梁"那种情形，不能当作地下站的证据。
        if common.structure_of(common.field(base, "type")) ~= "GROUND" then return end
        for _, key in ipairs({ "node0", "node1" }) do
            local node_entity = common.field(base, key)
            -- 读节点坐标照抄本文件 collect_tracks 的既有写法（position_from_node 封装了字段形态差异），
            -- 别自己拼 common.field(node, "position")。
            local position = node_entity ~= nil
                and position_from_node(common.safe_get_component(node_entity, "BASE_NODE", errors)) or nil
            if position ~= nil then
                local bucket = math.floor(position.x / CELL) .. ":" .. math.floor(position.y / CELL)
                local list = buckets[bucket]
                if list == nil then list = {}; buckets[bucket] = list end
                list[#list + 1] = position
                street_points = street_points + 1
            end
        end
    end, errors)
    if not ok then
        errors[#errors + 1] = { component = "BASE_EDGE_STREET", error = "overhead scan failed: " .. tostring(reason) }
    end

    local covered, checked = 0, 0
    for _, station in ipairs(stations) do
        local center = station.center
        if center ~= nil then
            checked = checked + 1
            local found = nil
            local ci, cj = math.floor(center.x / CELL), math.floor(center.y / CELL)
            for di = -1, 1 do
                for dj = -1, 1 do
                    local list = buckets[(ci + di) .. ":" .. (cj + dj)]
                    if list ~= nil then
                        for _, point in ipairs(list) do
                            local dx, dy = point.x - center.x, point.y - center.y
                            if (dx * dx + dy * dy) <= NEAR * NEAR and point.z > center.z + CLEAR then
                                found = "road"
                                break
                            end
                        end
                    end
                    if found ~= nil then break end
                end
                if found ~= nil then break end
            end
            station.overhead = found
            if found ~= nil then covered = covered + 1 end
        end
    end

    return { street_points = street_points, stations_checked = checked, stations_covered = covered }
end

local function collect_lines(terminal_lookup, errors)
    local lines = {}
    local ok, reason = common.safe_for_each_entity("LINE", function(line_entity)
        local line_id = entity_id(line_entity)
        local component = common.safe_get_component(line_entity, "LINE", errors)
        if line_id == nil or component == nil then return end
        local stops, all_rail = {}, true
        for offset, stop in ipairs(common.sequence_values(common.field(component, "stops"))) do
            local group_id = entity_id(common.field(stop, "stationGroup"))
            local station_index = number(common.field(stop, "station")) or 0
            local terminal_index = number(common.field(stop, "terminal")) or 0
            local terminal = terminal_lookup[terminal_key(group_id, station_index, terminal_index)]
            if terminal == nil then all_rail = false end
            stops[#stops + 1] = {
                sequence_index = offset - 1, station_group_id = group_id,
                station_index = station_index, terminal_index = terminal_index,
                alternative_terminals = alternative_terminals(stop),
                node_id = terminal and terminal.node_id or nil,
            }
        end
        if all_rail and #stops >= 2 then
            lines[#lines + 1] = {
                entity_id = line_id,
                name = common.name_from_component(common.safe_get_component(line_entity, "NAME", errors)) or ("Line " .. tostring(line_id)),
                stops = stops,
            }
        end
    end, errors)
    if not ok then errors[#errors + 1] = { component = "LINE", error = tostring(reason) } end
    table.sort(lines, function(a, b) return a.entity_id < b.entity_id end)
    return lines
end

local function collect_depots(lines, errors)
    local line_ids, depots_by_id, depots = {}, {}, {}
    for _, line in ipairs(lines) do line_ids[line.entity_id] = true end
    local vehicle_system = common.field(api.engine and api.engine.system, "transportVehicleSystem")
    local get_depot_vehicles = common.field(vehicle_system, "getDepotVehicles")
    local ok, reason = common.safe_for_each_entity("VEHICLE_DEPOT", function(depot_entity)
        local depot_id = entity_id(depot_entity)
        if depot_id == nil then return end
        local center, bounds = bounds_for(depot_entity, errors)
        local construction = common.safe_get_component(depot_entity, "CONSTRUCTION", errors)
        local construction_file = common.field(construction, "fileName")
        local lower_file = type(construction_file) == "string" and string.lower(construction_file) or ""
        local file_classifies_rail = (string.find(lower_file, "train", 1, true) ~= nil
            or string.find(lower_file, "rail", 1, true) ~= nil)
            and string.find(lower_file, "tram", 1, true) == nil
        local parked_vehicle_ids, parked_source = {}, "UNKNOWN"
        if get_depot_vehicles ~= nil then
            local call_ok, values = pcall(function() return get_depot_vehicles(depot_entity) end)
            if call_ok then
                for _, value in ipairs(common.sequence_values(values)) do
                    local vehicle_id = entity_id(value)
                    if vehicle_id ~= nil then parked_vehicle_ids[#parked_vehicle_ids + 1] = vehicle_id end
                end
                parked_source = "TRANSPORT_VEHICLE_SYSTEM_GET_DEPOT_VEHICLES"
            end
        end
        local item = {
            entity_id = depot_id,
            name = common.name_from_component(common.safe_get_component(depot_entity, "NAME", errors)) or ("Depot " .. tostring(depot_id)),
            center = center, bounds = bounds,
            construction_file = type(construction_file) == "string" and construction_file or nil,
            assigned_vehicle_ids = {}, rail_assigned_vehicle_ids = {},
            parked_vehicle_ids = parked_vehicle_ids,
            parked_vehicle_count_source = parked_source,
            rail_candidate = file_classifies_rail,
            rail_classification_source = file_classifies_rail and "CONSTRUCTION_FILE_CLASSIFIED" or "UNKNOWN",
        }
        depots[#depots + 1] = item
        depots_by_id[depot_id] = item
    end, errors)
    if not ok then errors[#errors + 1] = { component = "VEHICLE_DEPOT", error = tostring(reason) } end

    -- TRANSPORT_VEHICLE.depot is observed on active vehicles too.  Therefore
    -- this is an assignment count, not a claim that the vehicles are parked.
    common.safe_for_each_entity("TRANSPORT_VEHICLE", function(vehicle_entity)
        local vehicle = common.safe_get_component(vehicle_entity, "TRANSPORT_VEHICLE", errors)
        local depot = depots_by_id[entity_id(common.field(vehicle, "depot"))]
        if depot == nil then return end
        local vehicle_id = entity_id(vehicle_entity)
        depot.assigned_vehicle_ids[#depot.assigned_vehicle_ids + 1] = vehicle_id
        if line_ids[entity_id(common.field(vehicle, "line"))] then
            depot.rail_assigned_vehicle_ids[#depot.rail_assigned_vehicle_ids + 1] = vehicle_id
            depot.rail_candidate = true
            if depot.rail_classification_source == "UNKNOWN" then
                depot.rail_classification_source = "ASSIGNED_RAIL_LINE_VEHICLE"
            end
        end
    end, errors)
    table.sort(depots, function(a, b) return a.entity_id < b.entity_id end)
    return depots
end

function M.collect()
    local errors = {}
    local nodes, edges, node_map = collect_tracks(errors)
    -- 节点 → 该处轨道走向（切向）。站台周围要沿"垂直铁路方向"采剖面，先在这里把方向备好。
    local node_tangent = {}
    for _, edge in ipairs(edges) do
        if edge.tangent0 ~= nil then node_tangent[edge.node0] = edge.tangent0 end
        if edge.tangent1 ~= nil then node_tangent[edge.node1] = edge.tangent1 end
    end
    local stations, terminal_lookup = collect_stations(node_map, node_tangent, errors)
    -- 标注"正上方有没有贴地公路"：把真地下站和"下凹式地面站"分开的关键一步
    local overhead = annotate_overhead(stations, errors)
    -- 站台周围一圈的地形高度（第三条判据的原始数据，先只采不判）
    local surroundings = annotate_surroundings(stations, get_height_function(), errors)
    local lines = collect_lines(terminal_lookup, errors)
    local depots = collect_depots(lines, errors)
    -- 地面 / 桥 / 隧道各多少条。前端靠它判断这层有没有结构信息（旧版数据没有这个字段）。
    local structures = {}
    for index = 1, #edges do
        local name = edges[index].structure or "UNKNOWN"
        structures[name] = (structures[name] or 0) + 1
    end
    return {
        schema_version = 1, status = "OK", source_status = "ENGINE_OBSERVED",
        nodes = nodes, edges = edges, stations = stations, lines = lines, depots = depots,
        structures = structures,
        counts = { nodes = #nodes, edges = #edges, stations = #stations, lines = #lines, depots = #depots },
        errors = errors, write_command_sent = false,
        overhead_diagnostics = overhead,
        surroundings_diagnostics = surroundings,
    }
end

return M
