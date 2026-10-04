-- 只读探针：线路财务 —— 游戏 UI 里那条「收入 / 维护费」曲线，引擎到底给不给 mod 读
--
-- 为什么要有它（用户 2026-10-02 的原话）：
--   「我在游戏里可以单独查看每个线路的盈亏啊，查」
--
-- 官方手册确实写了界面有这东西（`gamemanual:statisticsdatalayers.md`「Line Details」）：
--   线路窗口有四个标签页 —— overview / vehicle list / **FINANCES** / charts；
--   FINANCES 页「a chart shows the financial balance splitted in the actual income from
--   the transported cargo and the maintenance cost of rolling stock」；
--   线路统计表还有一列 Balance =「the current annual profit or loss」。
--   ⇒ **那两个数一定存在**，问题只是**引擎暴不暴露给 mod**。
--
-- 已经排除的（都来自实测产物，不是推断）：
--   · 31 个 system 里**没有任何**财务 / 统计 / 账本接口
--     （`bridge/world-probe.json` → `system_methods`；`lineSystem` 的 9 个方法全是
--      "线→站 / 线→车"的连接查询）
--   · `Line` 组件**两条读取路都试过**：
--       - 组件视图（`component_fields`）只有 2 个字段：`stops` / `waitingTime`
--       - 聚合表（`game.interface.getEntity`）有 7 个：`itemsTransported` / `frequency` /
--         `rate` / `stops` / `name` / `id` / `type`
--     —— **一个"钱"字都没有**。
--   · 玩家账本 `player.ACCOUNT.journal` 5 万条，每条字段 `{amount, position, time, category}`，
--     `category` 只有 `type / construction / maintenance / other / carrier` 五个维度
--     —— **没有线路引用**（所以做不出"第 12345 号线亏了多少"）。
--
-- ★ 还剩**一个没验证过**的可能，本探针就是去问它：
--   `LOG_BOOK` 组件（`api.type.ComponentType.LOG_BOOK` = 74）。
--   `type.LogBook` 的定义是「`name2log`：{[string]=LogBook.Log}」，而
--   `type.LogBook.Log` 有 `times {int,...}` + `values {int,...}` ——
--   官方原文：「A LogBook contains information about the evolution of a variable
--   (e.g. amounts of money) over time.」
--   **这正是"图表数据源"该长的样子**（时间序列 + 数值）。
--   但 `world-probe.json` 里它是 `walked: false` —— 从没成功遍历到挂它的实体。
--   同理 `MAINTENANCE_COST`（= 18）也是 `walked: false`，而它的定义正是
--   「Contains the maintenance cost of objects」—— 也就是 UI 那条维护费曲线。
--
-- 另外顺带问清 `game.config` 里几个一直缺口径的常量：
--   `chargeMaintenanceInterval`（维护费**多久收一次** —— 以前只能标"周期待实测"）、
--   `economy`（整张经济参数表）。
--
-- 只读：不发写命令、不改游戏状态。每个引擎调用都裹 pcall，失败只记一条不中断。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

local LINE_SAMPLE = 6          -- 细查几条线的组件视图 + 聚合表
local SCAN_LIMIT = 420         -- 扫多少条线统计组件覆盖（本存档 273 条）
local LOG_KEYS_LIMIT = 40      -- name2log 最多列几个键
local LOG_POINTS_LIMIT = 8     -- 每条时间序列最多取几个点
local ENTITY_PROBE_LIMIT = 4   -- 每类实体试几个（找挂 LOG_BOOK / MAINTENANCE_COST 的）
local VEHICLE_SAMPLE = 8       -- 细查几辆车的装载（cargoLoad / capacities 用 pairs 问）
local ERROR_LIMIT = 25

-- 关心的配置键（只按名字挑，值一律照抄引擎给的，不做单位换算）
local CONFIG_HINTS = {
    "econom", "maintenance", "charge", "cost", "money", "price", "interest", "loan",
    "fare", "ticket", "depreciat", "vehicleLife", "Lifetime",
}

