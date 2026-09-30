-- 只读探针：经济（公司账本 / 每条线的运营开销与运价 / 全局运输统计 / 库存）
--
-- 为什么要有它（用户 2026-09-30 定的运营前提）：
--   「城镇发展优先，保证整体盈利」—— 判据的红线是**整体盈利**，
--   而客运线允许亏着跑。要执行这条判断，必须能读到两样东西，而现有产物里**都没有**：
--     ① 公司整体收支（账本流水）→ 判断"整体是不是在赚钱"
--     ② 每条线的运营开销（维护费）与运价 → 判断"这条客运线一年亏多少"
--   `layer-*` 只有几何与流量，`state.json` 只有余额存量（余额是**存量**，不是利润）。
--
-- 引擎依据（全部取自专家包 api 文档，不是我猜的）：
--   · `Account` 组件（ACCOUNT=0，挂在 player 上）：字段 `minimumLoan` / `position` / `journal`。
--     `journal` 是 `enum.JournalEntry` 列表，每条含 `time` / `amount` / `category`（`position` 已废弃恒 nil）；
--     `category` 是 `enum.JournalEntryCategory`，含 `type` / `construction` / `maintenance` / `other` / `carrier`。
--     `enum.JournalEntryType`：LOAN=0 INTEREST=1 CONSTRUCTION=2 ACQUISITION=3 MAINTENANCE=4 INCOME=5 OTHER=6
--     `enum.JournalEntryCarrier`：ROAD=0 RAIL=1 TRAM=2 OTHER=3 AIR=4 WATER=5
--     `enum.JournalEntryMaintenance`：VEHICLE=0 INFRASTRUCTURE=1 OTHER=2
--     🔴 **账本条目里没有"哪条线"这个字段**（那 7 个字段里没有实体引用）——
--        所以公司账本只能按 carrier 聚合，做不出"第 12345 号线亏了多少"。
--        线路级的亏盈只能靠"维护费 + 运价 + 运量"这条侧路估算，见下面 lines 段。
--   · `MaintenanceCost` 组件（MAINTENANCE_COST=18）：字段 `maintenanceCost`，
--     官方文档原文只说 "the maintenance cost of an object"，**没写单位与周期**（很可能是每月）。
--     ⇒ 探针照抄引擎给的数，**不当成已确认口径**；前端/分析里要标"周期待实测"。
--   · `LineVehicleInfo`（Line 的子表）：`transportModes` / `defaultPrice` —— 运价在这里。
--   · `system.simCargoSystem.getSimCargosForLine(lineEntity)` —— 这条线上运的货。
--   · `util.getTransportedData()` → `TransportationStats{cargoTransported, passengersTransported}`（全局累计）。
--   · `system.simEntityAtVehicleSystem.getFare()` —— 票价。
--   · `simEntityAtStockSystem` 一族：`getStockCount(stockEntity, stockId)` / `getStock2SimEntityMap()`。
--     （顺带把用户先前问的"实时的原料数量"做准 —— 之前是靠数 SIM_ENTITY_AT_STOCK 个数的粗口径。）
--   · `transportHistorySystem.getStationTransportHistoryReferences/getTargetTransportHistoryReferences`
--     → `{Entity}`，这些实体挂 `TRANSPORT_HISTORY`。
--
-- 🚩 这个探针**没有在游戏里跑过**（写它的时候游戏是关的）。所以：
--   · 每个引擎调用都裹 pcall，失败只记一条错误、不中断；
--   · 输出里带 `shape` 段（字段探针）与 `components_present` 段（实体到底挂了哪些组件），
--     下一轮拿到真数据就能确定口径，不用再猜；
--   · 已知不确定的地方在输出里标 `unverified`，不假装是确认过的。
--
-- 只读：不发写命令，不改游戏状态。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"

local M = {}

local JOURNAL_LIMIT = 50000     -- 账本最多读多少条（超大存档保护）
local LINE_LIMIT = 400          -- 最多记多少条线（本存档 271 条）
local ERROR_LIMIT = 30          -- 错误只留前若干条（避免产物被刷爆，学 component_access 的教训）
local STOCK_SAMPLE = 3          -- 库存交叉验证采样几家产业

