-- 产业图层采集器（只读）
--
-- 数据源：SIM_BUILDING 组件。
--
-- 读法要点（2026-09-28 修正）：`SIM_BUILDING` 的**组件视图**里没有 position，
-- 只有 level / stockList。所以位置必须走 BOUNDING_VOLUME 的包围盒中心
-- （rail_network.lua 的 bounds_for() 已在 STATION/TOWN 上验证可用）。
-- 之前直接读 building.position 导致 131 个产业全被跳过。
--
-- 名字同样不在组件视图里；先用 field_probe 把真实字段名探出来再说，
-- 本版先输出位置 / 等级 / 库存关联，名字留空。

local common = require "tpf2_mcp/collectors/common"
local component_access = require "tpf2_mcp/collectors/component_access"
local field_probe = require "tpf2_mcp/collectors/field_probe"

local M = {}

local function vec(value)
    if value == nil then return nil end
    local x, y, z = common.field(value, "x"), common.field(value, "y"), common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = type(z) == "number" and z or 0 }
end

-- 照 rail_network.lua 的 bounds_for()：用 BOUNDING_VOLUME 的包围盒中心当位置。
-- 读不到就是 nil，由调用方的 no_bounds 计数报告规模（不往 errors 里堆）。
--
-- 2026-09-30 增：**同时把包围盒尺寸带出来**。原先只返回中心、把尺寸丢掉，
-- 于是前端只能把所有产业画成同一个符号 —— 用户 2026-09-29 明确不满过
-- （"地图上的产业我看成橙色方块太丑"/"具体形状要像火车站那样画出来"）。
-- 数据本来就在手上（min/max 两个角点都读出来了），只是没往外传。
-- 返回 (center, size)；size.x / size.y 是**占地长宽**（世界坐标 x/y 为水平面，z 为高度）。
-- ⚠️ 这是**轴对齐**包围盒：建筑若带旋转，矩形会略大于实际轮廓，够用但不精确。
local function bounds_for(entity)
    local volume = component_access.get(entity, "BOUNDING_VOLUME")
    local bbox = common.field(volume, "bbox")
    local minimum = vec(common.field(bbox, "min")) or vec(common.field(bbox, "bbMin"))
    local maximum = vec(common.field(bbox, "max")) or vec(common.field(bbox, "bbMax"))
    if not minimum or not maximum then return nil end
    local center = {
        x = (minimum.x + maximum.x) / 2,
        y = (minimum.y + maximum.y) / 2,
        z = (minimum.z + maximum.z) / 2,
    }
    local size = {
        x = maximum.x - minimum.x,
        y = maximum.y - minimum.y,
        z = maximum.z - minimum.z,
    }
    return center, size
end

local function number_or_nil(value)
    if type(value) == "number" then return value end
    return nil
end

-- ── 实时库存：厂里现在有多少货 ────────────────────────────────────────────
--
-- 为什么不能直接读：`SIM_BUILDING.stockList` 只是个**实体 id**（比如 7674），
-- 不是数量；组件里也没有现成的"库存量"字段（`itemsProduced` / `itemsConsumed`
-- / `itemsShipped` 实测长度都是 0）。
--
-- TPF2 是**个体模拟** —— 每件货都是一个实体。货在厂里等着的时候挂在
-- `SIM_ENTITY_AT_STOCK` 上，它的 `stock` 字段指向所属库存（就是那个 stockList）。
-- 所以"这家厂里现在有多少件" = 按 stock **数实体**，这个一定数得出来。
--
-- 货种首次实现时不知道挂在哪个组件上（`SIM_ENTITY_AT_STOCK` 只有 stock / arrivalTime
-- 两个字段），所以顺带把前几个货实体的**完整组件结构**吐进 `stock_probe`（诊断用）。
-- 这样一次重启既拿到能用的件数，也能看清货种该怎么读，不必再来一轮。

local STOCK_ENTITY_COMPONENTS = {
    "SIM_ENTITY_AT_STOCK", "SIM_CARGO", "CARGO_TYPE", "NAME", "POSITION",
    "MOVE_PATH", "SIM_CARGO_AT_TERMINAL", "TRANSPORT_HISTORY",
}
local STOCK_PROBE_LIMIT = 4

