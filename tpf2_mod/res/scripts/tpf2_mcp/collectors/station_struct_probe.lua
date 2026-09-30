-- 只读探针 v3：车站结构的模块网格。
--
-- 已确认（v2 实测，2026-09-30）：
--   ① `pairs(params.modules)` **可用** —— 四类站的模块格子全部读得出
--      （rail 68 / street 5 / water 7 / air 11），键 = 数字，值 = **模块对象 userdata（4 个元素）**
--   ② `pairs(params)` **也可用**，且是读参数的**唯一正确方式** ——
--      `params.size` 被 Sol2 容器的方法遮蔽（按名字取到 function，pairs 里才是真数字）
--   ③ 每类站的 `MangleId` 公式**不同**（各自 `.con` 里定义）：
--        water : 1000000*(c1+100) + 100*(c2+100) + c3      ← 实测吻合
--        street:  200000*(c2+100) + 100*(c1+100) + c3      ← 实测吻合（注意 c2 在前、档宽 20 万）
--        rail / air: `.con` 里 0 处 result[MangleId] → 走别的机制
--      ⚠️ 所以**不要依赖反解**，直接读模块对象里的坐标（本探针要问的）。
--   ④ `streetConnectorSystem.getConstructionEntityForStation(station)` → 建筑实体 id（数字），
--      比 `getStation2ConstructionMap` 干净。
--   ⑤ `api.res.moduleRep.getAll()` = 1715 个模块**路径字符串**；`constructionRep.getAll()` = 754 个建筑路径。
--      `get(字符串)` 会失败（要整数 id）→ 传**下标**试。
--
-- **本探针只回答一个问题**：模块对象（4 个元素）里装的是什么？
--   如果它自带坐标/朝向/模块路径 → 四类站统一读法，不需要管 MangleId 差异。
--
-- 只读：不发写命令，不改游戏状态。
local common = require "tpf2_mcp/collectors/common"
local M = {}

local V1_SAMPLE_PER_KIND = 2
local TERMINAL_SAMPLE = 8
local MODULE_DEEP = 3      -- 每类深挖前几个模块对象

-- 🔴 2026-09-30：`out.kinds` 从"每类 2 座"改成**全量**。
-- 原先 `all_full()` 一满就 return，整个 STATION_GROUP 遍历提前收工 ——
-- 后果是**全存档只有 4 座站有模块清单**。而前端要画**任意一座站**的站场结构
-- （slotId → 坐标的公式四类站都已解出并通过实测），就必须有每座站的 slotId。
-- 上限给 700（本存档 565 座站 + 余量）；真被截断时由 diagnostics.truncated 报出来。
-- 体积控制：字段探针（probe_fields）只在每类**首例**上跑，其余站不带 probe
-- （见 describe 的 with_probe 参数）—— 每站约 1–3 KB，565 座合计 ~1 MB，一次性探针可接受。
local FULL_STATION_LIMIT = 700

local STATION_KEYS = {
    "terminals", "name", "cargo", "position", "carriers", "town", "stationGroup", "id",
    "platforms", "tracks", "lanes", "group", "type", "level",
}

local TERMINAL_KEYS = {
    "vehicleNodeId", "nodeId", "node", "station", "cargo", "index", "platformIndex",
    "direction", "lane", "lanes", "length", "position",
}

local PARAM_KEYS = {
    "modules", "moduleIds", "moduleList", "moduleId", "cells", "grid", "tiles", "slots",
    "erastr", "era", "variant", "variants", "length", "width", "height", "size", "sizes",
    "config", "modelConfig", "main", "addons", "end_l", "end_r", "end_t", "end_b",
    "flip_end_l", "flip_end_r", "count", "total", "type", "name", "id",
    "templateIndex", "terminals", "cargo",
}

local MODULE_KEYS = { "modules", "moduleIds", "moduleList", "cells", "grid", "tiles", "slots", "main", "addons" }

-- 模块对象最可能装的字段（路径 + 坐标 + 朝向 + 尺寸）。
local MODULE_OBJ_KEYS = {
    "fileName", "file", "moduleFile", "module", "name", "path", "modelFile", "model", "id", "index",
    "position", "pos", "x", "y", "z", "coordI", "coordJ", "coord", "cell", "cellI", "cellJ",
    "variant", "k", "rotation", "rot", "angle", "dir", "face", "flip", "orientation",
    "sizeX", "sizeY", "width", "length", "depth", "height", "size",
    "category", "type", "cargo", "terminal", "terminals", "params", "metadata", "icon",
    "modelId", "desc", "moduleDesc", "descId", "groupId",
}

