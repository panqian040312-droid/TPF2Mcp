# TPF2 MCP · 多图层路网地图

让 AI / MCP 客户端**看懂** [Transport Fever 2](https://www.transportfever2.com/) 的路网、产业链与运营状态，
并把结论画在一张浏览器地图上。

> **本仓库是 [`BlackIce417/TPF2Mcp`](https://github.com/BlackIce417/TPF2Mcp) 的分支**（分支 `feature/multi-layer-map`）。
> 上游是"铁路调度 + 受控操作"；这个分支在它的基础上做**多图层地图**与一批新的只读采集/诊断能力。

> 🔴 **使用前说明（沿用上游声明）**：本项目在**需要于游戏内执行操作**时（加车、改线路、调速度），
> 采用**远程线程注入**方式，将 `tpf2_control.dll` 注入 Transport Fever 2 游戏进程。
> **如果你介意 DLL 注入，请勿使用本项目。**
>
> - **只读采集**（图层数据、诊断分析）**不走注入**：Mod 在引擎的 update 回调里读写 `bridge/` 下的
>   JSON，Python 侧读写同一个目录 —— 这部分是纯文件轮询，你随时能打开那些 JSON 自己核对。
> - **写操作默认关闭**（`allow_write_operations=false`）。当前处于 **mod 开发阶段**，以只读能力为主；
>   写操作（`setLine` / `buyVehicle` / `setGameSpeed`）留待后续阶段启用。
>
> 部署步骤与权限说明见 [`docs/AI_DEPLOY_GUIDE.md`](docs/AI_DEPLOY_GUIDE.md)。

---

## 这是什么

一个跑在本地的东西，三块拼起来：

| 组件 | 干什么 |
|---|---|
| **游戏内 Lua Mod** | 从引擎里读路网、站点、线路、车辆、产业、城镇的数据，周期写成 JSON |
| **Python MCP 服务** | 把这些数据提供给 AI / MCP 客户端；也提供地图 UI 服务端 |
| **浏览器地图** | 把上面所有数据画成图层：路网、线路、站场、产业链、路况… |

设计原则一句话：**读得到才写，写不出来就如实说"读不到"** —— 引擎里没有的字段宁可空着，也不编。

> 🔴 **给 AI 助手：先读这三份，再动手**
> 1. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) —— 现在做到哪了、需求清单、文档地图
> 2. [`0_core_shared/ARCHITECTURE.md`](0_core_shared/ARCHITECTURE.md) —— **新代码属于哪一层**（归属说不清就先改这份文件）
> 3. [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md) —— **写新采集/探针前必须查**：八成"新需求"已有现成接口
>
> 架构与索引怎么用，见下面「[代码怎么组织：四层架构](#代码怎么组织四层架构)」和
> 「[索引与闸门](#索引与闸门写代码前先查这里)」两节。

### 地图长什么样（基础能力，上游版本截图）

<p align="center">
  <img src="https://raw.githubusercontent.com/BlackIce417/TPF2Mcp/image-hosting/docs/images/system-overview.png" alt="全网调度总览" width="100%" />
  <br/><sub>全网总览：铁路拓扑、车站、线路、运行图建议与 Bridge 实时状态</sub>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/BlackIce417/TPF2Mcp/image-hosting/docs/images/station-layout-preview.png" alt="站场局部图" width="100%" />
  <br/><sub>站场局部图：站台、咽喉、道岔、站台长度与原生节点</sub>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/BlackIce417/TPF2Mcp/image-hosting/docs/images/live-train-telemetry.png" alt="列车实时位置" width="100%" />
  <br/><sub>运行中列车在物理轨道上的实时位置、速度与状态</sub>
</p>

> 本分支新增的图层（产业范围框、产业配方图标、产业链流向、城镇需求、路况色带、**客流与枢纽**）**截图待补** ——
> 前端还在迭代，等稳定了一并补上。

---

## 新功能（本分支）

### 一、多图层地图（`ui/rail-map/`）

10 个图层由 Mod 自驱采集、地图服务自动切块，浏览器按需加载：

| 图层 | 内容 |
|---|---|
| 路网 | 公路 + 轨道几何（本档 9,960 条边），含桥/隧道区分 |
| 线路 | 271 条线的走向 + **游戏里那条线的真实颜色** + 停靠站位 |
| 车辆 | 1,370 辆车的实时位置（按铁路/公路/水运/航空上色） |
| 车站 | 565 座站的坐标、容量、客运/货运属性 |
| **客流** | **273 条线的候车 / 在途人数**（含按上车站聚合，看得到"每个站有多少人在等"） |
| 产业 | 215 个产业的位置 + **按厂区实际占地的范围框** |
| 城镇 | 27 个城镇：城名 + **它需要什么货**（商业区/工业区各自的需求） |
| 地形 | 地形等高线（按官方四级重做） |
| 路况 | 道路拥堵色带（见下） |
| 产业链 | 物流关系（见下） |

> 图层文件的命名与数量由 `res/scripts/tpf2_mcp/collectors/layer_registry.lua` 决定，
> 采集频率也在那里（`delay` = 首次触发的帧号，`every` = 之后的间隔帧数）。
> 写进 `bridge/` 后，`1_data_collection/exporters/export-layer-map.py` **自动发现** `layer-*.json` 并切块 ——
> **加图层不用改后端**。

### 二、产业链（选中一个厂，看清它的上下游）

- 面板里可搜索的产业列表 → 选中后**高亮上下游产业**，并画出**物料流向线**
- 流向线的终点**落到具体车站**（靠引擎给的 `stopovers` + 线路站点序列对齐），不是画个大概方向
- 侧栏明细：货种、流量、在途/候运、关联车辆与线路

### 三、产业图标与配方（全部取自游戏本体）

- 图标是**游戏自带的货物图标**（从 `res\textures\ui\ui.zip` 提取，手写 TGA 解码，无第三方库）
  > ⚠️ 仓库里**不含**这些图标文件（它们是游戏素材，可再生成）：克隆后跑一次
  > `python tools/extract-industry-icons.py`，它会从你自己机器上的游戏里提取出来。
- 每个产业显示成 **`原料 ＋ 原料 → 产品`**，用量也是从游戏自己的 `.con` 定义里解出来的
  （例：钢铁厂 = `2 铁矿 + 2 煤 → 1 钢`）
- 例：铁矿=橙色矿石、原油=蓝色水滴、塑料=紫色立方、工具=淡蓝扳手

### 四、车站真实结构

- **333 座**有站房的车站（火车 78 / 汽车 195 / 港口 46 / 机场 14）画出**占地轮廓**与站台
- 模块格子级明细（每个站场由哪些 `.module` 拼成、各在哪个槽位）已能从引擎读出
- 另有 **195 座简易公交站 + 37 座货车卸货站**（没有站房建筑，靠站台自身属性区分）

### 五、经济数据（开发中）

- 从公司账本读**收入 / 维护 / 建设 / 购置 / 利息**五类流水（本档 58,944 条）
- 每条线路的**运价** `defaultPrice`、车辆数、货运量
- 全局累计运输量；库存量走引擎的 `getStock2SimEntityMap`
- ⚠️ 账本条目里**没有"哪条线"字段** —— 所以"某条线一年亏多少"只能靠"维护费+运价"侧路估算，
  这一点在数据里就写明了，不假装能算准

### 六、道路拥堵（开发中）

目标：像导航软件那样把路况涂成 绿/黄/橙/红，**每 5 分钟刷新、放大才显示、可开可关、静态不闪**。

现状：能扫到全部 **10,595 辆 NPC 私家车**（这游戏里"一辆车 = 一个被模拟的居民"，带出行目的地），
**"车 → 所在路段"的映射还在打通**（引擎给的路径下标与路段实体是两套 id，正在建换算表）。

### 七、站台容量与枢纽页

- **枢纽**的定义不靠猜：走引擎自己的**服务范围系统** `catchmentAreaSystem`（两个站的服务范围重叠 → 可换乘
  → 属同一个枢纽），再用并查集求连通分量。本档 **170 个枢纽**，最大的一个含 **29 座站、跨度 1629 m**。
- **站台容量**：引擎里**没有**容量接口，但每条"候车区的边"有 `getNumFreePlaces(edgeId)`，
  **站台容量 = Σ 该站台每条候车边的剩余位置**。实测广州北站站台 1 的 Σ = **476**，与游戏 UI 的「0/476」精确吻合。
  ⚠️ 车站的 `pool.moreCapacity`（站房共享池）是**单独一项**，不是站台容量 —— 早先拿它当分母算出的"超容"是错的。

### 八、数据生成工具（四层里的 1 / 2 层）

| 工具 | 位置 | 作用 |
|---|---|---|
| `extract-industry-icons.py` | `1_data_collection/exporters/` | 从游戏 `ui.zip` 提取货物图标（TGA 手写解码） |
| `extract-industry-recipes.py` | 同上 | 从 `.con` 解出配方与用量（自带硬校验） |
| `build-cargo-types.py` | 同上 | 货种 id → 中文名 + 图标字典 |
| `build-station-structures.py` | 同上 | 站场结构数据（占地框 + 站台 + 模块格子） |
| `build-road-geometry.py` | 同上 | 道路几何（给路况色带用） |
| `export-layer-map.py` | 同上 | 把 `bridge/layer-*.json` 切成前端能读的块（**运行时需要**） |
| `diagnose-industries.py` | `2_brain_analysis/` | 产业供需诊断首版（供应比 / 等待占比） |
| `analyze-line-economics.py` | `2_brain_analysis/` | 线路经济性分析 |
| `find_deadlock_risks.py` | `2_brain_analysis/` | 铁路死锁风险扫描 |
| `build-line-timetable-plan.py` | `2_brain_analysis/` | 运行图建议 |

> 原来这些都在仓库根的 `tools/` 里；2026-10-03 按四层归位后 `tools/` 已空。
> **部署时只有 `serve-rail-map.py` / `export-layer-map.py` / `export-rail-network-map.py` 三个是运行时需要的** ——
> 工坊包里的 `tools/` 由 `0_core_shared/build/build-workshop-package.ps1` 从四层里挑出来组装。

---

## Mod 怎么玩（快速上手）

1. **装 Mod**（见下面的"安装部署"），在游戏里启用它，进一个存档。
2. **保持游戏运行**（1x 就行，**别暂停**）—— 采集器和命令都挂在引擎的 update 回调上。
3. **起 MCP 服务**，让你的 AI 客户端连上；或者**起地图 UI** 自己看：
   ```
   python "<Mod 根>\mcp_server\start_ui.py"
   ```
   浏览器打开 `http://127.0.0.1:8790/`。
4. **打开图层面板**自己挑着看：公路 / 产业 / 车辆 / 线路 / 车站 / 城镇 / 产业链 / 路况。
   面板在左上角，地图可以拖动缩放；大部分图层默认是关的，勾上才画。
5. 想让它采集最新数据：让 AI 调一次 `get_game_state`（带 `force_refresh`），
   或者在页面里等自动刷新的那一轮。

**现在这个阶段它主要用来"看"**：路网长什么样、货从哪流到哪、哪条线堵、哪个厂缺料。
真正去**改游戏**（建线、加车、调站台）走的是受控流程、默认关闭，需要显式启用并逐次审批 ——
见 `docs/agent-mcp-tools.md`。

---

## 安装部署

**完整步骤见 → [`docs/AI_DEPLOY_GUIDE.md`](docs/AI_DEPLOY_GUIDE.md)**
（那份是**写给 AI 助手看的**，人也可以直接照做：三步安装、验证清单、以及一张"别人踩过的坑"列表。）

最省事的路径：

```bat
:: 1) 先改脚本里的 PROJ / STAGE 两个路径变量，然后双击
deploy_mod_layers.bat
:: 2) 完全退出并重启游戏，读档
:: 3) 起地图 UI
python "<Mod 根>\mcp_server\start_ui.py"
```

> 只改了**少数几个** Lua 文件时，用 `deploy-mod-probes.bat` 更快 —— 它是**最小化部署**（6 个文件的固定清单，
> 带 `certutil` md5 双向比对），但清单是写死的，改了清单外的文件**不会同步**，那种情况还是用 `deploy_mod_layers.bat`。

要求：Windows + Steam 版 TPF2 + **Python 3.11+**（无第三方依赖）。

> 🔴 三条最容易翻车的：**复制文件前必须退出游戏**；**改完 Lua 必须重启游戏**（读档不算）；
> **服务放在 Mod 根外面时必须设 `TPF2_MCP_MOD_DIR`**。

---

## 代码怎么组织：四层架构

源码按**四个层**组织（规约全文见 [`0_core_shared/ARCHITECTURE.md`](0_core_shared/ARCHITECTURE.md)，
**写新代码前先去那里确认归属**）：

| 层 | 干什么 | 允许 | 🔴 禁止 | 物理落点 |
|---|---|---|---|---|
| **0 共享契约** | 框架、协议、schema、路径表、构建与校验工具 | 被所有层 import | 放业务逻辑 | `0_core_shared/` ＋ `res/scripts/tpf2_mcp/0_core_shared/` |
| **1 采集** | **只读 + 导出**：把引擎里的东西变成外面能读的 JSON | 读引擎、机械整理、写 JSON | **业务判据**（什么算堵 / 缺货 / 该加车） | `1_data_collection/` ＋ `res/scripts/tpf2_mcp/1_data_collection/` |
| **2 分析** | 纯计算：读 JSON → 出方案 | 数学、统计、图算法、判据 | 写游戏、碰引擎 | `2_brain_analysis/` |
| **3 表现** | 渲染 + 收指令 | 画图、交互、查表 | 核心计算 | `3_dashboard_ui/` |
| **4 执行** | 唯一的写通道 | 改游戏状态（**须先过闸门**） | 自己拿主意 | `4_execution_control/` ＋ `res/scripts/tpf2_mcp/4_execution_control/` |

**归属判定口诀：读 → 算 → 看 → 动**

| 这个动作的输入是 | 归哪层 |
|---|---|
| 引擎对象（组件、实体、`getHeight`） | **1** |
| JSON 里的数字，且要判断"好不好 / 该不该" | **2** |
| 用户的手（点击、拖动、勾选） | **3** |
| 输出要改游戏状态 | **4** |

一个功能穿过 2–4 层是正常的 —— 四层切的是**阶段**，不是**功能模块**。

### 三条硬规则

1. **层间只走文件，不走 `import`** —— 任何 `import` 只能是 0 层或同层内部。
2. **1 层不许有"需要人拍板"的数字** —— 判据一句话：这段代码里有没有一个数字的取值需要人来拍板？
   有（阈值、权重、"该不该"）→ 越界，搬去 2 层。机械整理（聚合、求连通分量、槽位反解）允许。
3. **4 层没有 `approved_actions.json` 里的条目，一律不执行**。

### ⚠️ 但有几条路径被外部钉死，不跟着四层走

`tpf2_mod/`（引擎只从 `res/` 加载 Lua）、`mcp_server/`（MCP 注册点 + 工坊包结构）、
`ui/rail-map/`（地图服务的 `UI_DIRECTORY`）、`protocol/`、`bridge/`（运行时目录）。
**四层是"源码组织"，工坊包是"打平组装"** —— 由 `0_core_shared/build/build-workshop-package.ps1` 负责把四层拼回玩家要的平铺形状。
完整的"谁依赖它 / 能不能动"对照表在 `ARCHITECTURE.md` §二。

---

## 索引与闸门：写代码前先查这里

这个项目最容易犯的错是**"不知道手上有现成的，就自己造一个"**。为此建了两套索引，各带一道**会失败的断言**：

| 索引 | 回答什么问题 | 谁生成 | 闸门命令 |
|---|---|---|---|
| [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md) | **我手上有什么数据、从哪个接口拿、用过没** | `0_core_shared/index/build-data-inventory.py` | `--check`：出现**基线外的新接口**直接失败 |
| [`docs/CODE_WIKI_INDEX.md`](docs/CODE_WIKI_INDEX.md) | **每份源码干什么、凭什么这么写、官方哪一页说的** | `0_core_shared/index/build-code-wiki-index.py` | `--check`：**新增源码文件没登记**直接失败 |
| `0_core_shared/schema/fields.json` | **产物 JSON 里有哪些字段**（新字段前先查） | `0_core_shared/build-fields-index.py` | — |

现状（2026-10-04）：**182 个源码文件 / 1125 个函数全部登记**；**61 个引擎接口在基线内**（代码里实际用了 59 个）。

### 写新采集器 / 新探针之前（硬规矩）

```
① 先查 docs/DATA_INVENTORY.md 第零节「我想要 → 现成接口」
② 再查 0_core_shared/schema/fields.json（产物字段）
③ 现成接口确实不够用，才新写
④ 新接口：补进生成脚本的 WISH_LIST（写清"我想要什么"）→ 再 --update-baseline
⑤ 新文件：登记 docs/code-wiki-map.json
⑥ 提交前跑下面四条
```

```bash
python 0_core_shared/index/build-data-inventory.py --check     # 接口基线
python 0_core_shared/index/build-code-wiki-index.py --check    # 源码登记
python 0_core_shared/index/build-data-inventory.py             # 生成 DATA_INVENTORY.md
python 0_core_shared/index/build-code-wiki-index.py            # 生成 CODE_WIKI_INDEX.md
```

**为什么立这条规矩**：实测引擎有 **31 个 system / 116 个方法**，项目历史上一度只用了 28 个 ——
即八成的"新需求"其实已有现成接口。踩过的例子：想要"每辆车装了什么货"写了新探针，
而现成接口 `getVehicle2Cargo2SimEntitesMap` 一直在；想要"车上乘客"也写了新探针，
而 `line_demand.lua` 早在用 `getSimPersonsForLine`。

> 唯一真相是映射表 `docs/code-wiki-map.json` —— **改代码 → 改映射表 → 重跑生成器**。
> `docs/DATA_INVENTORY.md` 与 `docs/CODE_WIKI_INDEX.md` 都是**自动生成，不要手改**。

---

## 项目组成

- `tpf2_mod/` — Lua Mod 源码（采集器 / 探针 / 图层）。**🔴 契约路径，不随四层移动**
- `mcp_server/` — Python MCP 服务 + 地图 UI 服务端。**🔴 契约路径**（内部本来就已按四层分：`analytics/planning/tasks` = 2 层、`operations/` = 4 层、`bridge/snapshot` = 1 层）
- `ui/rail-map/` — 地图前端（每个图层一个独立脚本）。**🔴 契约路径**（属 P4 待迁）
- `0_core_shared/` `1_data_collection/` `2_brain_analysis/` `3_dashboard_ui/` `4_execution_control/` — **四层源码**
- `protocol/` — bridge 协议定义｜`tests/` — 测试｜`docs/` — 文档
- `bridge/`（运行时生成）— Mod ↔ Python 的通信目录，**不是缓存，别删**

---

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | **现状入口**：需求清单 + 开发进度 + 文档地图 |
| [`0_core_shared/ARCHITECTURE.md`](0_core_shared/ARCHITECTURE.md) | **架构规约（施工图纸）**：四层定义、契约路径表、层间契约、1 层边界、搬迁进度 |
| [`docs/AI_DEPLOY_GUIDE.md`](docs/AI_DEPLOY_GUIDE.md) | **部署指南（给 AI 看的）**：三步安装 + 验证清单 + 坑清单 |
| [`AGENTS.md`](AGENTS.md) | **仓库硬规约**：路径归属、提交禁止项、工坊打包规范、变更前必跑的校验 |
| [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md) | **数据资产总账**（自动生成）：我想要 → 现成接口 |
| [`docs/CODE_WIKI_INDEX.md`](docs/CODE_WIKI_INDEX.md) | **代码 ↔ 官方文档索引**（自动生成） |
| [`docs/REFACTOR_PLAN.md`](docs/REFACTOR_PLAN.md) ／ [`docs/ARCHITECTURE_MERGE.md`](docs/ARCHITECTURE_MERGE.md) | 四层怎么来的、为什么这么分 |
| [`docs/technical-reference.md`](docs/technical-reference.md) | 架构、开发、安装与发布（上游） |
| [`docs/agent-mcp-tools.md`](docs/agent-mcp-tools.md) | 功能与受控操作入口（上游） |
| `docs/` 其余 | 上游各阶段开发文档与验收记录 |
