-- 产业链物流关系采集器（只读）
--
-- 用户诉求（2026-09-30 原话）：
--   「我希望是我选中某个产业的时候把相关联的上下游高亮并显示物料流向和关联交通」
--   「最终货物是送达城镇的，然后货物最终会在城镇消失」
--
-- 🔴 2026-09-30 傍晚**修正了边的终点**（用户定调）：「只划到对应的车站就可以了」
--   ⇒ 边的终点从"城镇"改成**车站**。理由两条：
--     ① 车站坐标是现成的 —— layer-stations.json 565 个站都带 position；
--     ② 城镇侧的坐标在游戏数据里**没有已知来源** —— SIM_BUILDING 全图只有 215 个、
--        且全是产业（实测），城镇建筑走的是 TownBuilding 组件，本项目尚未采。
--   车站由 (line, lineStop1) 决定，详见 ③ 段「目的地车站」那段注释。
--
-- 🔴 字段语义已**实测确认**（2026-09-30，零误差）—— 这是本文件存在的全部依据：
--   SIM_CARGO.sourceEntity  == 产业的 SIM_BUILDING.stockList
--                              （实测 97 / 97 全部命中，无一例外）
--   SIM_CARGO.targetEntity  == 产业的 stock（实测 43 / 563，即"厂 → 厂"原料链）
--                            | 其余 520 个不是产业 stock ⇒ 城镇（终端消费，货在城镇消失）
--   SIM_CARGO.cargoType     == 货物类型；tostring 得到可读名（"FOOD" / "PLASTIC" / "CRUDE"）
--   ⇒ **关键认知**：cargo 里的 source / target **不是产业实体本身，是产业的库存(stock)实体**。
--     所以本采集器必须同时输出产业侧索引（stock → industry），前端才能把 stock 翻回产业。
--     （曾经绕过的弯路：直接拿 sourceEntity 去 get_industry 查 —— 全部 ENTITY_NOT_FOUND，
--      因为 id 空间就不一样。别再走这条。）
--
-- 官方依据（api.type 的 SimCargo / SimCargoAtTerminal）：
--   SimCargo: cargoType int（never 0）/ targetEntity Entity / sourceEntity Entity /
--             speed float / vehicleUsed bool / startTime int（生产时间戳）
--   SimCargoAtTerminal: edgeId（the edge the cargo is currently using）/ place int
--
-- ⚠️ 与 collectors/demand_probe.lua 的分工（别搞混）：
--   demand_probe 挂 SimCargoSystem.OnToArriveAtDestination 事件，累计的是"**已抵达**"的货；
--   本采集器**全量遍历当前存在的 SIM_CARGO**（在途 + 站台等待 + 车上），
--   拿的是"**此刻的物流关系图**" —— 只有它才能直接拿来画连线。
--
-- 关联交通（用户明确要的第三项）：
--   货在当前车上 → SIM_ENTITY_AT_VEHICLE.vehicle → 车辆（车辆→线路由前端用 layer-vehicles 拼）
--   货在站台等   → SIM_ENTITY_AT_TERMINAL.line   → 线路
--   （线路名、车辆名都由前端从已有图层取，这里只给 id，不重复读组件。）
--
-- 输出：bridge/layer-freight.json（geometry_kind = "LINK"）

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

-- 上限：本存档当前在途货量约两万，留足余量。超过就截断并标 truncated（在 counts 里）。
-- ⚠️ 2026-09-30 实况：cargo_total = 201735（已触顶截断）。含大量"未开始运输"的货，
--    所以 CARGO_LIMIT 若还要放大，必须先评估 duration_ms（当时 2.97 s / every=9000）。
local CARGO_LIMIT = 200000
-- 单条边保留多少辆车 / 条线路样本：防某条大流量边把 JSON 撑爆（前端只需要"这条线上有车"）
local VEHICLE_SAMPLE = 8
local LINE_SAMPLE = 8
-- 单条边保留多少个 "(线路, 上车站, 下车站)" 组合。前端靠它定位"对应的车站"。
local STOPPING_SAMPLE = 16

local SILENT = setmetatable({}, { __index = function() return true end })

-- 读一个 vec3 字段（x/y/z）。z 缺省补 0。取法照 layer_industry.lua，保持一致。
local function vec_at(value)
    if value == nil then return nil end
    local x = common.field(value, "x")
    local y = common.field(value, "y")
    local z = common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

