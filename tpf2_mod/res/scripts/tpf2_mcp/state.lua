local config = require "tpf2_mcp/config"
local json = require "tpf2_mcp/json"
local town_collector = require "tpf2_mcp/collectors/town"
local industry_collector = require "tpf2_mcp/collectors/industry"
local station_collector = require "tpf2_mcp/collectors/station"
local line_collector = require "tpf2_mcp/collectors/line"
local vehicle_collector = require "tpf2_mcp/collectors/vehicle"
local company_collector = require "tpf2_mcp/collectors/company"
local operations_probe = require "tpf2_mcp/collectors/operations_probe"
local cargo_collector = require "tpf2_mcp/collectors/cargo"
local ui_source_probe = require "tpf2_mcp/collectors/ui_source_probe"
local context_probe = require "tpf2_mcp/collectors/context_probe"
local dynamic_probe = require "tpf2_mcp/collectors/dynamic_probe"
local write_api_probe = require "tpf2_mcp/collectors/write_api_probe"
local vehicle_write_probe = require "tpf2_mcp/collectors/vehicle_write_probe"
local line_raw_probe = require "tpf2_mcp/collectors/line_raw_probe"
local line_creation_probe = require "tpf2_mcp/collectors/line_creation_probe"
local api_inventory = require "tpf2_mcp/collectors/api_inventory"
local station_geometry = require "tpf2_mcp/collectors/station_geometry"
local rail_network = require "tpf2_mcp/collectors/rail_network"
local operational_telemetry = require "tpf2_mcp/collectors/operational_telemetry"
local simulation_collector = require "tpf2_mcp/collectors/simulation"
local line_demand = require "tpf2_mcp/collectors/line_demand"
local world_probe = require "tpf2_mcp/collectors/world_probe"
local route_probe = require "tpf2_mcp/collectors/route_probe"
local station_struct_probe = require "tpf2_mcp/collectors/station_struct_probe"
local economy_probe = require "tpf2_mcp/collectors/economy_probe"
local line_finance_probe = require "tpf2_mcp/collectors/line_finance_probe"
local terminal_waiting_probe = require "tpf2_mcp/collectors/terminal_waiting_probe"

local M = {}
local cached_snapshot = nil
local cached_at = 0
local cached_station_geometry = nil
local cached_rail_network = nil
local cached_world_probe = nil
local cached_route_probe = nil
local cached_station_struct_probe = nil
local cached_economy_probe = nil
local cached_line_finance_probe = nil

local function now()
    return os and os.time and os.time() or 0
end

function M.snapshot(sequence, force_refresh)
    local current_time = now()
    local refresh_interval = tonumber(config.snapshot_refresh_interval_seconds) or 2
    if not force_refresh and cached_snapshot and current_time - cached_at < refresh_interval then
        return cached_snapshot
    end
    local game = { status = "available", api_status = "runtime_verified" }
    local api_ok, api_error = pcall(function()
        game.world_entity = tostring(api.engine.util.getWorld())
        game.player_entity = tostring(api.engine.util.getPlayer())
    end)
    if not api_ok then
        game.status = "unavailable"
        game.api_status = "runtime_error"
        game.reason = tostring(api_error)
    end
    local towns, town_status = town_collector.collect()
    local industries, industry_status = industry_collector.collect()
    local stations, station_status = station_collector.collect()
    local lines, line_status = line_collector.collect()
    local vehicles, vehicle_status = vehicle_collector.collect()
    local companies, company_status = company_collector.collect()
    local cargo_types, cargo_status = cargo_collector.collect()
    local simulation, simulation_status = simulation_collector.collect()
    local snapshot = {
        -- File bridge protocol stays at v1. This is the independently versioned
        -- normalized world-snapshot contract.
        schema_version = tonumber(config.snapshot_schema_version) or 5,
        sequence = sequence,
        timestamp = current_time,
        metadata = {
            sequence = sequence,
            timestamp = current_time,
            field_sources = {
                cargo_types = "api.res.cargoTypeRep.getAll",
                ["vehicles[].capacity_total"] = "api.engine.component.TRANSPORT_VEHICLE.config.capacities",
                ["lines[].frequency_seconds"] = "game.interface.getEntity(line_id).frequency (1 / raw value)",
                -- ⚠️ `rate` 的**语义官方没有任何定义**：`api.type.Line` 里根本没有这个字段，
                --    它只出现在 `game.interface.getEntity(id)` 的聚合表里。
                --    本项目把它叫 throughput 是**我们自己的命名**，不是引擎口径。
                --    2026-10-03 实测：273 条线 Σ(rate × defaultPrice) = 5.5e6，
                --    而账本 INCOME 累计 3.24e11 —— **差 5 个数量级** ⇒
                --    它绝不是「件数 / 吨位」这类可以直接乘运价的量。
                --    🔴 别拿它算收入或运量。要算运量得另找口径（`LINE.itemsTransported` 还没验证）。
                ["lines[].throughput"] = "game.interface.getEntity(line_id).rate（⚠️ 语义未验证，勿当运量用）",
            },
            collector_status = { towns = town_status, industries = industry_status, stations = station_status, lines = line_status, vehicles = vehicle_status, company = company_status, cargo_types = cargo_status, simulation = simulation_status },
        },
        game = game, simulation = simulation,
        company = companies[1] or json.object({}), towns = towns, industries = industries, stations = stations, lines = lines, vehicles = vehicles, cargo_types = cargo_types,
    }
    cached_snapshot = snapshot
    cached_at = current_time
    return snapshot
