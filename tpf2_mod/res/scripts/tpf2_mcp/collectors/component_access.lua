-- 组件读取工具（只读）
--
-- 两条实机教训换来的：
--
-- ① 组件类型解析带缓存。`api.type.ComponentType[name]` 每次查都有开销，
--    大批量遍历（公路 5262 条边 + 9793 个节点）时缓存能省一截。
--
-- ② 不污染调用方的 errors 数组。`common.safe_get_component(entity, name, errors)`
--    会**无条件**往 errors 里追加一条；对几千个实体的遍历，一旦某个组件普遍
--    取不到（2026-09-28 就真出过：全部实体读字段失败），errors 会涨到几千条，
--    跟着 payload 一起写进 bridge 文件，把产物撑成垃圾。
--    这里改成直接 pcall：读不到就是 nil。规模由调用方的计数器（skipped /
--    no_bounds）报告，只对"整体性失败"留一条样例错误。

local common = require "tpf2_mcp/collectors/common"

local M = {}

local type_cache = {}

-- 解析组件类型（带缓存）。解析不到返回 nil。
function M.type(name)
    local cached = type_cache[name]
    if cached == nil then
        cached = common.component_type(name) or false
        type_cache[name] = cached
    end
    if cached == false then return nil end
    return cached
end

-- 读组件。读不到返回 nil，不抛错、不写任何错误数组。
function M.get(entity, name)
    local resolved = M.type(name)
    if resolved == nil then return nil end
    local ok, value = pcall(api.engine.getComponent, entity, resolved)
    if not ok then return nil end
    return value
end

return M