-- 按 id 取实体。⚠️ 只能用 game.interface.getEntity(id)（项目里 demand_probe / context_probe
-- / dynamic_probe 三处先例）；api.engine.getEntity(edgeId, cargoType) 是**完全不同的东西**
-- （官方定义："Gets one (random) entity from the cargo waiting"），不要混用。
local function entity_by_id(id)
    if type(id) ~= "number" then return nil end
    local ok, entity = pcall(function() return game.interface.getEntity(id) end)
    if ok then return entity end
    return nil
end

-- 取实体句柄的数值 id。字段可能是 number、也可能是单元素序列/map（引擎绑定不一致），
-- 所以三条路都试，全部包 pcall —— 拿不到就返回 nil，绝不让采集器崩。
local function first_id(value)
    if value == nil then return nil end
    local direct = tonumber(tostring(value))
    if direct ~= nil then return direct end
    local ok_seq, seq_hit = pcall(function()
        for _, item in ipairs(value) do
            local n = tonumber(tostring(item))
            if n ~= nil then return n end
        end
    end)
    if ok_seq and seq_hit ~= nil then return seq_hit end
    local ok_map, map_hit = pcall(function()
        for _, item in pairs(value) do
            local n = tonumber(tostring(item))
            if n ~= nil then return n end
        end
    end)
    if ok_map then return map_hit end
    return nil
end