end

function M.company_probe()
    local ok, result = pcall(company_collector.probe)
    if ok then return result end
    return { error = tostring(result) }
end

function M.write_api_probe()
    local ok, value = pcall(write_api_probe.probe)
    return ok and value or { error = tostring(value), write_command_sent = false }
end

function M.vehicle_write_probe()
    local ok, value = pcall(vehicle_write_probe.probe)
    return ok and value or { error = tostring(value), write_command_sent = false }
end

function M.semantic_probe()
    local function run(collector)
        local ok, value = pcall(collector.probe)
        return ok and value or { error = tostring(value) }
    end
    return { lines = run(line_collector), vehicles = run(vehicle_collector), industries = run(industry_collector) }
end

function M.operations_probe()
    local ok, result = pcall(operations_probe.all)
    return ok and result or { error = tostring(result) }
end

function M.ui_source_probe()
    local ok, result = pcall(ui_source_probe.collect)
    return ok and result or { error = tostring(result) }
end

function M.context_probe()
    local ok, result = pcall(context_probe.collect)
    return ok and result or { context = "game_script.update", error = tostring(result) }
end

function M.dynamic_probe()
    local ok, result = pcall(dynamic_probe.all)
    return ok and result or { error = tostring(result) }
end

function M.line_raw_probe()
    local ok, result = pcall(line_raw_probe.collect)
    return ok and result or { error = tostring(result), write_command_sent = false }
end

function M.line_creation_probe()
    local ok, result = pcall(line_creation_probe.collect)
    return ok and result or { error = tostring(result), write_command_sent = false }
end

-- 水运 / 航空航路探针（只读）：船和飞机不挂在 BASE_EDGE_* 上，它们的路径
-- 在引擎的 shipMoveSystem / aircraftMoveSystem / runwaySystem / tpNetLinkSystem 里。
-- 航路属于**基础设施**（跑道、泊位、网络链接），一次进程内不变 → 成功后缓存；
-- 失败不缓存，下次 get_game_state 还能重试（避免启动瞬间的时机问题被永久记住）。
function M.route_probe()
    if cached_route_probe ~= nil then return cached_route_probe end
    local ok, result = pcall(route_probe.collect)
    if not ok then return { error = tostring(result), write_command_sent = false } end
    cached_route_probe = result
    return result
end

-- 车站结构探针（只读）：四类站（铁路/汽车/码头/机场）都是"一个 .con + 若干 .module 格子"，
-- 这个探针回答"模块网格能不能从 Lua 读出来"，以及"水运/公路/航空站的 STATION.terminals 是否存在"。
-- 结论一次进程内不变 → 成功后缓存；失败不缓存，下次 get_game_state 还能重试。
function M.station_struct_probe()
    if cached_station_struct_probe ~= nil then return cached_station_struct_probe end
    local ok, result = pcall(station_struct_probe.collect)
    if not ok then return { error = tostring(result), write_command_sent = false } end
    cached_station_struct_probe = result
    return result
end

