-- 客流图层（流式）—— 把客流从「外部主动拉」改成「mod 自驱推」
--
-- 为什么要有这一层：
--   客流原先只有两条路 ——
--     ① MCP 工具 `get_line_demand`：一次查一条线，要外部主动发命令；
--     ② 手动脚本 `collect-line-demand.py`：遍历所有线存 SQLite。
--   ② 走的正是 layer_registry 顶部注释点名要淘汰的模式（"靠外部 Python 服务按时发命令来取，
--   那是 bridge 单槽邮箱争锁的根源"）。本层把它变成和其余九层一样：mod 按周期自己采、写 JSON、
--   Python 侧纯读。产出 `bridge/layer-passenger.json`。
--
-- 🔴 为什么必须是流式：一条线要遍历它**车上和候车的全部**乘客/货物实体，
--    273 条线一次做完会卡帧。所以照抄 layer_terrain 的分帧写法：每个 update 采 BATCH 条线，
--    全部采完才交出产物。
--
-- 架构边界（0_core_shared/ARCHITECTURE.md §四）：本层**只读 + 机械整理**。
--   · 不写任何游戏状态；
--   · 不做业务判据 —— 不输出"实载率好不好""该不该加车"这类要看人拍板的结论；
--   · 字段**全部复用** `line_demand.collect` 已有的名字，不新造。

local common = require "tpf2_mcp/collectors/common"
local line_demand = require "tpf2_mcp/collectors/line_demand"

local M = {}

-- 每个 update 采几条线。数越小越不容易掉帧，但采满一轮的帧数越多。
local BATCH = 4
-- 最多采多少条线（防止异常存档把产物撑爆）。本存档 273 条。
local LINE_LIMIT = 400
-- 单条线最多遍历多少实体（透传给 line_demand 的上限保护）。
local MAX_ENTITIES = 8000
-- by_journey（按上/下车站的 OD 分组）每条线最多留几条 —— 明细很长，只留头部。
-- 字段名不变，只是截断，所以不算新字段。
local JOURNEY_LIMIT = 12

-- 重采周期（update 数）。客流变化比车辆慢得多，可以拍稀疏些。
local RESAMPLE_EVERY = 12000
-- 启动后先跳过多少 update（避开其余各层的首次采集相位；340-46=294 不是 15 的倍数）。
local START_DELAY = 340

local job = nil
local last_payload_shape = nil

-- 取某点的游戏时间（毫秒）。写法与 line_demand.lua 一致 ——
-- TODO(架构): 这段与 line_demand.lua 的 `game_time_ms` 重复，待提进 0 层 common.lua。
local function game_time_ms()
    local ok_world, world = pcall(api.engine.util.getWorld)
    if not ok_world or world == nil then return nil end
    local value = common.safe_get_component(world, "GAME_TIME", {})
    return common.field(value, "gameTime")
end

-- 玩家全部线路。
-- 🔴 用 `common.safe_for_each_entity("LINE", ...)` —— 全项目其余各层都是这么枚举线路的
--    （layer_lines.lua:140 / economy_probe.lua:269 / line.lua:48），复用优先。
--    ⚠️ 不要用 `api.engine.system.lineSystem.getLines()`：实测它**返回 userdata 而不是 table**
--    （2026-10-04 部署验证：`type(value) ~= "table"` 成立 → 整层直接 ERROR）。
--    项目里这个方法从无成功先例，唯一用过它的是从未验证的 line_finance_probe.lua。
local function collect_lines()
    local out = {}
    local errors = {}
    local ok, info = common.safe_for_each_entity("LINE", function(entity)
        if #out < LINE_LIMIT then out[#out + 1] = entity end
    end, errors)
    if not ok then return nil, "enumerate LINE: " .. tostring(info) end
    if #out == 0 then return nil, "no LINE entities found" end
    return out, nil
end

