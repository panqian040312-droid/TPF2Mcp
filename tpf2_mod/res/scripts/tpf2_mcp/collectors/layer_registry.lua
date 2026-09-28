-- 图层注册表 —— mod 自驱推送的派发中心
--
-- 为什么要有它：多图层地图要的新数据，不再靠外部 Python 服务"按时发命令"来取
-- （那是 bridge 单槽邮箱争锁的根源），改由 mod 自己在 tick 里按周期采集并写文件，
-- Python 侧退化成纯读。这也是 `heartbeat.json` 早就验证过的模式。
--
-- 挂载点：runtime.lua 的 M.tick() 里，operations.tick() 之后、poll_interval 的
-- early-return 之前 —— 必须在那之前，否则调度频率会被 bridge 轮询间隔（默认 5 个
-- update）绑死，动态层就没法更快。
--
-- 调度用 update 计数而不是真实时间：update 频率由引擎帧率决定、与游戏速度倍率无关，
-- 所以"每 N 个 update"在 1x 和 10x 下行为一致。游戏暂停时 tick 不跑，那也无妨 ——
-- 数据本来就没变。
--
-- 输出：bridge/layer-<name>.json（平铺命名。mod 沙箱里 io.open 不会建目录，
-- 所以不能用 bridge/layers/ 这种子目录，除非由外部 Python 服务预建。）

local bridge_io = require "tpf2_mcp/collectors/bridge_io"

local layer_road = require "tpf2_mcp/collectors/layer_road"
local layer_industry = require "tpf2_mcp/collectors/layer_industry"
local layer_vehicles = require "tpf2_mcp/collectors/layer_vehicles"

local M = {}

-- every : 每多少个 update 采一次（首次采集算第 1 次）
-- delay : 启动后先跳过多少个 update 再开始。两个作用：
--         ① 等存档世界加载完（太早采会拿到空数据）
--         ② 让各层首次采集错峰，避免同一帧里连采几层把帧率压下去
-- kind  : static = 内容基本不变（修路才会变）；dynamic = 持续变化
local LAYERS = {
    { name = "vehicles", kind = "dynamic", every = 15,   delay = 45,  collect = layer_vehicles.collect },
    { name = "road",     kind = "static",  every = 4500, delay = 75,  collect = layer_road.collect },
    { name = "industry", kind = "static",  every = 5400, delay = 120, collect = layer_industry.collect },
}

local counters = {}
local status = {}
local enabled = true

local function publish(layer, update_count)
    local collect_ok, payload = pcall(layer.collect)
    if not collect_ok then
        payload = { status = "ERROR", error = tostring(payload) }
    end
    if type(payload) ~= "table" then
        payload = { status = "ERROR", error = "collector returned " .. type(payload) }
    end

    payload.layer = layer.name
    payload.kind = layer.kind
    payload.schema_version = 1
    payload.sampled_at_update = update_count

    local written, write_error = bridge_io.write_json(bridge_io.layer_file(layer.name), payload)
    status[layer.name] = {
        ok = written and true or false,
        at_update = update_count,
        count = (type(payload.counts) == "table" and payload.counts.total) or nil,
        status = payload.status,
        error = written and payload.error or write_error,
    }
    return written and true or false
end

-- 每 tick 调用一次（由 runtime.lua 传入全局 update_count）
function M.tick(update_count)
    if not enabled then return end
    if type(update_count) ~= "number" then return end
    for index = 1, #LAYERS do
        local layer = LAYERS[index]
        local counter = (counters[layer.name] or 0) + 1
        counters[layer.name] = counter
        local since_delay = counter - layer.delay
        -- since_delay == 1 是首次；之后每 every 一次
        if since_delay > 0 and (since_delay - 1) % layer.every == 0 then
            publish(layer, update_count)
        end
    end
end

-- 手动触发（调试用；由 runtime 的显式命令调用，不参与自驱节奏）
function M.force(layer_name, update_count)
    for index = 1, #LAYERS do
        local layer = LAYERS[index]
        if layer.name == layer_name then
            return publish(layer, update_count or 0)
        end
    end
    return false
end

function M.status()
    return status
end

function M.set_enabled(value)
    if type(value) == "boolean" then enabled = value end
    return enabled
end

function M.layer_names()
    local names = {}
    for index = 1, #LAYERS do names[#names + 1] = LAYERS[index].name end
    return names
end

return M