-- 经济探针（只读）：公司账本（整体收支）+ 每条线的维护费/运价/运量。
-- 用户 2026-09-30 定的运营前提是"城镇发展优先、保证整体盈利"，所以判据的红线在**整体盈亏**；
-- 而账本/维护费在现有产物里都没有，靠这个探针补。同样成功后缓存（一次进程内不变）。
function M.economy_probe()
    if cached_economy_probe ~= nil then return cached_economy_probe end
    local ok, value = pcall(economy_probe.collect)
    cached_economy_probe = ok and value or { status = "ERROR", error = tostring(value) }
    return cached_economy_probe
end

-- 线路财务探针（只读）：用户 2026-10-02 问「游戏里能单独看每条线的盈亏，引擎给不给 mod 读」。
-- 已排除 system 接口 / Line 组件两条路 / 玩家账本三个方向，只剩 `LOG_BOOK` 组件没验证过
-- —— 本探针去问它，顺带把 `game.config` 里维护费周期（chargeMaintenanceInterval）读出来。
-- 一次进程内不变 → 成功后缓存。
function M.line_finance_probe()
    if cached_line_finance_probe ~= nil then return cached_line_finance_probe end
    local ok, value = pcall(line_finance_probe.collect)
    cached_line_finance_probe = ok and value or { status = "ERROR", error = tostring(value) }
    return cached_line_finance_probe
end

-- 站台候车人数 / 剩余位数探针。
-- ⚠️ 极度克制（最多 6 次调用、只碰 1 个站 2 个站台）—— 车站侧接口有原生崩溃前科，
--   见 collectors/terminal_waiting_probe.lua 顶部说明。
-- 一次进程内结果不变 → 成功后缓存，所以挂在 get_game_state 上不会反复跑。
local cached_terminal_waiting_probe = nil

function M.terminal_waiting_probe()
    if cached_terminal_waiting_probe ~= nil then return cached_terminal_waiting_probe end
    local ok, value = pcall(terminal_waiting_probe.collect)
    cached_terminal_waiting_probe = ok and value or { status = "ERROR", error = tostring(value) }
    return cached_terminal_waiting_probe
end

function M.api_type_inventory() local ok, value = pcall(api_inventory.type_inventory); return ok and value or { error = tostring(value) } end
function M.api_command_inventory() local ok, value = pcall(api_inventory.command_inventory); return ok and value or { error = tostring(value) } end
function M.world_probe()
    if cached_world_probe ~= nil then return cached_world_probe end
    local ok, value = pcall(world_probe.probe)
    cached_world_probe = ok and value or { error = tostring(value) }
    return cached_world_probe
end
function M.station_geometry()
    if cached_station_geometry ~= nil then return cached_station_geometry end
    -- 站群 id 交给采集器自己挑。这里原本写死 552273 —— 那个组在存档里不存在，
    -- 产物永远是 STATION_GROUP_UNAVAILABLE（每次 get_game_state 都白跑一趟）。
    local ok, value = pcall(station_geometry.collect, nil, 1200)
    cached_station_geometry = ok and value or { status = "ERROR", error = tostring(value), write_command_sent = false }
    return cached_station_geometry
end

function M.rail_network()
    if cached_rail_network ~= nil then return cached_rail_network end
    local ok, value = pcall(rail_network.collect)
    cached_rail_network = ok and value or { status = "ERROR", error = tostring(value), write_command_sent = false }
    return cached_rail_network
end

function M.set_track_resources(entries)
    rail_network.set_track_resources(entries)
    cached_rail_network = nil
end

function M.operational_telemetry(section)
    local ok, value = pcall(operational_telemetry.collect, section)
    return ok and value or { status = "ERROR", error = tostring(value), write_command_sent = false }
end

function M.line_demand(line_id, maximum)
    local ok, value = pcall(line_demand.collect, line_id, maximum)
    return ok and value or { status = "ERROR", line_id = line_id, error = tostring(value) }
end

function M.vehicle_dispatch_state(vehicle_id, maximum)
    local telemetry = M.operational_telemetry("vehicles_live")
    local live = nil
    for _, vehicle in ipairs(telemetry.vehicles or {}) do
        if vehicle.entity_id == vehicle_id then live = vehicle break end
    end
    if live == nil then return { status = "ENTITY_NOT_FOUND", vehicle_id = vehicle_id } end
    return {
        schema_version = 1,
        source_status = "ENGINE_OBSERVED_DYNAMIC_WITH_CLASSIFIED_LOAD",
        vehicle = live,
        demand = type(live.line_id) == "number" and M.line_demand(live.line_id, maximum) or nil,
    }
end

return M
