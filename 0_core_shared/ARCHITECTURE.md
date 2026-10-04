# 架构规约（TPF2Mcp）

> **这份文件是施工图纸，不是说明书。**
> 🔴 **硬规矩**：写任何新代码之前，先在这里找到它属于哪一层；归属说不清 → 先改这份文件，再写代码。
> 配套：`docs/ARCHITECTURE_MERGE.md`（为什么要这么分）｜`docs/REFACTOR_PLAN.md`（搬迁进度）

---

## 一、四层定义

| 层 | 干什么 | 允许 | 🔴 禁止 | 物理落点 |
|---|---|---|---|---|
| **0 共享契约** | 框架、协议、schema、路径表、构建与校验工具 | 被所有层 import | 放业务逻辑 | `0_core_shared/` ＋ `tpf2_mod/res/scripts/tpf2_mcp/0_core_shared/` |
| **1 采集** | **只读 + 导出**。把引擎里的东西变成外面能读的文本 | 读引擎、机械整理、写 JSON | **业务判据**（什么算堵/缺货/该加车） | `1_data_collection/` ＋ `res/scripts/tpf2_mcp/1_data_collection/` |
| **2 分析** | 纯计算。读 JSON → 出方案 | 数学、统计、图算法、判据 | 写游戏、碰引擎 | `2_brain_analysis/` |
| **3 表现** | 渲染 + 收指令 | 画图、交互、查表 | **核心计算** | `3_dashboard_ui/` |
| **4 执行** | 唯一写通道 | 改游戏状态（须先过闸门） | 自己拿主意 | `4_execution_control/` ＋ `res/scripts/tpf2_mcp/4_execution_control/` |

### 归属判定口诀：读 → 算 → 看 → 动

| 这个动作的输入是 | 归哪层 |
|---|---|
| **引擎对象**（组件、实体、`getHeight`） | **1** |
| **JSON 里的数字，且要判断"好不好 / 该不该"** | **2** |
| **用户的手**（点击、拖动、勾选） | **3** |
| **输出要改游戏状态** | **4** |

> 一个功能穿过 2–4 层是**正常的**。四层切的是**阶段**，不是**功能模块**。
> 只"看"的功能最多到 3；能"动"的功能才穿到 4。

---

## 二、🔴 契约路径表（这几处被外部钉死，动之前先看这一节）

| 路径 | 谁依赖它 | 能不能动 |
|---|---|---|
| `tpf2_mod/res/config/game_script/tpf2_mcp.lua` | **引擎**启动时扫描 | ❌ **不能动**。只改里面的 `require` |
| `tpf2_mod/res/scripts/tpf2_mcp/**` | 引擎 `require` | ⚠️ 可加子目录（四层就在这下面分），**路径改一处、require 同步改** |
| `mcp_server/start_server.py` | `~/.workbuddy/mcp.json`（MCP 注册点） | ❌ **不能动**（可改内部 `sys.path`） |
| `mcp_server/start_ui.py` | `rail-map-service.pyw` 的 `SERVICE_ENTRY` | ❌ **不能动** |
| **发布包里的** `tools/serve-rail-map.py` | `start_ui.py:13` 的 `UI_SERVER` | ❌ **包内位置不能动**（源码里它是 `3_dashboard_ui/server/serve-rail-map.py`） |
| **发布包里的** `tools/export-layer-map.py` | `deploy_mod_layers.bat` 的逐文件清单 | ❌ 包内位置固定（源码里它是 `1_data_collection/exporters/export-layer-map.py`） |
| `ui/rail-map/` | `rail-map-service.pyw` 的 `UI_DIRECTORY` | ⚠️ 能移，但要同步改 `.pyw`（**P4 待办**） |
| 工坊包结构（`mod.lua` + `res/` + `mcp_server/` + 精选 `tools/` + `ui/rail-map/` 平铺） | `0_core_shared/build/build-workshop-package.ps1` 白名单 | ❌ **结构不能变**（玩家装的就是它） |
| `bridge/` | mod（写）↔ Python（读） | ❌ 运行时目录，位置固定 |
| `docs/code-wiki-map.json` | 索引生成器 | ⚠️ 任何搬迁都要同步改路径键 |

> 🔴 **读懂这张表的关键：区分「源码位置」和「发布包位置」。**
> 源码分成四层后，发布包**打平**成玩家要的平铺形状 —— 所以同一个文件在源码里叫
> `3_dashboard_ui/server/serve-rail-map.py`，在包里叫 `tools/serve-rail-map.py`。
> `start_ui.py` / `deploy_mod_layers.bat` 指的是**包里那一份**，所以它们**不用改**。
> 改这三个文件要改**四层里的源**，然后重新打包。

**原则**：`tpf2_mod/` `mcp_server/` `ui/rail-map/` 这三个是**发布/加载契约路径**，四层是**源码组织**。
源码分层、构建打平 —— 由 `build-workshop-package.ps1` 负责把四层组装回平铺形状。

---

## 三、层间契约（只走文件，不走 import）

