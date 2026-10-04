-- 站台「容量」探针 v6（只读，单站精查）
--
-- v5 的成果（已确认）：
--   ✅ `stationSystem.getStationTerminalsForPersonEdge(edge)` 返回的是**一串数字 id**
--      （实测 240014 / 129189）—— EdgeId → 站台 的映射打通了。
--   ✅ 广州北站（station 实体 104701）`pool.moreCapacity = 200`（= UI 里那行「共享池 76/200」）。
--   ✅ 它有 3 个站台，**每个站台 28 条 personEdge**；站台 1 的前 4 条 free = [22,12,12,22]，
--      周期 4 ⇒ 7 轮 × 68 = **476** —— 与 UI 的「站台 1 = 0/476」**精确吻合**。
--      ⇒ **容量模型成立：站台容量 = Σ(该站台每条候车边的剩余位置)**
--         （占用为 0 时，Σ free 就是容量本身）
--
-- v5 没跑完的原因：`MAX_CALLS = 12` 太小，3 站台 × 28 边 = 84 次调用。
--
-- v6 只做一件事：**把广州北站 3 个站台的 28×3 条边全部采回来**，逐条报 free，
-- 算 Σ，然后和 UI 的 476 / 1170 / 476 / 75 逐行对照。
--
-- 输出: bridge/terminal-waiting-probe.json
--
-- 🔴 所有引擎调用必须写成**完整链式** `api.engine.system.<system>.<method>(...)`。

local common = require "tpf2_mcp/collectors/common"

local M = {}

local MAX_CALLS = 120
local TARGET_STATION_ID = 104701          -- 广州北站
local MAX_TERMINALS = 6
local MAX_EDGES_PER_TERMINAL = 40
local DECODE_EDGES = 2
local PAIR_NAMES = { "first", "second", "entity", "value", "key", "id", "terminal", "station", "index" }

local function safe_tostring(value)
    local ok, text = pcall(tostring, value)
    return ok and text or nil
end

local function shape_of(value)
    local kind = type(value)
    if kind == "nil" then return { type = "nil" } end
    if kind == "number" or kind == "string" or kind == "boolean" then
        return { type = kind, value = value }
    end
    if kind == "table" then
        return { type = "table", array_count = common.array_count(value), text = safe_tostring(value) }
    end
    return { type = kind, text = safe_tostring(value) }
end

local function decode_item(item)
    local out = { shape = shape_of(item) }
    for _, name in ipairs(PAIR_NAMES) do
        local ok, value = pcall(function() return item[name] end)
        if ok and value ~= nil then
            local kind = type(value)
            out[#out + 1] = { via = name, type = kind, text = safe_tostring(value),
                              value = (kind == "number" or kind == "string") and value or nil }
        end
    end
    for index = 1, 2 do
        local ok, value = pcall(function() return item[index] end)
        if ok and value ~= nil then
            local kind = type(value)
            out[#out + 1] = { via = "[" .. index .. "]", type = kind, text = safe_tostring(value),
                              value = (kind == "number" or kind == "string") and value or nil }
        end
    end
    return out
end

