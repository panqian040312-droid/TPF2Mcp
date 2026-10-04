# 4 执行控制层（execution control）

**干什么**：唯一的写通道。所有改游戏状态的动作都在这里。

| 必须 | 🔴 禁止 |
|---|---|
| 执行前先跑 `validator.py` 检查状态 | **没有 `approved_actions.json` 的条目就执行** |
| 失败必须回滚 | 自己拿主意（"我觉得这条线该加车"） |
| 执行后记 `audit_log.json` | 绕过闸门直接发命令 |

**四步流程**：`validator.py` → 执行（写 MCP 工具 → `command.json`）→ 失败回滚（复用 `diff.py`）→ 记 `audit_log.json`。

## 现状（尚未搬迁）

| 实际位置 | 内容 |
|---|---|
| `mcp_server/src/tpf2_mcp/operations/` | **整套执行骨架**：`controller.py` + `capabilities.py`（前置检查）+ `diff.py`（回滚依据）+ `handlers/`×7 + `models.py` |
| `mcp_server/src/tpf2_mcp/journal.py`、`work_log.py` | **`audit_log.json` 的现成实现** |
| `tools/operate-*.py`、`apply-*.py`、`replace-line-fleet.py` | 操作脚本 |
| `tools/test-*-live.py`（9 个）、`watch-operations-until.py` | 验收脚本 |
| `tpf2_mod/res/scripts/tpf2_mcp/operations/` | Lua 侧：`dispatcher` / `line_stop_builder` / `timetable_controller` |

## 与其他层的不同

**4 层允许有算法**（`timetable_controller` 的实时调度每帧跑、算完立刻发车）——
"1 层禁止计算"这条**不适用于 4 层**。

⚠️ 当前 `allow_write_operations = false`、`tpf2_control.dll` 未装 → 写通道尚未启用。