-- 把 line_demand 的完整结果裁成汇总：丢掉 by_journey 明细的尾巴，其余字段名原样保留。
local function summarize_side(block)
    if type(block) ~= "table" then return nil end
    local out = {
        total_for_line = block.total_for_line,
        waiting = block.waiting,
        onboard = block.onboard,
        other = block.other,
        status = block.status,
        truncated = block.truncated,
        classified = block.classified,
        median_waiting_seconds = block.median_waiting_seconds,
        p90_waiting_seconds = block.p90_waiting_seconds,
        max_waiting_seconds = block.max_waiting_seconds,
        average_waiting_seconds = block.average_waiting_seconds,
        waiting_over_1h = block.waiting_over_1h,
        vehicles = block.vehicles,
    }
    -- 按「上车站（line_stop_0）」聚合 waiting / onboard。
    -- 🔴 **必须在截断之前算** —— 否则只统计得到前 JOURNEY_LIMIT 条 OD。
    -- 这是**机械整理**（不是业务判据，合规 ARCHITECTURE §四）：R26 要的
    -- 「每个停站有多少人在候车」由它直接给出；下游拿 layer-lines.json 的
    -- `stops[].index` 就能把停站下标翻成车站 id。
    if type(block.by_journey) == "table" then
        local wait_by_stop, board_by_stop = {}, {}
        for _, journey in ipairs(block.by_journey) do
            local stop = journey.line_stop_0
            if type(stop) == "number" then
                wait_by_stop[stop] = (wait_by_stop[stop] or 0) + (journey.waiting or 0)
                board_by_stop[stop] = (board_by_stop[stop] or 0) + (journey.onboard or 0)
            end
        end
        local by_stop = {}
        for stop, waiting in pairs(wait_by_stop) do
            by_stop[#by_stop + 1] = { stop = stop, waiting = waiting, onboard = board_by_stop[stop] or 0 }
        end
        table.sort(by_stop, function(a, b) return a.stop < b.stop end)
        if #by_stop > 0 then out.by_stop = by_stop end
    end

    if type(block.by_journey) == "table" and #block.by_journey > 0 then
        local head = {}
        for index = 1, math.min(#block.by_journey, JOURNEY_LIMIT) do
            head[index] = block.by_journey[index]
        end
        out.by_journey = head
    end
    if type(block.by_cargo) == "table" and #block.by_cargo > 0 then
        out.by_cargo = block.by_cargo
    end
    return out
end

local function start_job()
    local lines, error_message = collect_lines()
    if lines == nil then return nil, error_message end
    return {
        lines = lines,
        index = 0,
        rows = {},
        errors = 0,
        first_error = nil,
    }
end

local function finish(job_ref, update_count)
    local payload = {
        status = "OK",
        source_status = "ENGINE_COMPONENT_CLASSIFIED",
        game_time_ms = game_time_ms(),
        counts = { total = #job_ref.rows, lines_available = #job_ref.lines, errors = job_ref.errors },
        lines = job_ref.rows,
        errors = {},
    }
    if job_ref.first_error ~= nil then
        payload.errors[#payload.errors + 1] = { note = job_ref.first_error }
    end
    payload.sampled_at_update = update_count
    return payload
end

-- 流式约定（layer_registry 里走 advance 分支）：
--   返回 nil   = 还在采，下一帧继续
--   返回 table = 采完了，这就是产物
function M.advance(should_start, update_count)
    if job == nil then
        if not should_start then return nil end
        local started, error_message = start_job()
        if started == nil then
            return {
                status = "ERROR",
                source_status = "ENGINE_OBSERVED",
                error = error_message,
                errors = { { note = error_message } },
            }
        end
        job = started
        return nil
    end

    local produced = 0
    while job.index < #job.lines and produced < BATCH do
        job.index = job.index + 1
        produced = produced + 1

        local line = job.lines[job.index]
        local line_id = tonumber(tostring(common.entity_id(line)))
        if line_id == nil then
            job.errors = job.errors + 1
            if job.first_error == nil then job.first_error = "line entity has no numeric id at index " .. job.index end
        else
            local ok, detail = pcall(line_demand.collect, line_id, MAX_ENTITIES)
            if ok and type(detail) == "table" then
                job.rows[#job.rows + 1] = {
                    line_id = line_id,
                    passengers = summarize_side(detail.passengers),
                    cargo = summarize_side(detail.cargo),
                }
            else
                job.errors = job.errors + 1
                if job.first_error == nil then job.first_error = "line " .. line_id .. ": " .. tostring(detail) end
            end
        end
    end

    if job.index < #job.lines then return nil end

    local payload = finish(job, update_count)
    last_payload_shape = payload.counts
    job = nil
    return payload
end

-- 供 heartbeat 带出状态用（layer_registry 只看 status，这个函数给人工排查留个口子）
function M.shape()
    return last_payload_shape
end

return M
