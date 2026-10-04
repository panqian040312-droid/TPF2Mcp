# 取长补短方案：原架构 × 四层架构 的融合设计

> 生成：2026-10-03 ｜ 状态：**待拍板**
> 配套：`docs/REFACTOR_PLAN.md`（怎么搬、搬去哪、分几期）—— 本文只回答**融合后长什么样**。
> 体检依据：`_audit/dup_scan.json`、`docs/DATA_INVENTORY.md`、`docs/CODE_WIKI_INDEX.md`、`AGENTS.md`

---

## 一句话结论

**两者不是对错之争，是切法不同。**
原架构按「交付物」切（每个目录是一个能单独加载/交付的东西），四层按「职责」切。
⇒ 融合 = **承认「交付物边界」是物理约束，在这个约束内部按职责重切**；同时**把原架构已经写好的执行层骨架直接继承，不重写**。

---

## 一、融合原则（三条）

| # | 原则 | 含义 |
|---|---|---|
| 1 | **职责定层，交付物定路径** | 一个文件属于哪层，看它**干什么**；它**放在哪**，看它**被谁加载**。两者解耦，用 `ARCHITECTURE.md` 的契约路径表钉死 |
| 2 | **层间只走文件，不走 import** | 四层之间靠 `bridge/*.json` 和 `approved_actions.json` 说话。「跨层调用一律禁止」以此为落地形式 |
| 3 | **能继承的不新建** | 原架构里 `operations/`（执行骨架）、`journal/work_log`（审计）、`analytics/planning/tasks`（分析雏形）、`protocol/`（契约）**已经写好**，只搬不改 |

---

## 二、融合后的架构

```
                        ┌─────────────────────────────┐
   游戏引擎 ──▶ Lua mod ─┤ 0_core_shared（契约层）      │
                        │  框架/协议/schema/字段索引/   │
                        │  构建与校验工具/契约路径表     │
                        └─────────────┬───────────────┘
                                      │ 被所有层 import（允许，它是契约）
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐  写JSON  ┌──────────────────┐  出方案  ┌──────────────────┐
│ 1 采集         │ ───────▶│ 2 分析            │ ───────▶│ 3 表现            │
│ 只读导出       │         │ 纯计算            │         │ 渲染 + 收指令      │
│               │         │                  │         │                  │
│ Lua collectors│         │ analytics/       │         │ ui/rail-map/     │
│ export-*.py   │         │ planning/        │         │ serve-rail-map   │
│ bridge 读桥    │         │ tasks/           │         │                  │
└───────┬───────┘         └──────────────────┘         └────────┬─────────┘
        │                                                        │
        │                                       用户点「批准」─────┘
        │                                                        ▼
        │                                          approved_actions.json
        │                                                        │
        │                                                        ▼
        │                              ┌──────────────────────────────────┐
        └──── 只读 MCP 工具 ◀──────────│ 4 执行                            │
                                      │ ① validator.py 先查状态           │
                                      │ ② 执行（写 MCP 工具 → command.json）│
                                      │ ③ 失败 → 回滚（复用 diff.py）      │
                                      │ ④ 成功 → audit_log.json（复用      │
                                      │         journal.py / work_log.py）│
                                      └──────────────────────────────────┘
```

**MCP 工具层被四层吸收**（不再是第 5 个无家可归的层）：**按它服务哪一层归属**——

| 工具类别 | 归属 | 例子 |
|---|---|---|
| 只读查询 | **1 层** | `get_lines` / `get_stations` / `get_vehicles` / `get_game_state` / `get_world_snapshot` / `get_industries` / `get_towns` |
| 分析诊断 | **2 层** | `analyze_network` / `detect_network_problems` / `find_deadlock_risks` 一类 / `rank_*` / `simulate_*` / `plan_new_line_candidates` |
| 写操作与任务 | **4 层** | `propose_operation` / `validate_operation` / `create_task` / `approve_task_step` / `continue_task` / `create_rollback_operation` |
| 能力说明 | **0 层** | `get_agent_operations_guide` / `get_operation_capabilities` / `get_task_capabilities` |

> 关键：**这三组工具注册在同一个 `server.py` 里**（发布契约要求），但**代码分居三层**，互不 import。

---

## 三、6 条冲突的判决

