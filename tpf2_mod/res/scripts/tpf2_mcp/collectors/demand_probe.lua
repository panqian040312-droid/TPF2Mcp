-- 乘客 / 货物流量采集器（只读）
--
-- 背景：游戏自带脚本 res/scripts/mission/arrivaltracker.lua 证明引擎会派发
--   SimPersonSystem.OnCompletedLineUsage（乘客完成一次乘车）
--   SimCargoSystem.OnToArriveAtDestination（货物抵达目的地）
-- 存档里因此留下了累计计数（__ug_gui_game_info_passenger = 1594787）。
--
-- 本采集器做两件事：
--   1) 监听这两个事件，对事件实体（乘客/货物）做"数值字段直方图"，
--      以便离线判断哪个字段挂着 线路ID / 车辆ID / 车站ID；
--   2) 对指定实体（线路 / 车辆 / 车站）做字段普查（含嵌套子表），
--      找出引擎里是否真的存在 载客量 / 候客量 字段。
--
-- 所有操作包裹在 pcall 内；本文件不写入任何游戏状态，只往 mod 的 bridge 目录写 JSON。
-- 输出: <mod>/bridge/demand-probe.json

local json = require "tpf2_mcp/json"
local config = require "tpf2_mcp/config"

local M = {}

local MAX_DEPTH = 3
local MAX_KEYS = 90
local MAX_SEQ = 12
local HIST_LIMIT = 300
local WRITE_EVERY_TICKS = 60

-- 要普查的实体（来自存档快照，若存档已变则对应实体可能不存在，会安全跳过）
local TARGETS = {
    { kind = "line", id = 224503, label = "京广客运" },
    { kind = "line", id = 98983, label = "JY客运" },
    { kind = "vehicle", id = 159365, label = "列车41(16节)" },
    { kind = "vehicle", id = 234337, label = "列车12(8节)" },
    { kind = "station", id = 243069, label = "天津" },
    { kind = "station", id = 105581, label = "广州北站" },
}

local state = {
    schema_version = 1,
    source_status = "ENGINE_EVENT_HOOKS",
    events = { person = 0, cargo = 0, unhandled = 0 },
    errors = {},
    person_samples = {},
    cargo_samples = {},
    numeric_hist = {},      -- 字段路径 -> { 值 -> 次数 }
    entity_inventory = {},  -- 目标实体字段普查
    first_tick_done = false,
    tick_count = 0,
    phase = nil,
}