local function decode_vector(result, limit)
    local items = {}
    if result == nil then return items end
    pcall(function()
        for key, value in pairs(result) do
            if #items < limit then
                items[#items + 1] = { key = safe_tostring(key), key_type = type(key), decoded = decode_item(value) }
            end
        end
    end)
    return items
end

function M.collect()
    local state = { calls = 0, stopped_early = false, errors = {} }
    local report = {
        status = "OK",
        source_status = "READ_ONLY_PROBE",
        probe_version = 6,
        purpose = "站台容量 v6：广州北站(104701) 三个站台的全部候车边 free 之和，对齐 UI 的 476/1170/476/75",
        guard = { max_calls = MAX_CALLS, target_station_id = TARGET_STATION_ID },
    }

    local function attempt(label, fn, ...)
        if state.calls >= MAX_CALLS then
            state.stopped_early = true
            return nil, "call budget exhausted"
        end
        state.calls = state.calls + 1
        local ok, value = pcall(fn, ...)
        if ok then return value, nil end
        state.errors[#state.errors + 1] = { label = label, error = safe_tostring(value) }
        return nil, safe_tostring(value)
    end

    -- 顺便复采两个 EdgeId → 站台 id 的映射（v5 已确认可用）
    local map = attempt("getEdgeInfoMap()", function()
        return api.engine.system.simPersonAtTerminalSystem.getEdgeInfoMap()
    end)
    local edge_keys = {}
    if map ~= nil then
        pcall(function()
            for key in pairs(map) do
                if #edge_keys < DECODE_EDGES then edge_keys[#edge_keys + 1] = key end
            end
        end)
    end
    local decoded = {}
    for index, edge in ipairs(edge_keys) do
        local result, error_message = attempt("getStationTerminalsForPersonEdge(edge)", function()
            return api.engine.system.stationSystem.getStationTerminalsForPersonEdge(edge)
        end)
        decoded[#decoded + 1] = { index = index, error = error_message,
                                  shape = result ~= nil and shape_of(result) or nil,
                                  items = decode_vector(result, 3) }
    end
    report.decoded_edge_terminals = decoded

    -- 目标站：只对命中实体读组件
    local found_entity, seen = nil, 0
    common.safe_for_each_entity("STATION", function(entity)
        if found_entity ~= nil then return end
        seen = seen + 1
        if tonumber(tostring(common.entity_id(entity))) == TARGET_STATION_ID then found_entity = entity end
    end, state.errors)
    report.stations_scanned_for_target = seen

    if found_entity == nil then
        report.status = "TARGET_STATION_NOT_FOUND"
        report.calls_made = state.calls
        report.errors = state.errors
        return report
    end

    local station = common.safe_get_component(found_entity, "STATION", {})
    local pool = common.field(station, "pool")
    local more_capacity = pool ~= nil and common.field(pool, "moreCapacity") or nil
    report.target = {
        station_id = TARGET_STATION_ID,
        station_name = common.name_from_component(station),
        cargo = common.field(station, "cargo"),
        pool_more_capacity = type(more_capacity) == "number" and more_capacity or nil,
    }

    local terminals = common.sequence_values(common.field(station, "terminals"))
    report.target.terminal_count = terminals ~= nil and #terminals or 0

    local terminal_reports, first_edge = {}, nil
    if terminals ~= nil then
        for tIndex = 1, math.min(#terminals, MAX_TERMINALS) do
            local terminal = terminals[tIndex]
            local entry = { index = tIndex, tag = common.field(terminal, "tag"), free = {}, free_sum = 0, edges_done = 0 }
            local person_edges = common.sequence_values(common.field(terminal, "personEdges"))
            entry.person_edge_count = person_edges ~= nil and #person_edges or 0
            if person_edges ~= nil then
                for eIndex = 1, math.min(#person_edges, MAX_EDGES_PER_TERMINAL) do
                    local person_edge = person_edges[eIndex]
                    if first_edge == nil then first_edge = person_edge end
                    local free = attempt("getNumFreePlaces(personEdge)", function()
                        return api.engine.system.simPersonAtTerminalSystem.getNumFreePlaces(person_edge)
                    end)
                    local value = type(free) == "number" and free or nil
                    entry.free[#entry.free + 1] = value
                    if value ~= nil then
                        entry.free_sum = entry.free_sum + value
                        entry.edges_done = entry.edges_done + 1
                    end
                end
            end
            terminal_reports[#terminal_reports + 1] = entry
        end
    end
    report.target.terminals = terminal_reports

    if first_edge ~= nil then
        local result, error_message = attempt("getStationTerminalsForPersonEdge(targetEdge)", function()
            return api.engine.system.stationSystem.getStationTerminalsForPersonEdge(first_edge)
        end)
        report.round_trip = { error = error_message,
                              shape = result ~= nil and shape_of(result) or nil,
                              items = decode_vector(result, 3) }
    end

    report.calls_made = state.calls
    report.stopped_early = state.stopped_early
    report.errors = state.errors
    return report
end

return M