| # | 冲突 | 判决 |
|---|---|---|
| 1 | 分层依据不同（技术栈 vs 职责） | **以职责为准重切**；但外围承认交付物边界，用契约路径表接住 |
| 2 | Lua 是自包含发布单元，不只是采集层 | **在 `res/scripts/tpf2_mcp/` 内部分层**（Lua 侧只有 0 / 1 / 4 三层，没有 2/3）。**引擎侧寸步不让** |
| 3 | `tools/` 的构建工具在四层里没位置 | 归 **0 层 `build/`** —— 构建与校验是「契约的自我维护」，不属于任何业务层 |
| 4 | MCP 工具层没位置 | **按服务对象拆进四层**（见上表）。工具层不是第五层，是各层的对外接口 |
| 5 | 字段"不能随意发明" | **不是冲突**。现有机制已覆盖引擎接口层，只需**补字段级**（`schema/fields.json`）。规则：新字段要么复用已有路径，要么登记说明为什么复用不了 |
| 6 | 发布契约 vs 目录自由 | **源码分层 + 构建打平**：`build-workshop-package.ps1` 从四层重新组装成工坊包需要的平铺形状 |

---

## 四、层间契约（四层怎么说话）

| 从 → 到 | 传什么 | 形式 | 冻结？ |
|---|---|---|---|
| 1 → 2 | 世界快照 | `bridge/layer-*.json`、`bridge/*-probe.json` | 图层产物**冻结**；探针产物**可增但须登记** |
| 2 → 3 | 候选方案 | `bridge/plan-*.json`（新增，复用已有字段优先） | 进 `schema/` |
| 3 → 4 | 用户批准的动作 | `approved_actions.json` | **冻结**，四层里唯一的"通行证" |
| 4 → 游戏 | 写命令 | `bridge/command.json`（**只能由 MCP 工具写**） | 已有（`protocol/`） |
| 4 → 全部 | 执行流水 | `audit_log.json`（复用 `journal.py`） | **冻结** |
| 任意 → 0 | 路径 / schema / 字段索引 | `ARCHITECTURE.md` + `schema/*.json` | 冻结 |

**四条硬规则**（写进 `ARCHITECTURE.md`）：

1. **1 层不许向上要数据** —— 它只能读引擎。
2. **2 层不许写游戏** —— 它只能出方案文件。
3. **4 层不许自己拿主意** —— 没有 `approved_actions.json` 里的条目，一律不执行。
4. **跨层只走文件** —— 任何 `import` 都必须是 0 层，或同层内部。

---

## 五、保留 / 改造 / 新建

### 5.1 直接继承（原架构的资产，搬而不改）

| 资产 | 去哪层 | 为什么值得留 |
|---|---|---|
| `operations/`：`controller.py` + `capabilities.py` + `diff.py` + `handlers/`（7 个）+ `models.py` | **4 层核心** | **这已经是一个标准的执行控制层骨架**：控制器、前置能力检查、前后差异（＝回滚依据）、操作处理器、数据模型，五件齐备 |
| `journal.py` + `work_log.py` | 4 层 | `audit_log.json` 的现成实现，不用新写 |
| `analytics/` + `planning/` + `tasks/` | 2 层 | 分析/决策/编排雏形已成型 |
| `protocol/` + `bridge.py` + `config.py` | 0 层 | 跨语言契约现成 |
| `snapshot.py` + `save_scope.py` | 1 层 | 快照索引与存档作用域现成 |
| Lua `collectors/` 9 个图层采集器 | 1 层 | 已实测跑通（8 个图层产物都在） |
| Lua `bridge_io.lua` / `common.lua` / `component_access.lua` / `layer_registry.lua` | 0 层 | 写盘出口、读字段三条路的工具、调度器 |
| `ui/rail-map/` 全套 | 3 层 | 图层与交互已生效 |
| **`DATA_INVENTORY.md` + `interface-baseline.json` 机制** | 0 层 | 「先查再写」的强制闸门已经有了，**扩到字段级即可** |
| `code-wiki-map.json` + 生成器 | 0 层 | 代码↔文档索引机制现成（179 文件 / 1098 函数） |

### 5.2 改造（保留功能，换位置 / 合并重复）