-- 实时库存。
--
-- 🔴 2026-10-02 实测更正 —— 我上一轮判错过，而且连错两次，两次都错在"没看清手上的数据"：
--   ① 老版「数 SIM_ENTITY_AT_STOCK 实体、按 `stock` 字段分组」**是有效的**：
--      实测 215 个产业合计 **153,892 件**（非零 51 个；深圳制钢厂一家就 41,100）。
--      我上一轮写它"全为 0"是误判 —— 当时看的是 `itemsProduced`/`itemsConsumed` 那几个数组，
--      那是"生产/消耗记录表"，跟库存量不是一回事。
--   ② 引擎的 `simEntityAtStockSystem.getStock2SimEntityMap()` 官方文档写明返回
--      「stock → **cargo 实体列表**」——**不是件数**。我上一轮按数字去 `tonumber(value)`，
--      3118 项里只认出 14 项，库存合计错成 14 件（比不用还差）。
--   ⇒ 所以**主路改回"数实体"**（已验证），API 那条降级成**形状诊断**（`stock_api_shape`）：
--      把它每项 value 的类型、以及"当数字 / 数元素"两种算法的总量都记下来，
--      下次看数据就知道该怎么正确解析，不必再赌一轮。
-- 返回 counts(库存id→件数), 遍历到的实体数, 是否成功, 用的哪条路
local function pairs_flat(value)
    local out = {}
    if value == nil then return out end
    pcall(function() for key, item in pairs(value) do out[key] = item end end)
    return out
end

-- 只看形状、**不用它算数**。任何失败都吞掉，绝不影响主路。
local function stock_api_shape()
    local probe = { ok = false, map_items = 0, numeric_total = 0, element_total = 0, samples = {} }
    pcall(function()
        local map = api.engine.system.simEntityAtStockSystem.getStock2SimEntityMap()
        if map == nil then probe.error = "map is nil"; return end
        probe.ok = true
        for stock, value in pairs(map) do
            probe.map_items = probe.map_items + 1
            -- 算法 A：当成数字直接加（上一轮的错误做法，留着重现用）
            local as_number = tonumber(tostring(value))
            if as_number ~= nil then probe.numeric_total = probe.numeric_total + as_number end
            -- 算法 B：当成"货实体集合"数元素个数（文档暗示的正确做法）
            local by_array = common.array_count(value)
            local by_pairs = nil
            pcall(function()
                local n = 0
                for _ in pairs(value) do n = n + 1 end
                by_pairs = n
            end)
            local best = by_array
            if best == nil or best == 0 then best = by_pairs end
            if best ~= nil then probe.element_total = probe.element_total + best end
            if #probe.samples < 5 then
                probe.samples[#probe.samples + 1] = {
                    stock_id = tonumber(tostring(stock)),
                    value_type = type(value),
                    as_number = as_number,
                    by_array = by_array,
                    by_pairs = by_pairs,
                    text = tostring(value):sub(1, 40),
                }
            end
        end
    end)
    return probe
end

local function by_stock_counts(errors)
    -- **主路：数实体**（`stock` 字段必须走 pairs —— getter 路径拿不到）
    local counts, seen = {}, 0
    local ok = common.safe_for_each_entity("SIM_ENTITY_AT_STOCK", function(entity)
        seen = seen + 1
        local component = common.safe_get_component(entity, "SIM_ENTITY_AT_STOCK", errors)
        local flat = pairs_flat(component)
        local stock = number_or_nil(flat.stock) or number_or_nil(common.field(component, "stock"))
        if stock ~= nil then
            counts[stock] = (counts[stock] or 0) + 1
        end
    end, errors)
    return counts, seen, ok, "entity_count"
end

