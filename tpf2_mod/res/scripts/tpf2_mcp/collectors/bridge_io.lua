-- 公共 bridge 写入模块 —— mod 沙箱内唯一可靠的写盘出口
--
-- 为什么需要它：`runtime.lua` 与 `collectors/demand_probe.lua` 各自带了一份 local
-- 的 `write_json`。多图层再各写一份就会变成第三、第四份，迟早不一致。这里收口。
--
-- 沙箱约束（2026-09-28 实测，不是推测）：
--   * 没有 os.rename / os.remove  → 不能"写临时文件再改名"做原子替换
--   * io.open 不会自动建目录      → 只写 bridge 根目录下的平铺文件名
--   * 所以图层文件统一命名 `layer-<name>.json`，不分子目录
--     （若将来要 bridge/layers/ 子目录，必须由外部 Python 服务预建，mod 侧做不到）

local json = require "tpf2_mcp/json"
local config = require "tpf2_mcp/config"

local M = {}

function M.bridge_dir()
    local dir = config and config.bridge_dir
    if type(dir) ~= "string" or dir == "" then return nil end
    return dir
end

-- 写纯文本。返回 ok, err
function M.write_text(name, text)
    local dir = M.bridge_dir()
    if dir == nil then return false, "bridge dir unavailable" end
    if type(name) ~= "string" or name == "" then return false, "empty file name" end
    if type(text) ~= "string" then return false, "content must be a string" end
    local handle, open_error = io.open(dir .. "/" .. name, "w")
    if handle == nil then return false, tostring(open_error) end
    local ok, write_error = pcall(function() handle:write(text) end)
    if not ok then
        pcall(function() handle:close() end)
        return false, tostring(write_error)
    end
    pcall(function() handle:flush() end)
    pcall(function() handle:close() end)
    return true
end

-- 写 JSON 文件（先编码再落盘，编码失败不会写坏已有文件）。返回 ok, err
function M.write_json(name, object)
    local ok, encoded = pcall(json.encode, object)
    if not ok then return false, "encode failed: " .. tostring(encoded) end
    return M.write_text(name, encoded)
end

-- 图层文件的统一命名：layer-road.json / layer-industry.json / layer-vehicles.json
function M.layer_file(layer_name)
    return "layer-" .. tostring(layer_name) .. ".json"
end

return M