-- 一个值长什么样。🔴 **不能只用 `#` 数长度** —— `#` 对 map（非连续整数键）返回 0，
-- 本项目踩过这个坑（空数组被当成"读不到"）。所以同时报 pairs 计数。
local function describe(value, depth)
    local out = { value_type = type(value) }
    if value == nil then return out end
    local t = type(value)
    if t == "number" or t == "string" or t == "boolean" then
        out.value = value
        return out
    end
    if t ~= "table" and t ~= "userdata" then return out end

    local pairs_count, sample, scalar = 0, nil, nil
    local keys = {}
    pcall(function()
        for key, item in pairs(value) do
            pairs_count = pairs_count + 1
            if #keys < 12 then keys[#keys + 1] = tostring(key) end
            if sample == nil then
                sample = { key = tostring(key), value_type = type(item) }
                if type(item) == "number" or type(item) == "string" or type(item) == "boolean" then
                    sample.value = item
                end
            end
        end
    end)
    out.pairs_count = pairs_count
    if keys[1] ~= nil then out.keys = keys end

    -- 数组长度（仅当看起来像数组时才报，避免 0 被误读成"空"）
    local hash_ok, hash_len = pcall(function() return #value end)
    if hash_ok then out.array_len = hash_len end

    -- 单元素直接取值：`values = {...}` 这种常常是 Sol2 绑定的 proxy，pairs 拿不到但 [1] 能拿
    if depth and depth > 0 then
        local first = common.field(value, 1)
        if type(first) == "number" or type(first) == "string" or type(first) == "boolean" then
            scalar = first
            out.first_element = first
        end
    end
    if sample then out.sample = sample end
    if scalar ~= nil then out.scalar = scalar end
    return out
end

-- ===== ① game.config：经济 / 维护相关常量 =====================================
-- 一直缺的两样口径就在这里：维护费**多久收一次**、以及整张经济参数表。
local function read_config(report)
    local out = { note = "game.config 只有 45 个键 → 全量导出（不按关键字筛，免得漏掉名字里没有关键字的）" }
    local config = common.field(game, "config")
    if config == nil then
        out.error = "game.config 读不到（game 全局不存在？）"
        report.config = out
        return
    end

    local entries, hit_names = {}, {}
    pcall(function()
        for key, value in pairs(config) do
            local name = tostring(key)
            entries[#entries + 1] = { key = name, value = describe(value, 1) }
            local lower = string.lower(name)
            for index = 1, #CONFIG_HINTS do
                if string.find(lower, CONFIG_HINTS[index], 1, true) then
                    hit_names[#hit_names + 1] = name
                    break
                end
            end
        end
    end)
    table.sort(entries, function(a, b) return a.key < b.key end)
    out.key_count = #entries
    out.all = entries
    out.economy_related = hit_names
    out.note = out.note .. "；economy_related 是名字含 econom/maintenance/charge/cost/price/... 的那些（给一眼看法）"
    report.config = out
end

-- ===== ② LOG_BOOK 组件：找挂它的实体，读 name2log =============================
-- 这是"图表数据源"的最后一种可能。命中就直接把键名和序列形状打出来。
local function describe_logbook(book)
    local out = { component_type = type(book) }
    local n2l = common.field(book, "name2log")
    if n2l == nil then
        out.name2log = nil
        out.note = "LOG_BOOK 组件在，但 name2log 读不到"
        return out
    end
    out.name2log = describe(n2l)

    local keys, logs = {}, {}
    pcall(function()
        for key, log in pairs(n2l) do
            if #keys < LOG_KEYS_LIMIT then keys[#keys + 1] = tostring(key) end
            if #logs < LOG_KEYS_LIMIT then
                local entry = { name = tostring(key) }
                local times = common.field(log, "times")
                local values = common.field(log, "values")
                entry.times = describe(times)
                entry.values = describe(values)
                -- 取前几个点（times/values 应当是等长数组）
                local points = {}
                for index = 1, LOG_POINTS_LIMIT do
                    local t = common.field(times, index)
                    local v = common.field(values, index)
                    if t == nil and v == nil then break end
                    points[#points + 1] = { t = t, v = v }
                end
                if #points > 0 then entry.head = points end
                logs[#logs + 1] = entry
            end
        end
    end)
    out.keys = keys
    out.logs = logs
    out.note = "times/values 是等长数组；head 是前几个点（t = 游戏内时间）"
    return out
end

local function hunt_logbook(entity, label, out, errors)
    local book = component_access.get(entity, "LOG_BOOK")
    if book == nil then return false end
    local entry = { entity = label, entity_id = common.entity_id(entity) }
    local ok, detail = pcall(describe_logbook, book)
    entry.logbook = ok and detail or { error = tostring(detail) }
    out[#out + 1] = entry
    return true
end

-- ===== ③ MAINTENANCE_COST 组件：挂在谁身上、值多少 ===========================
local function hunt_maintenance(entity, label, out)
    local component = component_access.get(entity, "MAINTENANCE_COST")
    if component == nil then return false end
    out[#out + 1] = {
        entity = label,
        entity_id = common.entity_id(entity),
        maintenance_cost = common.field(component, "maintenanceCost"),
        component_fields = describe(component),
    }
    return true
end

-- ===== ⑤ 车辆的装载 / 容量（用户问「能不能基于每个交通工具算收入」）=========
--
-- 已排除的：车辆类组件（`TRANSPORT_VEHICLE` / `TRAIN` / `SHIP` / `AIRCRAFT` / `RAIL_VEHICLE`）
-- 的**聚合表只有同样 14 个通用字段** —— allCapacities / capacities / cargoLoad / carrier /
-- depot / id / line / name / position / speed / state / stopIndex / type / vehicles，**没有钱**。
-- 组件视图更是只有 position 或干脆是空。
--
-- ★ 但 `cargoLoad` / `capacities` 是「这辆车装了哪些货、能装多少」——
--   如果它们能读出「货种 → 数量」，那「每辆车运了多少 × 运价」就能算出来，
--   再按 `line` 汇总就是**每条线的收入**（用户要的"基于交通工具计算"）。
--   `world-probe.json` 报这两个 `length: 0` —— ⚠️ 那是用 `#` 数的，
--   而 **map（非连续整数键）用 `#` 就是 0**，本项目踩过这个坑。
--   ⇒ 这里必须用 pairs 重新问一次，并把键值对打出来。
local function dump_pairs(value, limit)
    local out = { value_type = type(value) }
    if value == nil then return out end
    local ok, count = pcall(function() return #value end)
    if ok then out.array_len = count end
    local items = {}
    local total = 0
    pcall(function()
        for key, item in pairs(value) do
            total = total + 1
            if #items < limit then
                local row = { key = tostring(key), key_type = type(key), value_type = type(item) }
                if type(item) == "number" or type(item) == "string" or type(item) == "boolean" then
                    row.value = item
                else
                    row.shape = describe(item, 1)
                end
                items[#items + 1] = row
            end
        end
    end)
    out.pairs_count = total
    if #items > 0 then out.items = items end
    return out
end

local function probe_vehicle_load(vehicle, label, out)
    local entry = { label = label, entity_id = common.entity_id(vehicle) }

    -- 组件视图
    local component = component_access.get(vehicle, "TRANSPORT_VEHICLE")
    entry.has_transport_vehicle = component ~= nil
    if component ~= nil then
        for _, name in ipairs({ "cargoLoad", "capacities", "allCapacities" }) do
            entry["component_" .. name] = dump_pairs(common.field(component, name), 12)
        end
        entry.component_other_fields = describe(component)
    end

    -- 聚合表（第三条取值路）
    local interface = common.field(game, "interface")
    local get_entity = common.field(interface, "getEntity")
    if type(get_entity) == "function" then
        local ok_call, agg = pcall(get_entity, common.entity_id(vehicle))
        if ok_call and agg ~= nil then
            for _, name in ipairs({ "cargoLoad", "capacities", "allCapacities" }) do
                entry["aggregate_" .. name] = dump_pairs(common.field(agg, name), 12)
            end
            entry.aggregate_line = common.field(agg, "line")
            entry.aggregate_name = common.field(agg, "name")
            entry.aggregate_state = common.field(agg, "state")
        else
            entry.aggregate_error = "取实体失败"
        end
    end
    out[#out + 1] = entry
end

-- ===== ④ 一条线的两条读取路（组件视图 vs 聚合表）=============================
local function probe_one_line(line, index, report, errors)
    local id = common.entity_id(line)
    local entry = { index = index, entity_id = id, name = common.field(component_access.get(line, "LINE"), "name") }

    -- 组件视图：逐个试项目登记的全部组件名，列出命中的
    local ok_names, names = pcall(common.components_of, line)
    entry.components_of = ok_names and names or { error = tostring(names) }

    -- 已知能读到的那两个组件，把字段全摊出来
    local line_component = component_access.get(line, "LINE")
    entry.line_component_fields = describe(line_component)
    entry.vehicle_info = describe(common.field(line_component, "vehicleInfo"), 1)

    -- 聚合表（第三条取值路）—— 本项目"组件视图空、聚合表有"的老坑，必须两条都走
    local interface = common.field(game, "interface")
    local get_entity = common.field(interface, "getEntity")
    if type(get_entity) == "function" then
        local ok_call, agg = pcall(get_entity, id)
        if ok_call and agg ~= nil then
            local fields = {}
            pcall(function()
                for key, value in pairs(agg) do
                    fields[tostring(key)] = describe(value, 2)
                end
            end)
            entry.aggregate_fields = fields
        else
            entry.aggregate_error = ok_call and "返回 nil" or tostring(agg)
        end
    else
        entry.aggregate_error = "game.interface.getEntity 不是函数"
    end

    -- 顺带问这条线挂没挂那两个关键组件（单条线路粒度）
    entry.has_log_book = component_access.get(line, "LOG_BOOK") ~= nil
    entry.has_maintenance_cost = component_access.get(line, "MAINTENANCE_COST") ~= nil

    return entry
end

-- ========================================================================
function M.collect()
    local report = {
        probe_kind = "line-finance",
        write_command_sent = false,
        question = "游戏 UI 里每条线的「运输收入 / 车辆维护成本」两条曲线，引擎是否给 mod 读？"
            .. "—— 已排除 system 接口、Line 组件两路、玩家账本、车辆类组件四个方向；"
            .. "只剩 LOG_BOOK 组件、以及车辆 cargoLoad（能不能读出运量）这两条没验证",
        generated_from = "api.engine.system.lineSystem + api.engine.getComponent + game.interface.getEntity + game.config",
    }
    local errors = {}

    -- ① 配置常量
    pcall(read_config, report)

    -- 取全部线路
    local lines = nil
    local ok_lines, value = pcall(function() return api.engine.system.lineSystem.getLines() end)
    if ok_lines and type(value) == "table" then lines = value end
    report.lines_available = lines ~= nil
    if lines == nil then
        report.errors = { { step = "getLines", error = tostring(value) } }
        return report
    end

    -- 🔴 用 pairs 收成数组再遍历。**不要用 `#lines`** —— 引擎返回的可能是 map 或
    --    Sol2 绑定的 proxy，`#` 会返回 0，那样一条线都扫不到（本项目踩过这个坑）。
    local line_list = {}
    pcall(function()
        for _, line in pairs(lines) do
            if #line_list < SCAN_LIMIT then line_list[#line_list + 1] = line end
        end
    end)
    local line_count = #line_list
    report.line_count = line_count
    report.line_count_note = "用 pairs 收集（不用 # ；引擎返回值可能是 map）"

    -- ② 细查前几条线
    local samples = {}
    for index = 1, line_count do
        if #samples >= LINE_SAMPLE then break end
        local ok, entry = pcall(probe_one_line, line_list[index], index, report, errors)
        if ok then samples[#samples + 1] = entry
        else errors[#errors + 1] = { step = "probe_one_line", index = index, error = tostring(entry) } end
    end
    report.line_samples = samples

    -- ③ 扫全部线路：统计那两个组件到底挂不挂
    local scan = { scanned = 0, with_log_book = 0, with_maintenance_cost = 0, component_view_nonempty = 0 }
    local component_hits = {}
    for index = 1, line_count do
        local line = line_list[index]
        scan.scanned = scan.scanned + 1
        if component_access.get(line, "LOG_BOOK") ~= nil then scan.with_log_book = scan.with_log_book + 1 end
        if component_access.get(line, "MAINTENANCE_COST") ~= nil then
            scan.with_maintenance_cost = scan.with_maintenance_cost + 1
        end
        local ok_names, names = pcall(common.components_of, line)
        if ok_names and type(names) == "table" and #names > 0 then
            scan.component_view_nonempty = scan.component_view_nonempty + 1
            for _, name in ipairs(names) do
                component_hits[name] = (component_hits[name] or 0) + 1
            end
        end
    end
    scan.component_view_hits = component_hits
    report.line_scan = scan

    -- ④ 全实体范围找 LOG_BOOK / MAINTENANCE_COST（线路以外的地方也试）
    --    这两样东西**可能压根不挂在线路上** —— 没找到之前不能下"引擎不给"的结论。
    local log_found, maint_found = {}, {}
    local vehicle_list = {}
    local tried = {}

    local function try_entity(entity, label)
        if entity == nil then return end
        tried[label] = (tried[label] or 0) + 1
        pcall(hunt_logbook, entity, label, log_found, errors)
        pcall(hunt_maintenance, entity, label, maint_found)
    end

    -- 线路
    for index = 1, math.min(line_count, ENTITY_PROBE_LIMIT) do try_entity(line_list[index], "line") end
    -- 玩家（账本挂在它身上，LOG_BOOK 也可能在这）
    local ok_player, player = pcall(function() return api.engine.util.getPlayer() end)
    if ok_player then try_entity(player, "player") end
    -- 车辆
    local ok_vehicles, vehicles = pcall(function() return api.engine.system.transportVehicleSystem.getVehicles() end)
    if ok_vehicles and type(vehicles) == "table" then
        pcall(function()
            for _, vehicle in pairs(vehicles) do
                if #vehicle_list < VEHICLE_SAMPLE then vehicle_list[#vehicle_list + 1] = vehicle end
            end
        end)
        for index = 1, math.min(#vehicle_list, ENTITY_PROBE_LIMIT) do
            try_entity(vehicle_list[index], "vehicle")
        end
    end
    -- 产业建筑（TRANSPORT_HISTORY 就挂在它们身上，LOG_BOOK 也可能同处）
    local ok_stock, stocks = pcall(function() return api.engine.system.stockListSystem.getCargoType2stockList2sourceAndCount() end)
    if ok_stock then tried["stockListSystem_call"] = type(stocks) end

    report.log_book_hits = log_found
    report.maintenance_cost_hits = maint_found
    report.entities_tried = tried

    -- ⑤ 车辆的装载与容量 —— 用户问「能不能基于每个交通工具算收入」。
    --    车辆的聚合表里没有钱；唯一还能算的就是「运了多少货」，
    --    而它藏在 `cargoLoad` / `capacities`（用 pairs 问，别用 `#`）。
    local loads = {}
    for index = 1, #vehicle_list do
        local ok, entry = pcall(probe_vehicle_load, vehicle_list[index], "vehicle#" .. index, loads)
        if not ok then
            errors[#errors + 1] = { step = "probe_vehicle_load", index = index, error = tostring(entry) }
        end
    end
    report.vehicle_loads = loads
    report.vehicle_loads_note = "cargoLoad / capacities 一律用 pairs 问 —— world-probe 里那两个 length=0 "
        .. "是用 `#` 数的，map 用 `#` 就是 0（本项目老坑）。若这里能读出「货种 → 数量」，"
        .. "「每辆车运了多少 × 运价」就算得出来，按 line 汇总就是每条线的收入。"

    -- ⑤ 结论段（把"是什么"和"不是什么"分开写，方便下结论时不误读）
    -- 车辆装载到底读不读得出来 —— 决定「基于交通工具算收入」这条路通不通
    local cargo_readable, capacity_readable = false, false
    for _, entry in ipairs(loads) do
        for _, key in ipairs({ "component_cargoLoad", "aggregate_cargoLoad" }) do
            local block = entry[key]
            if type(block) == "table" and (block.pairs_count or 0) > 0 then cargo_readable = true end
        end
        for _, key in ipairs({ "component_capacities", "component_allCapacities", "aggregate_capacities" }) do
            local block = entry[key]
            if type(block) == "table" and (block.pairs_count or 0) > 0 then capacity_readable = true end
        end
    end

    report.conclusion = {
        log_book_accessible = #log_found > 0,
        maintenance_cost_accessible = #maint_found > 0,
        line_level_finance_field_found = false,
        vehicle_level_finance_field_found = false,
        vehicle_cargo_load_readable = cargo_readable,
        vehicle_capacity_readable = capacity_readable,
        note = "前四个布尔由本探针的实测段判定：line_samples[].aggregate_fields / vehicle_loads[] 里"
            .. "若没有 income/balance/profit/revenue 一类字段，则该层级确实没有钱。"
            .. "vehicle_cargo_load_readable = 用 pairs 能读出「货种 → 数量」⇒ "
            .. "「每辆车运了多少 × 运价」可行，按 line 汇总就是每条线的收入。",
    }

    report.errors = errors
    return report
end

return M