| 从 → 到 | 文件 | 冻结？ |
|---|---|---|
| 1 → 2 | `bridge/layer-*.json`（**10 个图层**）、`bridge/state.json` | **冻结** |
| 1 → 2 | `bridge/*-probe.json`（探针产物） | 可增，**必须登记新字段** |
| 2 → 3 | `bridge/plan-*.json` | 新建，进 schema |
| 3 → 4 | `bridge/approved_actions.json` | **冻结**（四层里唯一的通行证） |
| 4 → 游戏 | `bridge/command.json` | 已有（`protocol/`），**只能由 MCP 工具写** |
| 4 → 全部 | `bridge/audit_log.json` | **冻结** |
| 任意 → 0 | `0_core_shared/schema/*.json`、本文件 | **冻结** |

### 四条硬规则

1. **1 层不许向上要数据** —— 它只读引擎。
2. **2 层不许写游戏** —— 它只出方案文件。
3. **4 层不许自己拿主意** —— 没有 `approved_actions.json` 里的条目，一律不执行。
4. **跨层只走文件** —— 任何 `import` 只能是 0 层或同层内部。

---

## 四、🔴 1 层「禁止计算」的精确边界

按字面执行会误伤。判据一句话：

> **这段代码里有没有出现一个数字，它的取值需要人来拍板？** 有 → 越界。

| Lua 里在做什么 | 例 | 判 |
|---|---|---|
| **业务判据**（阈值、权重、"该不该"） | 速度分档 0.5 / 15 / 45 km/h ⚠️ 待搬 | 🔴 **禁止** |
| **为导出而做的机械整理** | 两万条货聚合成边、并查集求连通分量、槽位反解成坐标 | 🟡 **允许**，规则登记在本文件，**不得引入阈值/权重** |
| **纯搬运**（读字段 → 写 JSON） | 各 `layer_*.lua` 主体 | 🟢 本职 |

### Lua 里的三条边界（决定什么必须留在 Lua）

| 边界 | 内容 | 判 |
|---|---|---|
| **① 引擎边界** | 读组件/实体、调 `game.interface.getHeight`、遍历引擎实体 | 🔴 **必须留**——Python 够不着 |
| **② 沙箱边界** | `json.encode`、`bridge_io.write_json`（Lua 沙箱没有 io） | 🔴 **必须留**——环境强制 |
| **③ 性能边界** | 9500 路段 × 10658 车的空间匹配、6.8 万点地形采样 | 🟡 **建议留**——搬出去传输比算还贵 |

> ⚠️ **"地图底层"不是判据**。反例：`json.lua` / `bridge_io.lua` / `carrier_name` / `timetable_controller`
> 四个都跟地图无关，但都必须留 Lua。
> 同样，`layer_terrain.lua` 的网格切分（算 `cols`/`rows`/`step`）长得像地图底层，却**是纯算术、可搬**。
> ⇒ **同一个文件要按行切，不能按文件判。**

### 该留在 Lua 的运算清单（已逐条核对）

**必须留**：`vec` / `bounds_center` / `bounds_for`（取坐标）、`get_height_function` / `sample_height`（引擎函数）、
`entity_id` / `first_id`（userdata → 数字）、`structure_of` / `carrier_name` / `street_type_of`（枚举翻译）、
所有 `safe_for_each_entity`、`json.encode`、`bridge_io.write_json`

**建议留（边遍历引擎对象边算，或数据量大）**：`point_segment_distance` + 空间网格 + `nearest`、
地形网格生成、`activity_bounds`、路段聚合累加、**`bump` / `flatten`（账本聚合）**

**🔴 应搬去 2 层**（输入是**已收集好的数字表**，纯统计）：速度分档阈值、`percentile`、`majority_key`、
`make_union_find`、`tally` / `tally_numeric` / `count_up`、排序、`normalized_offsets` / `minimum_headway`

> 🔴 **这两类的分界判据**：看**输入是什么**。
> 输入是**引擎实体流**（边遍历 `SIM_CARGO` 边累加、边遍历账本边聚合）⇒ **必须留 Lua**——
> 重新取值要再过一遍引擎，Python 拿不到那些对象。
> 输入是**已经收好的数字表**（一组速度值求分位、一组计数求众数）⇒ **可以搬**。
> ⚠️ 2026-10-03 校验 `economy_probe.lua` 时发现：`bump` / `flatten` 原先被我错列进"应搬"，
> 实际它们是前者，**已更正**。

**例外**：`operations/timetable_controller.lua` 的实时调度算法属于 **4 层**，**不受本条约束**——
它每帧跑、算完立刻发车，必须留 Lua。

---

## 五、数据字段纪律（复用优先）

> **新字段要么复用已有路径，要么登记说明为什么复用不了。**