-- 枚举名照抄官方文档（数字 → 名字）。**不硬编码取值判断**，只用来把数字翻成人看得懂的字。
local TYPE_NAME = {
    [0] = "LOAN", [1] = "INTEREST", [2] = "CONSTRUCTION", [3] = "ACQUISITION",
    [4] = "MAINTENANCE", [5] = "INCOME", [6] = "OTHER",
}
local CARRIER_NAME = {
    [0] = "ROAD", [1] = "RAIL", [2] = "TRAM", [3] = "OTHER", [4] = "AIR", [5] = "WATER",
}
local MAINT_NAME = { [0] = "VEHICLE", [1] = "INFRASTRUCTURE", [2] = "OTHER" }
local CONSTRUCTION_NAME = {
    [0] = "STREET", [1] = "TRACK", [2] = "SIGNAL", [3] = "STATION",
    [4] = "DEPOT", [5] = "BULLDOZER", [6] = "OTHER",
}

local ENTRY_KEYS = { "time", "amount", "position", "category" }
local CATEGORY_KEYS = { "type", "construction", "maintenance", "other", "carrier" }

-- 引擎 system 对象的名字（`api.engine.system.<名>`）。项目里已在用的是
-- streetConnectorSystem / stationSystem / simPersonSystem / simCargoSystem /
-- transportVehicleSystem / transportNetworkSystem / catchmentAreaSystem / townBuildingSystem
-- —— 其余按同一命名规律列成候选，**逐个探测哪个真的存在**（而不是假定）。
local SYSTEM_CANDIDATES = {
    "lineSystem",
    "simCargoSystem",
    "simEntityAtStockSystem",
    "simEntityAtVehicleSystem",
    "simPersonAtTerminalSystem",
    "transportHistorySystem",
    "transportVehicleSystem",
}

local function push_error(errors, entry)
    if #errors < ERROR_LIMIT then errors[#errors + 1] = entry end
end

-- 裹 pcall 调用。返回 value；失败返回 nil（错误信息由调用方按需记）。
local function call(fn)
    local ok, value = pcall(fn)
    if ok then return value end
    return nil
end

-- 遍历"引擎集合"。它们可能是 userdata（不是普通 table），可能是 0 基。
-- 返回 发出的个数, 引擎报的总数。
local function each_index(value, limit, fn)
    local count = common.array_count(value)
    if count == nil then return 0, nil end
    -- 0 基判定：value[0] 有值、而 value[count] 没值 ⇒ 0..count-1
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

-- 某个实体挂了哪些组件。
-- ⚠️ 2026-09-30 首次实测教训：原本写的 `for name in pairs(api.type.ComponentType) do ... end`
-- **枚举不出任何东西**（返回空数组）—— 本机 `pairs(ComponentType)` 不工作。
-- 改成走 `common.components_of`（按硬编码的 77 个常量名逐个试）。
local function present_components(entity, errors)
    if entity == nil then return nil end
    local ok, names = pcall(common.components_of, entity)
    if not ok or names == nil then
        push_error(errors, { stage = "present_components", error = tostring(names) })
        return nil
    end
    return names
end

