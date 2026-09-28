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

-- 触发条件：counter > delay 且 (counter - delay - 1) % every == 0
--   → vehicles 落在 counter ≡ 1 (mod 15)，即 46 / 61 / 76 / 91 / …
--
-- every : 每多少个 update 采一次（首次采集算第 1 次）
-- delay : 启动后先跳过多少个 update 再开始。两个作用：
--         ① 等存档世界加载完（太早采会拿到空数据）
--         ② 让各层首次采集错峰
-- kind  : static = 内容基本不变（修路才会变）；dynamic = 持续变化
--
-- ⚠️ 相位是刻意错开的，不要随手改数字：road 与 industry 的 delay 之所以各加 1
--   （75→76、120→121），是因为原值会让首次采集正好落在 vehicles 的 76 / 121 上
--   —— 同一帧里采两层会叠加卡顿（公路一次要遍历 5262 条边 + 9793 个节点）。
--   tick() 里还有一道"同一帧最多采一层"的兜底。
local LAYERS = {
    { name = "vehicles", kind = "dynamic", every = 15,   delay = 45,  collect = layer_vehicles.collect },
    { name = "road",     kind = "static",  every = 4500, delay = 76,  collect = layer_road.collect },
    { name = "industry", kind = "static",  every = 5400, delay = 121, collect = layer_industry.collect },
}

local counters = {}
local status = {}
local enabled = true
local last_publish_update = nil

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
        if since_delay > 0 and (since_delay - 1) % layer.every == 0 then
            if last_publish_update == update_count then
                -- 同一帧已经采过一层了：把计数退回去，下一帧再判（相位不变，
                -- 因为下一帧 counter 会回到同一个值再次满足条件）
                counters[layer.name] = counter - 1
            else
                last_publish_update = update_count
                publish(layer, update_count)
            end
        end
    end
end

-- 手动触发（供将来加显式命令用；不参与自驱节奏）
function M.force(layer_name, update_count)
    for index = 1, #LAYERS do
        local layer = LAYERS[index]
        if layer.name == layer_name then
            return publish(layer, update_count or 0)
        end
    end
    return false
end

-- 各层最近一次采集结果。由 runtime.lua 的 heartbeat() 带出去，
-- 这样心跳文件里就能看到图层状态，不用额外开命令通道。
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