local function note_error(where, err)
    if #state.errors >= 40 then return end
    state.errors[#state.errors + 1] = tostring(where) .. ": " .. tostring(err)
end


local function bridge_dir()
    local dir = config and config.bridge_dir
    if type(dir) ~= "string" or dir == "" then return nil end
    return dir
end


local function write_json(name, object)
    local dir = bridge_dir()
    if dir == nil then return false, "bridge dir unavailable" end
    local handle, err = io.open(dir .. "/" .. name, "w")
    if handle == nil then return false, tostring(err) end
    local ok, encoded = pcall(json.encode, object)
    if not ok then handle:close() return false, "encode failed" end
    handle:write(encoded)
    handle:close()
    return true
end


-- 把任意 Lua 值转成可 JSON 序列化的结构（深度与宽度受限）
local function describe(value, depth)
    local t = type(value)
    if t == "nil" then return nil end
    if t == "number" or t == "string" or t == "boolean" then return value end
    if t ~= "table" and t ~= "userdata" then return "<" .. t .. ">" end
    if depth >= MAX_DEPTH then return "<" .. t .. ">" end

    local out = {}
    local count = 0
    pcall(function()
        for key, item in pairs(value) do
            count = count + 1
            if count > MAX_KEYS then break end
            out[tostring(key)] = describe(item, depth + 1)
        end
    end)
    -- 序列部分（部分 userdata 只支持 1..#v）
    if count == 0 then
        pcall(function()
            local n = #value
            if n and n > 0 then
                for i = 1, math.min(n, MAX_SEQ) do
                    out[tostring(i)] = describe(value[i], depth + 1)
                end
            end
        end)
    end
    if count == 0 and next(out) == nil then return "<" .. t .. ">" end
    return out
end


local function tally(path, value)
    local hist = state.numeric_hist[path]
    if hist == nil then
        hist = {}
        state.numeric_hist[path] = hist
    end
    local key = tostring(value)
    if hist[key] == nil then
        if state.numeric_hist_count == nil then state.numeric_hist_count = 0 end
        if state.numeric_hist_count > HIST_LIMIT * 40 then return end
        state.numeric_hist_count = state.numeric_hist_count + 1
    end
    hist[key] = (hist[key] or 0) + 1
end


-- 遍历实体的一层/两层字段，把数值字段计入直方图
local function tally_numeric(value, prefix, depth)
    local t = type(value)
    if t == "number" then
        tally(prefix, value)
        return
    end
    if (t ~= "table" and t ~= "userdata") or depth >= 2 then return end
    pcall(function()
        local n = 0
        for key, item in pairs(value) do
            n = n + 1
            if n > 40 then break end
            tally_numeric(item, prefix .. "." .. tostring(key), depth + 1)
        end
    end)
end


local function safe_get(id)
    if type(id) ~= "number" then return nil end
    local ok, entity = pcall(function() return game.interface.getEntity(id) end)
    if ok then return entity end
    return nil
end


local function snapshot_entity(kind, id, label)
    local entity = safe_get(id)
    if entity == nil then
        state.entity_inventory[tostring(id)] = { kind = kind, label = label, readable = false }
        return
    end
    local entry = { kind = kind, label = label, readable = true, fields = describe(entity, 0) }
    state.entity_inventory[tostring(id)] = entry
    tally_numeric(entity, kind .. ":" .. tostring(id), 0)
end


function M.handle_event(src, id, name, params)
    pcall(function()
        if id == "SimPersonSystem" and name == "OnCompletedLineUsage" then
            state.events.person = state.events.person + 1
            local entity = safe_get(params)
            if entity ~= nil then
                state.persons_seen = (state.persons_seen or 0) + 1
                if #state.person_samples < 3 then
                    state.person_samples[#state.person_samples + 1] = describe(entity, 0)
                end
                if state.persons_seen <= 4000 then
                    tally_numeric(entity, "person", 0)
                end
            end
        elseif id == "SimCargoSystem" and name == "OnToArriveAtDestination" then
            state.events.cargo = state.events.cargo + 1
            local entity = safe_get(params)
            if entity ~= nil then
                state.cargo_seen = (state.cargo_seen or 0) + 1
                if #state.cargo_samples < 3 then
                    state.cargo_samples[#state.cargo_samples + 1] = describe(entity, 0)
                end
                if state.cargo_seen <= 4000 then
                    tally_numeric(entity, "cargo", 0)
                end
            end
        else
            state.events.unhandled = state.events.unhandled + 1
            if state.last_unhandled == nil or state.last_unhandled.id ~= tostring(id) then
                state.last_unhandled = { id = tostring(id), name = tostring(name) }
            end
        end
    end)
end


function M.tick()
    pcall(function()
        state.tick_count = (state.tick_count or 0) + 1
        if state.first_tick_done == false then
            state.first_tick_done = true
            state.phase = "probe"
            for _, target in ipairs(TARGETS) do
                snapshot_entity(target.kind, target.id, target.label)
            end
            write_json("demand-probe.json", state)
            state.phase = "collecting"
        end
        if state.tick_count % WRITE_EVERY_TICKS == 0 then
            local now = os and os.time and os.time() or nil
            state.last_write = now
            write_json("demand-probe.json", state)
        end
    end)
end


function M.summary()
    return {
        events = state.events,
        persons_seen = state.persons_seen or 0,
        cargo_seen = state.cargo_seen or 0,
        bridge = bridge_dir(),
    }
end


return M