local function probe_stock_entities(errors)
    local out = {}
    common.safe_for_each_entity("SIM_ENTITY_AT_STOCK", function(entity)
        if #out >= STOCK_PROBE_LIMIT then return end
        local entry = { entity_id = common.entity_id(entity) }
        for _, name in ipairs(STOCK_ENTITY_COMPONENTS) do
            local component = common.safe_get_component(entity, name, errors)
            if component ~= nil then
                entry[name] = field_probe.describe(component)
            end
        end
        out[#out + 1] = entry
    end, errors)
    return out
end

function M.collect()
    local errors = {}
    local points = {}
    local skipped = 0
    local no_bounds = 0
    local probe = nil
    local building_missing = false

    -- 实时库存要先数一遍货实体（见文件前面 by_stock_counts 的说明）。
    -- 放在产业循环**之前**：一遍数完建好表，循环里 O(1) 查。
    local stock_counts, stock_seen, stock_ok, stock_source = by_stock_counts(errors)
    local stock_probe = probe_stock_entities(errors)
    -- 引擎映射表的形状诊断（**不用它算数**，只把"该怎么解析它"这件事查清楚）
    local stock_api = stock_api_shape()
    -- 交叉核对：产业的 `stockList` 值能不能在库存表的键里找到？
    -- **这是"库存能不能挂到产业上"的唯一判据** —— 命中率低就说明两套 id 不是一套，别猜。
    local stock_ids = {}
    common.safe_for_each_entity("SIM_BUILDING", function(entity)
        local building = component_access.get(entity, "SIM_BUILDING")
        local value = number_or_nil(common.field(building, "stockList"))
        if value ~= nil then stock_ids[value] = true end
    end, errors)
    local stock_id_total, stock_id_hit = 0, 0
    for value in pairs(stock_ids) do
        stock_id_total = stock_id_total + 1
        if stock_counts[value] ~= nil then stock_id_hit = stock_id_hit + 1 end
    end

    local ok, scanned_or_error = common.safe_for_each_entity("SIM_BUILDING", function(entity)
        local building = component_access.get(entity, "SIM_BUILDING")
        if building == nil then
            skipped = skipped + 1
            if not building_missing then
                building_missing = true
                errors[#errors + 1] = { component = "SIM_BUILDING",
                                        note = "unavailable; further occurrences only counted in skipped" }
            end
            return
        end
        if probe == nil then
            probe = { building = field_probe.describe(building) }
        end
        local center, size = bounds_for(entity)
        if center == nil then
            no_bounds = no_bounds + 1
            return
        end
        local stock_id = number_or_nil(common.field(building, "stockList"))
        points[#points + 1] = {
            entity_id = common.entity_id(entity),
            position = center,
            -- 占地尺寸（世界坐标 x/y 长宽、z 高）。前端拿它画每个工厂的实际矩形，
            -- 而不是把 214 个产业全画成同一个符号。
            extent = size,
            level = number_or_nil(common.field(building, "level")),
            upgrade_progress = number_or_nil(common.field(building, "upgradeProgress")),
            stock_list = stock_id,
            -- ★ 实时库存：这个厂里现在有多少件货（数 SIM_ENTITY_AT_STOCK 得到的，见文件前面）
            stock_count = stock_id ~= nil and (stock_counts[stock_id] or 0) or nil,
            consumed_count = common.array_count(common.field(building, "itemsConsumed")),
            produced_count = common.array_count(common.field(building, "itemsProduced")),
            shipped_count = common.array_count(common.field(building, "itemsShipped")),
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

    -- 有多少个库存里真的有货（诊断用：如果这里远小于产业数，说明数法可能不对）
    local stocks_with_items = 0
    for _ in pairs(stock_counts) do stocks_with_items = stocks_with_items + 1 end

    return {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        geometry_kind = "POINT",
        counts = {
            total = #points,
            points = #points,
            scanned = scanned_or_error,
            skipped = skipped,
            no_bounds = no_bounds,
        },
        field_probe = probe,
        -- 库存诊断 + 统计。stock_probe 是前几个货实体的完整组件结构，
        -- 拿它确认"货种"到底挂在哪个组件上；stock_stats 看数出来的规模合不合理。
        stock_probe = stock_probe,
        stock_stats = {
            source = stock_source,
            entities_seen = stock_seen,
            stocks_with_items = stocks_with_items,
            ok = stock_ok,
            -- 交叉核对：产业 stockList 值里有多少能在库存表里找到（**这是能否挂到产业的判据**）
            industry_stock_ids = stock_id_total,
            industry_stock_ids_hit = stock_id_hit,
            -- 引擎映射表的形状（见 stock_api_shape 的说明）：map_items / numeric_total /
            -- element_total 三个数一对比，就知道"件数"到底该怎么从它里面取。
            api_shape = stock_api,
        },
        points = points,
        errors = errors,
    }
end

return M
