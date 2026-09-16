# TPF2 MCP 技术参考

本文面向开发、测试和发布维护者。面向普通使用者的项目介绍与启动入口见仓库根目录
[README](../README.md)。

## 架构

```text
MCP client <-> Python stdio MCP server <-> Bridge Protocol <-> TPF2 Lua Mod <-> TPF2 API
```

MCP Tool 不直接访问 Bridge 文件；`BridgeClient` 是 Python 侧唯一的 Bridge 边界。
Lua Mod 通过游戏脚本的 `load` 与周期性 `update` 回调采集并响应协议请求。

源码职责如下：

- `tpf2_mod/`：Lua Mod 与发布图片。
- `mcp_server/`：Python MCP Server、受控操作和数据处理。
- `ui/rail-map/`：铁路图前端。
- `tools/`：开发、安装、验证、导出和打包脚本。
- `protocol/`、`tests/`、`docs/`：协议、测试与文档。

## 开发环境

开发依赖必须位于仓库根目录的 `.venv/`，不要使用 `pip install --user` 或未激活环境
下的全局安装。当前 Python 运行时没有第三方依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .\mcp_server
python -m unittest discover -s tests -v
```

本机开发安装使用 `tools/install-mod.ps1`。该脚本用于已确认的游戏 Mod 根目录测试，
不是 Workshop 发布构建方式。运行真实游戏前，需要在游戏内启用 Mod 并重新进入存档，
再验证 Bridge ping 和游戏状态读取。

## 运行与安全模型

发布配置 `allow_write_operations = false`。MCP 的直接 `execute_operation` 不会向 Agent
暴露，且直接调用会被拒绝。

所有写入都必须遵循：

```text
get_operation_capabilities
-> propose_operation
-> validate_operation
-> create_task
-> plan_task
-> approve_task_step
-> continue_task
-> get_task
```

每次 `continue_task` 最多执行一个变更，并刷新游戏快照验证后置条件。受控能力与
Agent 工具入口见 [agent-mcp-tools.md](agent-mcp-tools.md)。

已验证的受控操作包括创建线路、设置停站、购买并分配车辆、设置停站策略和确认后
出售车辆。`REMOVE_VEHICLE_FROM_LINE` 仍不可用；未被引擎实际验证的能力应明确标记
为 `UNKNOWN`。

## 发布与 Workshop 测试

创意工坊发布文件夹由源码白名单组装，默认目录名为 `tpf2mcp_1`：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build-workshop-package.ps1
```

构建目标已存在时，脚本会停止而不是覆盖。发布前应完成自动化测试、构建脚本校验、
最终暂存目录层级检查，并从最终 Mod 根目录分别启动 MCP Server 与 UI 验证。

发布包根目录直接包含 Mod 文件、`mcp_server/`、精选 `tools/` 和 `ui/rail-map/`。
Bridge 数据、SQLite、日志、诊断、缓存、存档导出和本机配置均不得进入 Git 或发布包。
发布包不会自动启动 Python；最终用户应在 Mod 根目录的 `mcp_server/` 中执行：

```powershell
python start_server.py
python start_ui.py
```

然后打开 `http://127.0.0.1:8765/?view=network`。

## 延伸文档

- [架构说明](architecture.md)
- [Bridge 协议](bridge.md)
- [最终验收与能力边界](FINAL_GOAL_ACCEPTANCE.md)
- [网络智能分析](PHASE9_NETWORK_INTELLIGENCE.md)
- [决策支持](PHASE10_DECISION_SUPPORT.md)
- [受控操作](PHASE11_CONTROLLED_OPERATIONS.md)
- [任务编排](PHASE12_CLOSED_LOOP_TASKS.md)
- [线路管理](PHASE14_LINE_MANAGEMENT.md)
- [Agent MCP 工具](agent-mcp-tools.md)
