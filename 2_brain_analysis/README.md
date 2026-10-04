# 2 分析层（brain analysis）

**干什么**：纯计算。读 1 层的 JSON → 出方案。

| 允许 | 🔴 禁止 |
|---|---|
| 数学、统计、图算法 | 碰引擎、调 `game.interface.*` |
| 业务判据（阈值、权重、排序、推荐） | 写 `command.json` / 改游戏状态 |
| 产出 `bridge/plan-*.json` | 自己做决定（决定权在 3 层的用户和 4 层的闸门） |

依赖：`NetworkX`（图）、`PuLP`（线性规划）—— ⚠️ **项目目前无任何第三方依赖**，
引入前需决定是否随工坊包分发（见 `docs/REFACTOR_PLAN.md` §七）。

## 现状（尚未搬迁）

| 实际位置 | 内容 |
|---|---|
| `mcp_server/src/tpf2_mcp/analytics/`、`planning/`、`tasks/` | 分析 / 决策 / 任务编排 |
| `mcp_server/src/tpf2_mcp/graph.py`、`dwell_optimizer.py`、`timetable_planner.py`、`overtake_planner.py`、`fleet_policy.py`、`vehicle_length.py`、`demand_history.py` | 各算法 |
| `tools/diagnose-industries.py`、`find_deadlock_risks.py`、`analyze-line-economics.py` | 诊断脚本 |

## 应从这里搬进来的还有（现在错放在 1 层，见 ARCHITECTURE.md §四）

速度分档阈值、`percentile`、`majority_key`、`make_union_find`、
`bump` / `flatten`（账本聚合）、`tally` / `tally_numeric` / `count_up`、排序。