| 层 | 现在管不管 | 机制 |
|---|---|---|
| **引擎接口**（Lua 调了哪些 system 方法） | ✅ 已管 | `docs/interface-baseline.json`（**61 个批准，代码里用 59 个**）＋ `build-data-inventory.py --check` |
| **产物字段**（JSON 里出现哪些路径） | ✅ 已管 | `0_core_shared/schema/fields.json`（从 `bridge/*.json` 自动抽，**23,405 个字段**）＋ `build-fields-index.py --check` |

**写新采集器之前**：先查 `docs/DATA_INVENTORY.md` 第零节「我想要 → 现成接口」→ 再查 `fields.json`。
确需新增 → 补进生成脚本的 `WISH_LIST` → `--update-baseline`（进 git diff = 留痕）。

---

## 六、搬迁进度

| 期 | 内容 | 状态 |
|---|---|---|
| **P1** | 归档零散产物与旧脚本（24 产物 + 2 旧 bat） | ✅ 2026-10-03 |
| **P2** | 建骨架 + 本文件 + `schema/fields.json` | ✅ 2026-10-03 |
| **P3** | **`tools/` 51 个文件按层归位** ＋ 改引用点 ＋ 索引重映射 ＋ 补工坊白名单 | ✅ 2026-10-03 |
| **P4** | `ui/rail-map/` 迁入 3 层 ＋ Lua 分层 ＋ 前端去重 | ⏳ 待开工（需重启游戏） |
| **P5** | 执行层硬化（`validator.py` + `approved_actions.json` 闸门 + 回滚 + `audit_log.json`） | ⏳ 待开工 |

### P3 实际做了什么（2026-10-03）

| 动作 | 结果 |
|---|---|
| `tools/` → 四层 | **51 个文件**：0 层 13 ／ 1 层 10 ／ 2 层 6 ／ 3 层 1 ／ 4 层 21；`tools/` 目录已空 |
| 改引用点 | `deploy_mod_layers.bat`（2 条，**staging 目标路径不变，只改源**）、`collect_demand.bat`、`build-workshop-package.ps1`（tools 源路径改成显式对表） |
| 工坊白名单 | 补 **9 个前端文件** ＋ `cargo-types.json` / `industry-recipes.json` / `station-module-catalog.json` / `line-cost-profile.json` ＋ `icons/` `assets/` 目录 —— 原白名单只有 15 个 js，**打出来的包会缺图层** |
| 索引 | `code-wiki-map.json` 的 **51 个 `tools/` 键自动重映射**（0 未匹配 / 0 歧义，总键数仍 179 → +1 = 180） |
| 生成器 | `build-code-wiki-index.py` / `build-data-inventory.py`：`ROOT` 由 `parent.parent` 改为**向上找 `.git`**（搬目录后原写法会**静默**算错根目录）；`SCOPE` 由 `tools` 换成四层 |
| 校验 | ✅ 180 文件 / 1102 函数全部登记 ｜ ✅ 56 接口无越界 |

**P3 之后的增量**（2026-10-04）：新增 `collectors/layer_passenger.lua`（R30 客流）与重写
`collectors/terminal_waiting_probe.lua`（R26 站台容量探针）⇒ 索引涨到 **182 文件 / 1125 函数**；
探针新用到的 `stationSystem.getStationTerminalsForPersonEdge` 等接口走 `WISH_LIST` → `--update-baseline`
留痕，基线 **59 → 61 条**（其中 2 条已不再调用，可清理）。

🔴 **方案修正**：原计划要把 `mcp_server/src/tpf2_mcp/` 的内部包也搬进四层 —— **实测后取消**。
理由：① 它是**契约路径**（MCP 注册点 + 工坊包结构）；② 它**内部本来就已经分层**
（`analytics/planning/tasks` = 2 层、`operations/` = 4 层、`bridge/snapshot` = 1 层），且依赖单向无环。
搬它 = 为目录好看而破坏发布链路。

⚠️ **还没做**：`ui/rail-map/` 仍在原位（属 P4）—— `rail-map-service.pyw` 的 `UI_DIRECTORY` 指着它。

**P3 开工前必须同步改的引用点**（漏一个就断链）：
`deploy_mod_layers.bat`｜`rail-map-service.pyw`｜`mcp_server/start_ui.py`｜`mcp_server/start_server.py`｜
`~/.workbuddy/mcp.json`｜`build-workshop-package.ps1`｜`docs/code-wiki-map.json`（179 个路径键）｜
`build-code-wiki-index.py` 与 `build-data-inventory.py` 的 `SCOPE`｜`AGENTS.md`｜
`res/config/game_script/tpf2_mcp.lua`｜`ui/rail-map/index.html`｜`collect_demand.bat` + `start_rail_map.bat`

---

## 变更记录

| 日期 | 改了什么 |
|---|---|
| 2026-10-03 | 建立本文件。四层定义、契约路径表、层间契约、1 层边界、字段纪律 |
| 2026-10-04 | 契约路径表补「源码位置 vs 发布包位置」的区分（`tools/xxx.py` 在包里、在源码里是 `3_dashboard_ui/` `1_data_collection/`）；§五 两套索引都改成「已管」并补实测数字；§六 补 P3 之后的增量 |