-- 只读探测：失败的组件读取**不**污染主 errors 表（v2 就是这里刷出 154 条假错）。
local SILENT = setmetatable({}, { __index = function() return true end })

local function vec(value)
    if value == nil then return nil end
    local x = common.field(value, "x")
    local y = common.field(value, "y")
    local z = common.field(value, "z")
    if type(x) ~= "number" or type(y) ~= "number" then return nil end
    return { x = x, y = y, z = z }
end

local function kind_of(file)
    local text = string.lower(tostring(file or ""))
    if text == "" then return nil end
    if string.find(text, "station/rail", 1, true) or string.find(text, "station/train", 1, true) then return "rail" end
    if string.find(text, "station/street", 1, true) then return "street" end
    if string.find(text, "station/water", 1, true) or string.find(text, "harbor", 1, true) then return "water" end
    if string.find(text, "station/air", 1, true) or string.find(text, "airport", 1, true) or string.find(text, "airfield", 1, true) then return "air" end
    return nil
end

local function read_matrix(transf)
    if transf == nil then return nil end
    local out = { value_type = type(transf), count = common.array_count(transf) }
    local from_zero, from_one = {}, {}
    for i = 0, 15 do
        local value = common.field(transf, i)
        if type(value) == "number" then from_zero[#from_zero + 1] = value end
    end
    for i = 1, 16 do
        local value = common.field(transf, i)
        if type(value) == "number" then from_one[#from_one + 1] = value end
    end
    if #from_zero == 16 then out.zero_based = from_zero end
    if #from_one == 16 then out.one_based = from_one end
    if out.zero_based == nil and out.one_based == nil then
        out.partial = (#from_zero >= #from_one) and from_zero or from_one
    end
    return out
end

-- 一个格子的轻量读法：只要画图用得上的几项，不做深挖
-- （deep_module_object 很重，六百多个格子全深挖会把产物撑到几十 MB）。
local CELL_META_KEYS = { "cargo", "platform", "passenger_platform", "cargo_platform", "era", "level", "span" }

local function read_cell(slot_id, obj)
    local cell = { slot = slot_id }
    local name = common.field(obj, "name")
    if type(name) == "string" then cell.name = name end
    local variant = common.field(obj, "variant")
    if type(variant) == "number" then cell.variant = variant end
    local metadata = common.field(obj, "metadata")
    if metadata ~= nil then
        for _, key in ipairs(CELL_META_KEYS) do
            local value = common.field(metadata, key)
            local kind = type(value)
            if kind == "boolean" or kind == "number" or kind == "string" then
                cell[key] = value
            end
        end
    end
    return cell
end

-- 全量格子清单。
--
-- 🔴 只给"有多少格"是画不出结构的。要画真实结构，得知道**每格放了什么模块**，
--    再按 slotId 反解出网格坐标（i, j）—— 各站型的编码不一样，抄自各自的 .con：
--      火车站  slotId = 基址 + 1000*i + 10*j   格宽 5 m、格长 40 m
--      码头    slotId = 1000000*(c1+100) + 100*(c2+100) + c3
--      汽车站  slotId = 200000*(c2+100) + 100*(c1+100) + c3
--      机场    slotId = 基址 + 一维序号（不含坐标，反解不出位置）
--    （基址与格尺寸的出处见 .con 的 AddSlot / GetModuleAt；离线反解工具在 tools/ 下。）
local function read_cells(modules)
    if modules == nil then return nil, nil end
    local cells = {}
    local ok, err = pcall(function()
        for slot_id, obj in pairs(modules) do
            if type(slot_id) == "number" and obj ~= nil then
                cells[#cells + 1] = read_cell(slot_id, obj)
            end
        end
    end)
    table.sort(cells, function(a, b) return a.slot < b.slot end)
    return cells, (ok and nil or tostring(err))
end

local function read_module_grid(params)
    if params == nil then return { present = false } end
    local result = { present = true, params_type = type(params) }
    for _, key in ipairs(MODULE_KEYS) do
        local value = common.field(params, key)
        if value ~= nil then
            result[key] = { key = key, value_type = type(value), length = common.array_count(value) }
        end
    end
    -- ★ 全量格子清单（这半边的结构数据）
    local cells, cells_error = read_cells(common.field(params, "modules"))
    if cells ~= nil then
        result.cells = cells
        if cells_error ~= nil then result.cells_error = cells_error end
    end
    return result
end

-- =====================================================================
-- 通用小工具
-- =====================================================================

local function preview(value)
    if value == nil then return { type = "nil" } end
    local t = type(value)
    if t == "number" or t == "string" or t == "boolean" then return { type = t, value = value } end
    local out = { type = t }
    local count = common.array_count(value)
    if count ~= nil then out.length = count end
    local ok, text = pcall(tostring, value)
    if ok and type(text) == "string" and #text <= 90 then out.text = text end
    return out
end

local function try_pairs(value, limit)
    if value == nil then return { ok = false, error = "nil", items = {} } end
    local items = {}
    local ok, err = pcall(function()
        for k, v in pairs(value) do
            if #items >= limit then break end
            items[#items + 1] = { key = preview(k), value = preview(v) }
        end
    end)
    return { ok = ok, error = (not ok) and tostring(err) or nil, items = items }
end

local function try_ipairs(value, limit)
    if value == nil then return { ok = false, error = "nil", items = {} } end
    local items = {}
    local ok, err = pcall(function()
        for i, v in ipairs(value) do
            if #items >= limit then break end
            items[#items + 1] = { i = i, value = preview(v) }
        end
    end)
    return { ok = ok, error = (not ok) and tostring(err) or nil, items = items }
end

local function meta_info(value)
    local out = { value_type = type(value) }
    local ok, mt = pcall(getmetatable, value)
    if not ok then out.metatable_error = tostring(mt) return out end
    if mt == nil then out.metatable = "none" return out end
    out.metatable_type = type(mt)
    local keys = {}
    local ok2 = pcall(function()
        for k, v in pairs(mt) do
            if #keys >= 24 then break end
            keys[#keys + 1] = { key = tostring(k), type = type(v) }
        end
    end)
    out.metatable_keys = ok2 and keys or "unreadable"
    return out
end

-- =====================================================================
-- ★ 核心：模块对象里到底是什么？
-- =====================================================================

-- 把一个值展开一层：标量直接给；容器试 pairs / ipairs / 字段。
local function expand_value(value)
    local out = preview(value)
    if type(value) ~= "userdata" and type(value) ~= "table" then return out end
    local inside = try_pairs(value, 12)
    if #inside.items > 0 then out.pairs = inside end
    local ip = try_ipairs(value, 12)
    if #ip.items > 0 then out.ipairs = ip end
    out.fields = common.probe_fields(value, MODULE_OBJ_KEYS)
    out.vector = vec(value)
    return out
end

local function deep_module_object(obj)
    local out = { value_type = type(obj), len = common.array_count(obj) }
    if obj == nil then return out end
    out.container = meta_info(obj)
    out.fields = common.probe_fields(obj, MODULE_OBJ_KEYS)
    out.vector = vec(obj)
    local pr = try_pairs(obj, 16)
    out.pairs = pr
    local ip = try_ipairs(obj, 16)
    out.ipairs = ip
    -- pairs / ipairs 都不灵，就按索引逐个数（Sol2 容器常只给 __len + get()）
    if #pr.items == 0 and #ip.items == 0 then
        out.by_index = {}
        local getter = common.field(obj, "get")
        for i = 0, (out.len or 0) do
            local v = nil
            if type(getter) == "function" then
                local ok, got = pcall(getter, obj, i)
                if ok then v = got end
            end
            if v == nil then v = common.field(obj, i) end
            out.by_index[#out.by_index + 1] = { i = i, value = expand_value(v) }
        end
    else
        -- pairs / ipairs 能遍历 → 把每个值再展开一层（字段名取不到时的唯一线索）。
        -- 注意要**用原始遍历重取**，不能复用上面已被 preview() 过的项。
        out.expanded = {}
        local ok = pcall(function()
            for k, v in pairs(obj) do
                if #out.expanded >= 12 then break end
                out.expanded[#out.expanded + 1] = {
                    key = type(k) == "number" and { type = "number", value = k } or preview(k),
                    value = expand_value(v),
                }
            end
        end)
        if not ok or #out.expanded == 0 then
            local ok2 = pcall(function()
                for i, v in ipairs(obj) do
                    if #out.expanded >= 12 then break end
                    out.expanded[#out.expanded + 1] = { key = { type = "number", value = i }, value = expand_value(v) }
                end
            end)
            out.expanded_ipairs_ok = ok2
        end
    end
    return out
end

-- 模块网格：列出全部键；对前几个模块对象深挖。
local function deep_modules(params)
    local modules = common.field(params, "modules")
    local out = { present = modules ~= nil }
    if modules == nil then return out end
    out.container = meta_info(modules)
    out.raw_len = common.array_count(modules)
    local all = {}
    local pairs_ok, pairs_err = pcall(function()
        for k, v in pairs(modules) do
            all[#all + 1] = { key = k, value = v }
        end
    end)
    out.pairs_ok = pairs_ok
    out.pairs_error = (not pairs_ok) and tostring(pairs_err) or nil
    out.count = #all
    out.keys = {}
    for i, item in ipairs(all) do
        out.keys[#out.keys + 1] = item.key
        if i > 400 then break end
    end
    out.modules_deep = {}
    for i = 1, math.min(MODULE_DEEP, #all) do
        out.modules_deep[#out.modules_deep + 1] = { key = all[i].key, object = deep_module_object(all[i].value) }
    end
    return out
end

-- params 自身：pairs 是唯一正确读法（size 被容器方法遮蔽）。
local function deep_params(params)
    if params == nil then return { present = false } end
    local out = { present = true, container = meta_info(params), probe = common.probe_fields(params, PARAM_KEYS) }
    local items = {}
    local ok, err = pcall(function()
        for k, v in pairs(params) do
            items[#items + 1] = { key = preview(k), value = preview(v) }
        end
    end)
    out.pairs = { ok = ok, error = (not ok) and tostring(err) or nil, items = items }
    return out
end

-- res 层：getAll 给的是路径字符串数组；试传**下标**给 get()。
local function deep_res()
    local out = {}
    local function safe(label, fn)
        local ok, value = pcall(fn)
        if not ok then out[label] = { ok = false, error = tostring(value) } return nil end
        out[label] = { ok = true, preview = preview(value) }
        return value
    end

    local modules_all = safe("moduleRep.getAll", function() return api.res.moduleRep.getAll() end)
    if modules_all ~= nil then
        out["moduleRep.getAll"].first = (function()
            local items = {}
            for i = 0, 4 do
                local v = common.field(modules_all, i)
                if v ~= nil then items[#items + 1] = preview(v) end
            end
            if #items == 0 then
                for i = 1, 5 do
                    local v = common.field(modules_all, i)
                    if v ~= nil then items[#items + 1] = preview(v) end
                end
            end
            return items
        end)()
        for _, idx in ipairs({ 0, 1, 2, 100, 500 }) do
            local value = safe("moduleRep.get(" .. idx .. ")", function() return api.res.moduleRep.get(idx) end)
            if value ~= nil then
                local key = "moduleRep.get(" .. idx .. ")"
                out[key].probe = common.probe_fields(value, { "name", "fileName", "file", "size", "sizeX", "sizeY",
                    "width", "length", "depth", "height", "icon", "type", "cargo", "metadata", "terminals", "params",
                    "offset", "position" })
                out[key].pairs = try_pairs(value, 20)
            end
        end
        safe("moduleRep.getName(0)", function() return api.res.moduleRep.getName(0) end)
        safe("moduleRep.getFileName(0)", function() return api.res.moduleRep.getFileName(0) end)
    end

    local constructions_all = safe("constructionRep.getAll", function() return api.res.constructionRep.getAll() end)
    if constructions_all ~= nil then
        out["constructionRep.getAll"].first = (function()
            local items = {}
            for i = 0, 4 do
                local v = common.field(constructions_all, i)
                if v ~= nil then items[#items + 1] = preview(v) end
            end
            if #items == 0 then
                for i = 1, 5 do
                    local v = common.field(constructions_all, i)
                    if v ~= nil then items[#items + 1] = preview(v) end
                end
            end
            return items
        end)()
        for _, idx in ipairs({ 0, 1, 2, 100 }) do
            local value = safe("constructionRep.get(" .. idx .. ")", function() return api.res.constructionRep.get(idx) end)
            if value ~= nil then
                local key = "constructionRep.get(" .. idx .. ")"
                out[key].probe = common.probe_fields(value, { "name", "fileName", "description", "icon", "type",
                    "constructionType", "constructionTemplates", "params", "modules", "position" })
                out[key].pairs = try_pairs(value, 24)
            end
        end
    end
    return out
end

-- =====================================================================
-- collect
-- =====================================================================

function M.collect()
    local errors = {}
    local started = common.clock()
    local out = {
        status = "OK",
        source_status = "ENGINE_OBSERVED",
        probe_kind = "STATION_STRUCTURE",
        schema_version = 3,
        question = "模块对象（4 个元素）里装的是什么？（坐标/朝向/路径 → 四类站统一读法）",
        kinds = {},
        errors = errors,
    }

    local street_connector = api.engine.system.streetConnectorSystem

    -- 站 → 建筑实体 id（比 getStation2ConstructionMap 干净）
    local function construction_entity_for(station_entity)
        local ok, value = pcall(function() return street_connector.getConstructionEntityForStation(station_entity) end)
        if not ok or value == nil then return nil end
        if type(value) == "number" then return value end
        return common.entity_id(value)
    end

    local kinds = { rail = {}, street = {}, water = {}, air = {}, unknown = {} }
    local kind_names = { "rail", "street", "water", "air" }
    local total_seen = 0
    -- 全量口径：采到 FULL_STATION_LIMIT 座站才收工（不再是"每类 2 座就满"）。
    local function all_full()
        return total_seen >= FULL_STATION_LIMIT
    end

    local group_count = 0
    common.safe_for_each_entity("STATION_GROUP", function(group_entity)
        group_count = group_count + 1
        if all_full() then return end
        local group = common.safe_get_component(group_entity, "STATION_GROUP", errors)
        if group == nil then return end
        for _, station_entity in ipairs(common.sequence_values(common.field(group, "stations"))) do
            if all_full() then return end
            local construction_id = construction_entity_for(station_entity)
            local construction, file = nil, nil
            if construction_id ~= nil then
                construction = common.safe_get_component(construction_id, "CONSTRUCTION", SILENT)
                file = common.field(construction, "fileName")
            end
            local kind = kind_of(file) or "unknown"
            if kind ~= "unknown" and total_seen < FULL_STATION_LIMIT then
                total_seen = total_seen + 1
                kinds[kind][#kinds[kind] + 1] = {
                    station = station_entity, group = group_entity,
                    construction = construction, construction_id = construction_id, file = file,
                }
            end
        end
    end, errors)
    out.station_group_count = group_count

    -- with_probe：是否带上"字段探针"。**只有每类首例需要** —— 探针的用途是"把字段名探出来"，
    -- 全量输出时每座站都带一份纯属浪费体积（565 座 × 4 段探针 ≈ 几百 KB 无用数据）。
    local function describe(entry, kind, with_probe)
        local station = common.safe_get_component(entry.station, "STATION", SILENT)
        local info = {
            kind = kind,
            station_id = common.entity_id(entry.station),
            group_id = common.entity_id(entry.group),
            name = common.field(station, "name"),
            cargo = common.field(station, "cargo"),
            position = vec(common.field(station, "position")),
            construction_file = entry.file,
            construction_id = entry.construction_id,
            station_probe = with_probe and common.probe_fields(station, STATION_KEYS) or nil,
            terminals = {},
        }
        local terminals = common.sequence_values(common.field(station, "terminals"))
        info.terminal_count = #terminals
        for i, terminal in ipairs(terminals) do
            if i > TERMINAL_SAMPLE then break end
            local vn = common.field(terminal, "vehicleNodeId")
            local node_entity = common.field(vn, "entity")
            local node = node_entity ~= nil and common.safe_get_component(node_entity, "BASE_NODE", SILENT) or nil
            info.terminals[#info.terminals + 1] = {
                index = i - 1,
                vehicle_node_entity = common.entity_id(node_entity),
                position = vec(common.field(node, "position")) or vec(common.field(node, "pos")),
                probe = with_probe and common.probe_fields(terminal, TERMINAL_KEYS) or nil,
            }
        end
        local construction = entry.construction
        if construction ~= nil then
            local params = common.field(construction, "params")
            info.construction = {
                file_name = common.field(construction, "fileName"),
                position = vec(common.field(construction, "position")),
                transf = read_matrix(common.field(construction, "transf")),
                params_probe = with_probe and common.probe_fields(params, PARAM_KEYS) or nil,
                module_grid = read_module_grid(params),
            }
            if entry.construction_id ~= nil then
                local volume = common.safe_get_component(entry.construction_id, "BOUNDING_VOLUME", SILENT)
                if volume ~= nil then
                    local bbox = common.field(volume, "bbox")
                    info.bounding_volume = {
                        min = vec(common.field(bbox, "min")) or vec(common.field(bbox, "bbMin")),
                        max = vec(common.field(bbox, "max")) or vec(common.field(bbox, "bbMax")),
                    }
                end
            end
        end
        return info
    end

    local first_entries = {}
    local emitted = 0
    for _, kind in ipairs(kind_names) do
        out.kinds[kind] = {}
        for index, entry in ipairs(kinds[kind]) do
            -- 只有每类首例带字段探针（with_probe=true），其余站只带数据本身。
            out.kinds[kind][#out.kinds[kind] + 1] = describe(entry, kind, index == 1)
            emitted = emitted + 1
            if index == 1 then first_entries[kind] = entry end
        end
    end
    -- 全量口径的自检：前端要"每座站都能画结构"，所以这里必须能看出有没有采全。
    out.station_count_by_kind = {
        rail = #kinds.rail, street = #kinds.street, water = #kinds.water,
        air = #kinds.air, unknown = #kinds.unknown,
    }
    out.stations_emitted = emitted
    out.truncated = emitted >= FULL_STATION_LIMIT

    -- ★ v3 深挖节
    local deep = { kinds = {} }
    for _, kind in ipairs(kind_names) do
        local entry = first_entries[kind]
        if entry ~= nil then
            local params = (entry.construction ~= nil) and common.field(entry.construction, "params") or nil
            deep.kinds[kind] = {
                station_id = common.entity_id(entry.station),
                construction_file = entry.file,
                construction_id = entry.construction_id,
                params = deep_params(params),
                modules = deep_modules(params),
            }
        end
    end
    deep.res = deep_res()
    out.deep = deep

    -- ★ v4 站台负载探针（2026-09-30）
    -- 要回答：**能不能拿到"每座站此刻有多少人在等"**？
    -- 为什么问：容量已经采到了（`Station.pool.moreCapacity`，见 layer_stations.lua）。
    --   只要能同时拿到"当前等待量"，就能算占用率、做超容报警 —— 这正是官方车站统计里
    --   那个 `Overload` 列的意思（"A bad situation leads to a negative town growth effect"），
    --   也是官方车站图层"Stations that are overcrowded are colored red"的判据。
    -- 已知：`STATION.waiting` 读出来是 nil（context-probe 实测）—— 该字段不存在，别再试了。
    -- 四条候选路径**一次全探完**（探针最贵的是重启，别拆成几轮改）：
    --   ① `TRANSPORT_NETWORK` 实体怎么组织（`getSimPersonsAtTerminalForTransportNetwork` 的入参）
    --   ② 等待中的行人身上，`SIM_ENTITY_AT_TERMINAL` 有没有能定位到**具体站台**的字段
    --      （`line` 已验证存在，缺的是 terminal / station）
    --   ③ `stationSystem.getPersonNodeId2StationTerminalsMap()` 的真实形状（node → 站台）
    --   ④ 两个 system 上**到底有哪些方法**（一次列全，免得以后再为找方法名改探针）
    -- ⚠️ ② 会遍历 SIM_PERSON（数量可能很大），这一步可能偏慢 —— 探针是一次性的，可接受。
    local load_probe = {}
    do
        -- ① TRANSPORT_NETWORK：计数 + 前 3 个样本
        local tn_count, tn_samples = 0, {}
        pcall(function()
            common.safe_for_each_entity("TRANSPORT_NETWORK", function(entity)
                tn_count = tn_count + 1
                if #tn_samples < 3 then
                    local comp = common.safe_get_component(entity, "TRANSPORT_NETWORK", SILENT)
                    tn_samples[#tn_samples + 1] = {
                        entity_id = common.entity_id(entity),
                        probe = common.probe_fields(comp, {
                            "edges", "nodes", "graph", "carrier", "transportMode", "type", "size", "level",
                        }),
                    }
                end
            end, errors)
        end)
        load_probe.transport_network = { count = tn_count, samples = tn_samples }

        -- ② 等待中的行人 + 身上的组件（取样 3 个）
        local person_seen, person_samples = 0, {}
        pcall(function()
            common.safe_for_each_entity("SIM_PERSON", function(entity)
                person_seen = person_seen + 1
                if #person_samples >= 3 then return end
                local at_terminal = common.safe_get_component(entity, "SIM_ENTITY_AT_TERMINAL", SILENT)
                local at_vehicle = common.safe_get_component(entity, "SIM_ENTITY_AT_VEHICLE", SILENT)
                person_samples[#person_samples + 1] = {
                    entity_id = common.entity_id(entity),
                    at_terminal = common.probe_fields(at_terminal, {
                        "line", "terminal", "station", "node", "stop", "arrivalTime", "type", "cargo",
                    }),
                    at_vehicle = common.probe_fields(at_vehicle, { "vehicle", "line", "terminal", "seat" }),
                }
            end, errors)
        end)
        load_probe.person = { scanned = person_seen, samples = person_samples }

        -- ③ node → 站台 的映射形状（前 3 项）
        local node_map_count, node_map_samples = 0, {}
        pcall(function()
            local map = api.engine.system.stationSystem.getPersonNodeId2StationTerminalsMap()
            for key, value in pairs(map) do
                node_map_count = node_map_count + 1
                if #node_map_samples < 3 then
                    node_map_samples[#node_map_samples + 1] = {
                        -- ⚠️ 这里**不能**用 describe() —— 那是"描述车站"的函数（签名 entry/kind/with_probe），
                        --    拿它当通用 dump 用会得到一堆 nil。通用值预览要用文件级的
                        --    preview() / try_pairs()（try_pairs 还能看到 map 的**内层**结构）。
                        key = preview(key),
                        value = try_pairs(value, 3),
                    }
                end
            end
        end)
        load_probe.person_node_to_terminal = { count = node_map_count, samples = node_map_samples }

        -- ④ 两个 system 的方法名（一次列全）
        local function method_names(system)
            local names = {}
            pcall(function()
                for name in pairs(system) do names[#names + 1] = tostring(name) end
            end)
            table.sort(names)
            return names
        end
        pcall(function() load_probe.sim_person_methods = method_names(api.engine.system.simPersonSystem) end)
        pcall(function() load_probe.sim_cargo_methods = method_names(api.engine.system.simCargoSystem) end)
    end
    out.load_probe = load_probe

    -- ★ v5 站台负载探针（第二轮，2026-09-30 下午）
    -- 为什么要第二轮：用户在**游戏 UI 里亲眼看到**了「中山西站 → 经由 Hanoi中央车站 519 人」
    --   （官方手册也写着 overview 页 "a list of waiting cargo and passengers, grouped per line and direction"）
    --   ⇒ 这个数**引擎内部一定有**，只是没在 API 文档里露面。
    -- 第一轮（v4）的收获与缺口：
    --   ✅ 确认 `getPersonNodeId2StationTerminalsMap()` = 站台节点 → 子车站 id（7529 条，432318 实测反查对得上）
    --   ✅ 挖出 `simCargoSystem.getSimCargoAtTerminalForTransportNetwork`（文档里没有）
    --   ❌ 等待的行人身上**只有 line + arrivalTime**，terminal/station/node 全是 nil
    --   ❌ 那个映射的 key 只做了 tostring（preview），**没转 entity_id**
    --      ⇒ 拿不到可用的节点句柄，试不了任何下游接口。**这是第一轮最大的疏漏。**
    -- 本轮重点：`stationSystem` 实际有 **10 个方法，API 文档只列了 4 个** ——
    --   把未文档化的那几个全试一遍（尤其 getStationTerminalsForPersonNode）。
    local load_probe_v5 = {}
    do
        -- 把任意返回值 dump 成"类型 / 条数 / 前几项"的形状；出错也不炸。
        local function try_call(fn)
            local ok, value = pcall(fn)
            if not ok then return { error = tostring(value) } end
            if value == nil then return { value_type = "nil" } end
            local kind = type(value)
            if kind ~= "table" and kind ~= "userdata" then
                return { value_type = kind, value = tostring(value) }
            end
            return try_pairs(value, 3)
        end

        -- ① person node → 站台 映射：**这次把 key 转成 entity_id**（第一轮漏的就是这一步）
        local map_count, map_samples, person_nodes = 0, {}, {}
        pcall(function()
            local map = api.engine.system.stationSystem.getPersonNodeId2StationTerminalsMap()
            for key, value in pairs(map) do
                map_count = map_count + 1
                local node_id = common.entity_id(key)
                if node_id ~= nil and #person_nodes < 8 then person_nodes[#person_nodes + 1] = node_id end
                if #map_samples < 3 then
                    map_samples[#map_samples + 1] = {
                        key_entity_id = node_id,
                        key_type = type(key),
                        value = try_pairs(value, 3),
                    }
                end
            end
        end)
        load_probe_v5.person_node_map = { count = map_count, samples = map_samples }

        -- ② ★核心：拿①的节点句柄试 `getStationTerminalsForPersonNode`
        --    它若认，那"站台 → 车站"这条链就通了（缺的只剩"人 → 站台"）。
        local for_person_node = {}
        for i = 1, math.min(#person_nodes, 3) do
            local node = person_nodes[i]
            for_person_node[#for_person_node + 1] = {
                input = node,
                result = try_call(function()
                    return api.engine.system.stationSystem.getStationTerminalsForPersonNode(node)
                end),
            }
        end
        load_probe_v5.station_terminals_for_person_node = for_person_node

        -- ③ 与②配对的另两条（person edge / vehicle node）
        load_probe_v5.vehicle_node_map = try_call(function()
            return api.engine.system.stationSystem.getVehicleNodeId2StationTerminalsMap()
        end)

        -- ④ `getStations()` —— 若它一次给出所有站（甚至带等待数），那就最省事
        local stations_items, stations_count = {}, 0
        pcall(function()
            local all = api.engine.system.stationSystem.getStations()
            for key, value in pairs(all) do
                stations_count = stations_count + 1
                if #stations_items < 2 then
                    stations_items[#stations_items + 1] = { key = preview(key), value = try_pairs(value, 8) }
                end
            end
        end)
        load_probe_v5.get_stations = { count = stations_count, samples = stations_items }

        -- ⑤ destination → sp（名字暗示"目的地 → 人"，可能能反推人在哪个站等）
        load_probe_v5.destination_map = try_call(function()
            return api.engine.system.simPersonSystem.getDestination2SpMap()
        end)

        -- ⑥ 直接试 `getSimPersonsAtTerminalForTransportNetwork` —— 入参用 TRANSPORT_NETWORK 实体
        local tn_entities = {}
        pcall(function()
            common.safe_for_each_entity("TRANSPORT_NETWORK", function(entity)
                if #tn_entities < 3 then tn_entities[#tn_entities + 1] = common.entity_id(entity) end
            end, errors)
        end)
        local tn_tries = {}
        for i = 1, #tn_entities do
            local tn = tn_entities[i]
            tn_tries[#tn_tries + 1] = {
                input = tn,
                persons_at_terminal = try_call(function()
                    return api.engine.system.simPersonSystem.getSimPersonsAtTerminalForTransportNetwork(tn)
                end),
                persons_idle = try_call(function()
                    return api.engine.system.simPersonSystem.getSimPersonsIdleForTransportNetwork(tn)
                end),
                cargo_at_terminal = try_call(function()
                    return api.engine.system.simCargoSystem.getSimCargoAtTerminalForTransportNetwork(tn)
                end),
            }
        end
        load_probe_v5.transport_network_tries = tn_tries

        -- ⑦ transportNetworkSystem 只有两个方法，一并看形状
        load_probe_v5.tp_net_data = try_call(function()
            return api.engine.system.transportNetworkSystem.getTpNetData()
        end)
        load_probe_v5.tp_intersections = try_call(function()
            return api.engine.system.transportNetworkSystem.getIntersections()
        end)

        -- ⑧ 产业指标探针（用户 2026-09-30 截图：产量 / 发送 / 送达率 / 产品买家列表）
        -- 背景：用户拿"Zhongshan油井#2"的产业窗口问"这些数据找不找得到"。
        -- 现状问题：layer_industry.lua 采的 `produced_count` 用的是 `common.array_count(itemsProduced)` ——
        --   那是**数组条目数**（= 有几种产品），**不是产量**。用户要的是"400 单位"这种量。
        -- SIM_BUILDING 的 11 个字段里 itemsProduced / itemsShipped / itemsConsumed 是 table，
        --   但探针见到的样本 length=0（那几座厂当时没产量）—— 所以要**主动找一座有产量的**再看内容。
        -- 顺带直接问引擎 `simCargoSystem.getSimCargosForSource(厂)` —— 它是"这座厂生产出来的货"，
        --   很可能就是"发送量"的来源；而图 2 的"产品买家"列表应该对应 getSimCargosForTarget 那一路。
        local industry_probe = { scanned = 0, with_items = 0, samples = {} }
        pcall(function()
            common.safe_for_each_entity("SIM_BUILDING", function(entity)
                industry_probe.scanned = industry_probe.scanned + 1
                local building = common.safe_get_component(entity, "SIM_BUILDING", SILENT)
                if building == nil then return end
                local produced = common.field(building, "itemsProduced")
                local shipped = common.field(building, "itemsShipped")
                local consumed = common.field(building, "itemsConsumed")
                local n_produced = common.array_count(produced) or 0
                local n_shipped = common.array_count(shipped) or 0
                local n_consumed = common.array_count(consumed) or 0
                if (n_produced + n_shipped + n_consumed) == 0 then return end
                industry_probe.with_items = industry_probe.with_items + 1
                if #industry_probe.samples >= 3 then return end
                industry_probe.samples[#industry_probe.samples + 1] = {
                    entity_id = common.entity_id(entity),
                    name = common.field(building, "name"),
                    stock_list = common.field(building, "stockList"),
                    level = common.field(building, "level"),
                    upgrade_progress = common.field(building, "upgradeProgress"),
                    -- 这三个的**真实内容**（数组每项装什么：货种？数量？目的地？）
                    produced = try_ipairs(produced, 3),
                    shipped = try_ipairs(shipped, 3),
                    consumed = try_ipairs(consumed, 3),
                    -- 直接问引擎"这座厂产出的货"+"谁在等它的货"
                    cargo_from_source = try_call(function()
                        return api.engine.system.simCargoSystem.getSimCargosForSource(entity)
                    end),
                    cargo_to_target = try_call(function()
                        return api.engine.system.simCargoSystem.getSimCargosForTarget(entity)
                    end),
                }
            end, errors)
        end)
        load_probe_v5.industry = industry_probe
    end
    out.load_probe_v5 = load_probe_v5

    out.duration_ms = (common.clock() - started) * 1000
    return out
end

return M