function M.collect()
    local errors = {}
    local started = common.clock()
    local out = {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        probe_kind = "ECONOMY",
        schema_version = 1,
        question = "公司整体收支 + 每条线的维护费/运价/运量 —— 支撑『整体盈利』与『这条客运线一年亏多少』",
        unverified = {
            "MAINTENANCE_COST.maintenanceCost 的**周期与币种单位**官方文档没写（推测每月）—— 分析前要实测核对",
            "JournalEntry 的 amount 符号规则（正数是否统一表示流出）未实测 —— 所以按 type 分开求和，不合并",
            "本探针从未在游戏里运行过，字段名若有偏差看 shape 段",
        },
        errors = errors,
    }

    local player = call(function() return api.engine.util.getPlayer() end)
    local world = call(function() return api.engine.util.getWorld() end)

    -- ===== 0. 时间基准 =====
    -- 账本条目带的是游戏内时间戳，换算成"年"要有基准；游戏时间也一并记下来。
    local game_time_component = (world and component_access.get(world, "GAME_TIME"))
        or (player and component_access.get(player, "GAME_TIME"))
    out.game_time = common.field(game_time_component, "gameTime")

    -- ===== 1. 实体挂了哪些组件（发现用）=====
    -- 先问"线路实体到底挂没挂 MAINTENANCE_COST / LOG_BOOK / TRANSPORT_HISTORY"——
    -- 这决定了线路级经济数据走哪条路。写死假定不如当场问一次。
    out.components_present = {
        player = present_components(player, errors),
    }

    -- ===== 2. 公司账本（整体收支）=====
    local account = player and component_access.get(player, "ACCOUNT")
    local journal = account and common.field(account, "journal")
    local journal_out = {
        available = journal ~= nil,
        source = "player.ACCOUNT.journal",
        note = "账本条目**没有线路引用**，只能按 carrier 聚合；线路级亏盈要靠维护费+运价侧路估算",
        by_type = {},
        by_carrier = {},
        by_maintenance = {},
        by_construction = {},
        read = 0,
        total = nil,
        truncated = false,
    }

    local type_acc, carrier_acc, maint_acc, construction_acc = {}, {}, {}, {}
    local first_time, last_time = nil, nil

    local function bump(store, key, amount)
        local item = store[key]
        if item == nil then
            item = { key = key, count = 0, sum = 0, min = nil, max = nil }
            store[key] = item
        end
        item.count = item.count + 1
        if type(amount) == "number" then
            item.sum = item.sum + amount
            if item.min == nil or amount < item.min then item.min = amount end
            if item.max == nil or amount > item.max then item.max = amount end
        end
    end

    if journal ~= nil then
        local first_entry = nil
        local read, total = each_index(journal, JOURNAL_LIMIT, function(entry)
            if first_entry == nil then
                first_entry = entry
                -- 字段探针：把"这条账目到底有哪些字段"如实报出来（不依赖文档）。
                journal_out.shape = common.probe_fields(entry, ENTRY_KEYS)
                journal_out.category_shape = common.probe_fields(common.field(entry, "category"), CATEGORY_KEYS)
            end
            local time = common.field(entry, "time")
            if type(time) == "number" then
                if first_time == nil or time < first_time then first_time = time end
                if last_time == nil or time > last_time then last_time = time end
            end
            local amount = common.field(entry, "amount")
            local category = common.field(entry, "category")
            local entry_type = common.field(category, "type")
            bump(type_acc, TYPE_NAME[entry_type] or ("TYPE_" .. tostring(entry_type)), amount)
            bump(carrier_acc, CARRIER_NAME[common.field(category, "carrier")]
                or ("CARRIER_" .. tostring(common.field(category, "carrier"))), amount)
            local maintenance_kind = common.field(category, "maintenance")
            if maintenance_kind ~= nil then
                bump(maint_acc, MAINT_NAME[maintenance_kind] or ("MAINT_" .. tostring(maintenance_kind)), amount)
            end
            local construction_kind = common.field(category, "construction")
            if construction_kind ~= nil then
                bump(construction_acc, CONSTRUCTION_NAME[construction_kind]
                    or ("CONSTRUCTION_" .. tostring(construction_kind)), amount)
            end
        end)
        journal_out.read = read
        journal_out.total = total
        journal_out.truncated = (total ~= nil and read < total)
        journal_out.first_time = first_time
        journal_out.last_time = last_time
        if type(first_time) == "number" and type(last_time) == "number" then
            journal_out.span_seconds = last_time - first_time
        end
    end

    local function flatten(store)
        local list = {}
        for _, item in pairs(store) do list[#list + 1] = item end
        table.sort(list, function(a, b) return a.count > b.count end)
        return list
    end

    journal_out.by_type = flatten(type_acc)
    journal_out.by_carrier = flatten(carrier_acc)
    journal_out.by_maintenance = flatten(maint_acc)
    journal_out.by_construction = flatten(construction_acc)
    out.journal = journal_out

    -- ===== 3. 全局运输统计 =====
    local transported = call(function() return api.engine.util.getTransportedData() end)
    local fare = call(function() return api.engine.system.simEntityAtVehicleSystem.getFare() end)
    out.global = {
        transported = common.probe_fields(transported, { "cargoTransported", "passengersTransported" }),
        fare = { type = type(fare), value = type(fare) == "number" and fare or nil },
    }

    -- ===== 4. 线路级（维护费 / 运价 / 运量）=====
    local lines_out = {}
    local line_diag = { seen = 0, truncated = false, first_line_probed = false }
    common.safe_for_each_entity("LINE", function(entity)
        line_diag.seen = line_diag.seen + 1
        if #lines_out >= LINE_LIMIT then
            line_diag.truncated = true
            return
        end
        local line_component = component_access.get(entity, "LINE")
        local name_component = component_access.get(entity, "NAME")
        local vehicle_info = common.field(line_component, "vehicleInfo")

        -- 维护费：组件可能根本没挂 → 记 present=false，别让"读不到"看起来像"是 0"。
        local maintenance_component = component_access.get(entity, "MAINTENANCE_COST")
        local maintenance = common.field(maintenance_component, "maintenanceCost")

        local vehicles = call(function() return api.engine.system.transportVehicleSystem.getLineVehicles(entity) end)
        local cargos = call(function() return api.engine.system.simCargoSystem.getSimCargosForLine(entity) end)

        lines_out[#lines_out + 1] = {
            entity_id = common.entity_id(entity),
            name = common.field(name_component, "name") or common.name_from_component(name_component),
            maintenance_present = maintenance_component ~= nil,
            maintenance_cost = type(maintenance) == "number" and maintenance or nil,
            default_price = common.field(vehicle_info, "defaultPrice"),
            transport_modes = common.probe_fields(vehicle_info, { "transportModes", "defaultPrice" }),
            vehicle_count = common.array_count(vehicles),
            cargo_count = common.array_count(cargos),
            stop_count = common.array_count(common.field(line_component, "stops")),
        }

        -- 只有第一条线需要一次"组件清单"（上面 §1 的问法，换到线路实体上问一遍）
        if not line_diag.first_line_probed then
            line_diag.first_line_probed = true
            out.components_present.line = present_components(entity, errors)
        end
    end, errors)

    out.lines = {
        available = #lines_out > 0,
        note = "维护费的**周期未实测**；defaultPrice 是引擎给的运价原值",
        diagnostics = line_diag,
        items = lines_out,
    }

    -- ===== 5. 哪些 system 真的存在 =====
    local system_out = {}
    local ok_system = pcall(function()
        for _, name in ipairs(SYSTEM_CANDIDATES) do
            local value = call(function() return api.engine.system[name] end)
            system_out[name] = { present = value ~= nil, value_type = type(value) }
        end
    end)
    if not ok_system then
        push_error(errors, { stage = "systems", error = "api.engine.system 不可访问" })
    end
    out.systems = system_out

    -- ===== 6. 库存（顺带把"实时原料数量"做准）=====
    -- `getStock2SimEntityMap()` = "stock → 等在那儿的货" 的映射，一次调用就拿到全部。
    -- 但**键是什么类型没实测**（可能是库存实体、也可能是 stockId）→ 这里只报形状 + 少量样例，
    -- 不做聚合；再加上几家产业的 `getStockCount` 做交叉验证。
    local stock_map = call(function() return api.engine.system.simEntityAtStockSystem.getStock2SimEntityMap() end)
    local stock_out = {
        map_present = stock_map ~= nil,
        map_type = type(stock_map),
        map_key_count = nil,
        map_samples = {},
        industry_samples = {},
    }
    if stock_map ~= nil then
        pcall(function()
            local count = 0
            local samples = 0
            for key, value in pairs(stock_map) do
                count = count + 1
                if samples < 3 then
                    samples = samples + 1
                    stock_out.map_samples[#stock_out.map_samples + 1] = {
                        key_type = type(key),
                        key_value = type(key) == "number" and key or nil,
                        value_type = type(value),
                        value_count = common.array_count(value),
                    }
                end
            end
            stock_out.map_key_count = count
        end)
    end

    -- 采样几家产业，对每个 stockId 试 getStockCount（stockEntity, stockId）。
    -- 用途：确定"库存量"到底该按哪个键取 —— 取不到也是一种结论（写进 errors）。
    local sampled = 0
    common.safe_for_each_entity("SIM_BUILDING", function(entity)
        if sampled >= STOCK_SAMPLE then return end
        local building = component_access.get(entity, "SIM_BUILDING")
        local stock_list = common.field(building, "stockList")
        if stock_list == nil then return end
        sampled = sampled + 1
        local per_stock = {}
        for stock_id = 0, 5 do
            local count = call(function()
                return api.engine.system.simEntityAtStockSystem.getStockCount(entity, stock_id)
            end)
            if count ~= nil then
                per_stock[#per_stock + 1] = { stock_id = stock_id, value_type = type(count), value = count }
            end
        end
        stock_out.industry_samples[#stock_out.industry_samples + 1] = {
            entity_id = common.entity_id(entity),
            stock_list = stock_list,
            stock_list_type = type(stock_list),
            get_stock_count = per_stock,
        }
    end, errors)
    out.stock = stock_out

    -- ===== 汇总 =====
    out.counts = {
        journal_read = journal_out.read,
        journal_total = journal_out.total,
        lines_seen = line_diag.seen,
        lines_kept = #lines_out,
        lines_with_maintenance = (function()
            local n = 0
            for _, item in ipairs(lines_out) do
                if item.maintenance_cost ~= nil then n = n + 1 end
            end
            return n
        end)(),
    }
    out.duration_ms = (common.clock() - started) * 1000
    return out
end

return M