| 对象 | 动作 |
|---|---|
| Lua `operations/`（dispatcher / line_stop_builder / timetable_controller） | 搬进 `4_execution_control/` 子目录（仍在 `res/` 内） |
| `mcp_server/server.py` | 工具注册按层分组，`server.py` 留作启动壳 |
| `tools/` 43 个脚本 | 按层拆（详见 `REFACTOR_PLAN.md` §2.2） |
| 4 个 `export-*-map.py` | 合并成 1 个带 `--layer` 参数 |
| 9 个 `test-*-live.py` | 合并成 1 个带 `--case` 参数（现在相似度 0.42–0.53，同一模板抄了 9 遍） |
| 5 个前端图层壳（`buildPanel` ×5） | 抽 `3_dashboard_ui/shared/layer-shell.js` |
| `app.js` ↔ `network-app.js` 的 5 个画图函数 | 抽 `3_dashboard_ui/shared/geo.js` |
| `_percentile` ×2 / `validate_parameters` ×2 / `_connect` ×3 | 提进 0 层共享 |
| Lua `vec` ×11 / `bounds_for` ×4 / 高程采样 ×3 | 提进 0 层 `common.lua` |

### 5.3 新建（只有这五样）

| 新建物 | 层 | 作用 |
|---|---|---|
| `ARCHITECTURE.md` | 0 | 层间规则 + **契约路径表**（引擎加载路径、发布包结构、注册点） |
| `schema/fields.json` | 0 | 产物字段索引 —— 把「先查再写」从接口级盖到字段级 |
| `approved_actions.json` 闸门 | 3→4 | 用户批准变成代码可检查的门（**补上原架构唯一缺的物理卡点**） |
| `validator.py` | 4 | 执行前的固定入口（内部调 `capabilities.py`，不重写） |
| `schema/{layer,probe,actions,audit}.schema.json` | 0 | 四个冻结契约 |

> ⚠️ **不新建**：执行器（有 `controller.py`）、回滚机制（有 `diff.py`）、审计（有 `journal.py`）、
> 分析框架（有 `analytics/planning/tasks`）。这四样再生造一遍就是重蹈"造新轮子"的覆辙。

---

## 六、1 层「禁止计算」的精确边界

原话是「只负责读取和导出，绝对不准做逻辑计算」。若按字面执行会误伤——**有些"整理"不做就导不出来**，因为 Python 拿不到引擎对象。所以边界要划在三者之间：

| Lua 里在做什么 | 例子 | 判 |
|---|---|---|
| **业务判据**：什么算堵、什么算缺货、什么算该加车 | 目前 0 处（判据基本都在 Python 侧，好现象） | 🔴 **禁止** |
| **为导出而做的机械整理**：把引擎对象摊平成可序列化结构 | `layer_freight` 两万条货聚合成边、`layer_stations` 并查集求连通分量、`layer_terrain` 逐帧采样 | 🟡 **允许**，但整理规则必须登记进 `ARCHITECTURE.md`，**且不得引入阈值/权重/判断** |
| **纯搬运**：读字段 → 写 JSON | 各 `layer_*.lua` 的主体 | 🟢 本职 |

一句话判据：**「这段代码里有没有出现一个数字，它的取值需要人来拍板？」** 有 → 越界。

---

## 七、这份方案与原架构相比，到底赢在哪

| 维度 | 原架构 | 融合后 |
|---|---|---|
| 找"采集逻辑" | 要去 `tpf2_mod/` + `tools/` 两处翻 | 只在 `1_data_collection/` |
| 找"执行逻辑" | 要去 `mcp_server/operations/` + `tools/operate-*` 两处翻 | 只在 `4_execution_control/` |
| 加一个新功能 | 不知道该放哪，往往新开一个脚本 | 按层归位，位置唯一 |
| 执行前的检查 | 靠纪律（记忆里的 L0–L3），没有代码门 | `validator.py` + `approved_actions.json` 双门 |
| 执行后追溯 | 有日志，但不强制走 | `audit_log.json` 强制 |
| 新增字段 | 随口就加 | 先查 `fields.json`，复用不了要登记 |
| 发布包 | — | 不变（构建脚本打平），玩家无感 |

---

## 八、下一步

本文 + `docs/REFACTOR_PLAN.md` 的 §7（7 个待拍板点）一起看。
**拍板后第一件事不是搬目录**，而是 P1（零风险归档）＋ 写 `0_core_shared/ARCHITECTURE.md` ——
因为按你定的规矩，**写任何新代码前必须先有它**。