-- 把去重桶转成排好序的定长数组（桶是 string→true 的 map，为了去重）
local function bucket_to_array(bucket, limit)
    local out = {}
    for key in pairs(bucket) do
        if #out >= limit then break end
        out[#out + 1] = tonumber(key) or key
    end
    table.sort(out, function(a, b) return tostring(a) < tostring(b) end)
    return out
end

-- 站点桶 → 数组。桶里装的是 { line, wait_stop, dest_stop } 记录（去重靠调用方给的 key）。
-- 排序只为输出稳定（便于 diff 两次采集的差异），不代表业务优先级。
local function stopping_bucket_to_array(bucket, limit)
    local out = {}
    for _, item in pairs(bucket) do
        if #out >= limit then break end
        out[#out + 1] = item
    end
    table.sort(out, function(a, b)
        if a.line ~= b.line then return tostring(a.line) < tostring(b.line) end
        if a.dest_stop ~= b.dest_stop then return a.dest_stop < b.dest_stop end
        return a.wait_stop < b.wait_stop
    end)
    return out
end

function M.collect()
    local errors = {}
    local started = common.clock()

    -- ── ① 产业索引：stock id → 产业 id ────────────────────────────────────────
    -- cargo 的 source/target 存的是 stock id，必须靠这张表翻回产业。
    -- 用 component_access.get 而不是普通读，跟 layer_industry.lua 保持同一取法，
    -- 保证两边看到的 stockList 是同一个值（否则反查会错位）。
    local stock_to_industry = {}
    local industry_count = 0
    local no_stock = 0
    local ok_index, index_count = common.safe_for_each_entity("SIM_BUILDING", function(entity)
        local building = component_access.get(entity, "SIM_BUILDING")
        if building == nil then return end
        industry_count = industry_count + 1
        local industry_id = common.entity_id(entity)
        local stock = first_id(common.field(building, "stockList"))
        if stock == nil then
            no_stock = no_stock + 1
            return
        end
        stock_to_industry[tostring(stock)] = industry_id
    end, errors)

    if not ok_index then
        return {
            status = "ERROR",
            source_status = "ENGINE_OBSERVED",
            error = tostring(index_count),
            errors = errors,
        }
    end

    -- ── ② 全量遍历 SIM_CARGO，按 (source, target, cargoType) 聚合成边 ────────
    local links = {}
    local cargo_scanned = 0
    local truncated = false
    local unresolved_source, unresolved_target, missing_pair = 0, 0, 0
    local onboard_total, waiting_total, other_total = 0, 0, 0
    local sample = nil

    local ok_cargo, cargo_count = common.safe_for_each_entity("SIM_CARGO", function(entity)
        if cargo_scanned >= CARGO_LIMIT then truncated = true; return end
        cargo_scanned = cargo_scanned + 1

        local cargo = common.safe_get_component(entity, "SIM_CARGO", SILENT)
        if cargo == nil then missing_pair = missing_pair + 1; return end

        local source = first_id(common.field(cargo, "sourceEntity"))
        local target = first_id(common.field(cargo, "targetEntity"))
        if source == nil or target == nil then missing_pair = missing_pair + 1; return end

        local type_raw = common.field(cargo, "cargoType")
        local type_name = type_raw ~= nil and tostring(type_raw) or "UNKNOWN"

        local source_industry = stock_to_industry[tostring(source)]
        local target_industry = stock_to_industry[tostring(target)]
        if source_industry == nil then unresolved_source = unresolved_source + 1 end
        if target_industry == nil then unresolved_target = unresolved_target + 1 end

        local key = tostring(source) .. "|" .. tostring(target) .. "|" .. type_name
        local link = links[key]
        if link == nil then
            link = {
                source_stock = source,
                source_industry = source_industry,
                target = target,
                target_industry = target_industry,
                -- 判据：目标能在产业索引里查到就是"厂→厂"，否则是"厂→城镇"（货在此消失）
                target_kind = target_industry ~= nil and "industry" or "town",
                cargo_type = type_name,
                count = 0, onboard = 0, waiting = 0, other = 0,
                vehicles_bucket = {}, lines_bucket = {}, stopping_bucket = {},
                first_start_time = nil, last_start_time = nil,
            }
            links[key] = link
        end
        link.count = link.count + 1

        -- 生产时间戳跨度：前端可据此看"这条流向的货从什么时候开始积压"
        local start_time = common.field(cargo, "startTime")
        if type(start_time) == "number" then
            if link.first_start_time == nil or start_time < link.first_start_time then
                link.first_start_time = start_time
            end
            if link.last_start_time == nil or start_time > link.last_start_time then
                link.last_start_time = start_time
            end
        end

        -- 关联交通：车上 → 车辆；站台 → 线路。两者都没有就归 other。
        local at_vehicle = common.safe_get_component(entity, "SIM_ENTITY_AT_VEHICLE", SILENT)
        local vehicle = at_vehicle ~= nil and first_id(common.field(at_vehicle, "vehicle")) or nil
        local at_terminal = nil
        if vehicle ~= nil then
            link.onboard = link.onboard + 1
            onboard_total = onboard_total + 1
            link.vehicles_bucket[tostring(vehicle)] = true
        else
            at_terminal = common.safe_get_component(entity, "SIM_ENTITY_AT_TERMINAL", SILENT)
            local line = at_terminal ~= nil and first_id(common.field(at_terminal, "line")) or nil
            if line ~= nil then
                link.waiting = link.waiting + 1
                waiting_total = waiting_total + 1
                link.lines_bucket[tostring(line)] = true
            else
                link.other = link.other + 1
                other_total = other_total + 1
            end
        end

        -- ── 目的地车站（用户 2026-09-30 定调：「只划到对应的车站就可以了」）──────────
        -- 边的终点不再指向城镇，而是**车站**。车站由这对字段决定：
        --   line      = 货正在等 / 正在乘的线路实体
        --   lineStop0 = 当前所在站点（等车的那个站）
        --   lineStop1 = 将要下车的站点  ← 官方原文 "the stop the entity will get off the vehicle"
        -- 两个 stop 都是 **Line.stops 数组的相对下标**（不是车站 id），所以前端要拿
        -- layer-lines.json 里该线路的站点序列去解，再到 layer-stations.json 取车站坐标。
        -- 官方依据：api.type 的 SimEntityAtTerminal / SimEntityAtVehicle 字段表（两者字段相同）。
        -- ⚠️ other 类（既不在车上也不在站台）拿不到线路 —— 那批货还没开始运输。
        local carrier = at_vehicle or at_terminal
        if carrier ~= nil then
            local cline = first_id(common.field(carrier, "line"))
            if cline ~= nil then
                local wait_stop = tonumber(tostring(common.field(carrier, "lineStop0")))
                local dest_stop = tonumber(tostring(common.field(carrier, "lineStop1")))
                -- 两个下标都合法才记（nil / -1 表示此刻还没有目的地）
                if wait_stop ~= nil and dest_stop ~= nil and wait_stop >= 0 and dest_stop >= 0 then
                    local skey = tostring(cline) .. "|" .. tostring(wait_stop) .. "|" .. tostring(dest_stop)
                    if link.stopping_bucket[skey] == nil then
                        link.stopping_bucket[skey] = {
                            line = cline,
                            wait_stop = wait_stop,
                            dest_stop = dest_stop,
                            onboard = vehicle ~= nil,
                        }
                    end
                end
            end
        end

        -- 留一条完整样本供排查（只有第一条，避免体积）
        if sample == nil then
            sample = {
                entity_id = common.entity_id(entity),
                source_stock = source,
                source_industry = source_industry,
                target = target,
                target_industry = target_industry,
                cargo_type = type_name,
                start_time = start_time,
                speed = common.field(cargo, "speed"),
                vehicle_used = common.field(cargo, "vehicleUsed"),
                at_vehicle = vehicle,
            }
        end
    end, errors)

    -- ── ③ 收尾：桶转数组、排序、输出 ─────────────────────────────────────────
    local out_links = {}
    local industry_only, town_only = 0, 0
    local links_with_stops, stopping_total = 0, 0
    for _, link in pairs(links) do
        link.vehicles = bucket_to_array(link.vehicles_bucket, VEHICLE_SAMPLE)
        link.lines = bucket_to_array(link.lines_bucket, LINE_SAMPLE)
        -- stopovers = [(线路, 上车站, 下车站)] —— 前端靠它把边的终点落到**车站**上
        link.stopovers = stopping_bucket_to_array(link.stopping_bucket, STOPPING_SAMPLE)
        link.vehicles_bucket = nil
        link.lines_bucket = nil
        link.stopping_bucket = nil
        if #link.stopovers > 0 then
            links_with_stops = links_with_stops + 1
            stopping_total = stopping_total + #link.stopovers
        end
        if link.target_kind == "industry" then industry_only = industry_only + 1 else town_only = town_only + 1 end
        out_links[#out_links + 1] = link
    end
    -- 按流量降序 —— 前端默认先看大流量
    table.sort(out_links, function(a, b)
        if a.count ~= b.count then return a.count > b.count end
        if a.cargo_type ~= b.cargo_type then return a.cargo_type < b.cargo_type end
        return tostring(a.source_stock) < tostring(b.source_stock)
    end)

    local industry_index = {}
    for stock_key, industry_id in pairs(stock_to_industry) do
        industry_index[#industry_index + 1] = {
            stock = tonumber(stock_key) or stock_key,
            industry = industry_id,
        }
    end
    table.sort(industry_index, function(a, b)
        return tostring(a.industry) < tostring(b.industry)
    end)

    -- ── ④ 坐标：本采集器**不再自己取**（2026-09-30 变更）────────────────────────
    -- 用户定调「只划到对应的车站就可以了」之后，边的两端坐标都能从**已有图层**直接取，
    -- 本采集器不必再取一遍：
    --     产业端 → layer-industry.json 的 `points`（215 个点，带 entity_id + position 真坐标）
    --     车站端 → layer-stations.json 的 `stations[].position`（565 个站）
    -- 旧实现试图自己取：拿 **stock id** 去 game.interface.getEntity() 取 BOUNDING_VOLUME ——
    -- 取不到，因为 **stock id 不是实体 id**（id 空间不同）。结果 `nodes` 恒为 0、3989 次 pcall 全废。
    -- 这条路已废弃，不要重走。（`entity_by_id` / `vec_at` 两个函数先留着，将来若要去采
    -- TownBuilding 的城镇坐标还能复用。）
    --
    -- ⚠️ 仍无解的一块：target 不是产业 stock 的那 4138 条边（交接 5 称"城镇消费端"）。
    --    游戏里 SIM_BUILDING 全图只有 215 个且**全是产业**，城镇建筑走的是 TownBuilding 组件，
    --    本项目尚未采。所以"厂→城镇"这条线目前没有坐标源 —— 这正是改用车站终点的原因。

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        -- 前端据此决定画法：这是一层"关系边"，不是点也不是路网
        geometry_kind = "LINK",
        -- 坐标说明：本层**故意不给坐标**。前端取法见 ④ 段注释 ——
        --   产业端 → layer-industry.json 的 points（按 source_industry / target_industry 的实体 id 对）
        --   车站端 → layer-stations.json 的 stations[].position（按 stopovers 的 (line, dest_stop) 解）
        coord_source = "external: layer-industry.json / layer-stations.json",
        counts = {
            industries = industry_count,
            stock_index = #industry_index,
            industries_without_stock = no_stock,
            cargo_scanned = cargo_scanned,
            cargo_total = ok_cargo and cargo_count or nil,
            links = #out_links,
            links_to_industry = industry_only,
            links_to_town = town_only,
            -- 能落到车站上的边数 / 站点组合总数。其余边是"还没开始运输"的货（拿不到线路）。
            links_with_stops = links_with_stops,
            stopping_total = stopping_total,
            onboard = onboard_total,
            waiting = waiting_total,
            other = other_total,
            unresolved_source = unresolved_source,
            unresolved_target = unresolved_target,
            missing_pair = missing_pair,
            truncated = truncated,
        },
        duration_ms = (common.clock() - started) * 1000,
        sample = sample,
        industry_index = industry_index,
        links = out_links,
        errors = errors,
    }
end

return M
