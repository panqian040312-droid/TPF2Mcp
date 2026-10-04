# 代码 ↔ 官方文档索引

> **本文件由 `0_core_shared/index/build-code-wiki-index.py` 自动生成，不要手改。**
> 要改内容 → 改 `docs/code-wiki-map.json` → 重跑生成器。
> 手改这里的内容，下次生成就会被覆盖掉。

## 一、这张表是干什么的

项目里有两拨代码：**上游作者写的**（`origin/main`，止于 `836b70f`）和
**我们后加的**（分支 `feature/multi-layer-map`）。日子一长就没人说得清
「这段代码凭什么这么写、官方哪一页说的」。这张表就是干这个的：
**每个源码文件、每个函数，落到它依据的官方文档；没有依据的，明写没有。**

| 项 | 数 |
|---|---|
| 已登记的源码文件 | **182 / 182** |
| 扫到的函数 | **1115** 个 |
| ├ 单独标了出处的（函数本身有依据） | 98 |
| ├ 沿用本文件依据的（整文件同一套依据，已在文件级写明） | 1017 |
| └ 本文件判定为「无官方对应」的 | 0 |
| 用到的官方文档 | **34** 份 |

⚠️ **「没标出处」≠「漏了」**：`—` 是本项目自己的工程实现（管道、序列化、
界面外壳），**判定过、确实没有官方对应**；`SRC` 是依据游戏本体文件而非文档；
`SAVE` 是存档实测。三者的区别见下面第三节。

## 二、怎么维护（**新写代码必读**）

```
# 1) 看看有没有漏登记的（提交前跑，不通过就别提交）
python 0_core_shared/index/build-code-wiki-index.py --check

# 2) 改了代码/加了新文件，把新东西登记进映射表
#    改 docs/code-wiki-map.json（结构照抄现有条目）
python 0_core_shared/index/build-code-wiki-index.py --inventory | less   # 看清单

# 3) 重新生成索引
python 0_core_shared/index/build-code-wiki-index.py
```

**规则（已写进 `AGENTS.md`）**：

1. 新增源码文件 → **必须**在 `docs/code-wiki-map.json` 里登记，否则 `--check` 失败；
2. 改了函数的官方依据（比如换了字段来源）→ **必须**同步改映射表里对应那条；
3. 引用官方出处 **必须用代号**（`GM:towns` 这种），写错代号会让 `--check` 失败 ——
   这是故意的：**宁可报错，也不要让出处变成随口一说**。

## 三、出处代号表

| 代号写法 | 指什么 |
|---|---|
| `API:<页名>` | 引擎 API 参考（类型/字段/函数签名） |
| `CM:<页名>` | 社区指南（**必须甄别**，见 _digest/11） |
| `DG:<页名>` | 全库精读摘要（我们自己产出的二手材料） |
| `EX:<页名>` | 官方示例脚本 |
| `GM:<页名>` | 游戏手册（玩家视角：机制、运营、经济） |
| `MD:<页名>` | 官方 modding 文档（格式、字段、脚本） |
| `PN` | 官方文档 × 本项目的对接笔记（我们产出） |
| `SRC` | 游戏本体文件（res/construction、res/scripts、res/models 下的 .con/.module/.mdl/.lua） |
| `SAVE` | 存档实测（bridge 产物 / 探针实测），无文档出处 |
| `SELF` | 本项目自创（无官方对应，也不来自游戏文件） |
| `—` | 无官方对应 |

**关系类型**（这份代码和出处是什么关系）：

| 类型 | 含义 |
|---|---|
| 引用 | 直接调用官方 API / 读官方定义的表 |
| 复刻 | 把官方文档或游戏文件里的公式、编码规则原样实现了一遍 |
| 应用 | 官方机制的一个应用（机制本身是官方的，用法是本项目的） |
| 校验 | 用官方数据反查/校验本项目的实现对不对 |
| 对照 | 与官方做法不一致，或官方无明确说法（要标出来） |

**本索引实际引用到的文档**：

| 代号 | 文档标题 |
|---|---|
| `API:cmd` | Reference |
| `API:engine` | Reference |
| `API:gui` | Reference |
| `API:res` | Reference |
| `API:type` | Reference |
| `DG:04` | （读不到标题） |
| `DG:06` | （读不到标题） |
| `DG:08` | （读不到标题） |
| `DG:09` | （读不到标题） |
| `DG:10` | （读不到标题） |
| `GM:companyandfinances` | Company and Finances |
| `GM:gamefilelocations` | Game File Locations |
| `GM:industriescargos` | Industries and Cargo |
| `GM:linesvehicles` | Lines and Vehicles |
| `GM:modinstallation` | Mod Installation |
| `GM:railwaysignals` | Railway Signals |
| `GM:stationsdepots` | Stations and Depots |
| `GM:statisticsdatalayers` | Statistics and Data Layers |
| `GM:tipstricks` | Tips and Tricks |
| `GM:towns` | Towns |
| `MD:baseconfig` | Base Config |
| `MD:cargotypes` | Cargo Types |
| `MD:constructiontypes` | Construction Types |
| `MD:gamescripts` | Game Scripts |
| `MD:localizations` | Localizations |
| `MD:modcomponents` | Mod Components |
| `MD:modularconstructions` | Modular Constructions |
| `MD:modvalidator` | Mod validator tool (for console modding) |
| `MD:publishing` | Publish a Mod |
| `MD:resourcetypes_mdl` | Model Definition (.mdl) |
| `MD:scriptingbasics` | Scripting Basics |
| `MD:tracksstreets` | Tracks and Streets |
| `MD:vehicletypes` | Vehicle Types |
| `PN` | 官方文档 × 本项目：对接笔记 |
| `SAVE` | 存档实测（bridge 产物 / 探针实测），无文档出处 |
| `SELF` | 本项目自创（无官方对应，也不来自游戏文件） |
| `SRC` | 游戏本体文件（res/construction、res/scripts、res/models 下的 .con/.module/.mdl/.lua） |

## 四、逐文件索引

### 0_core_shared/　（14 个文件）

#### `0_core_shared/build-fields-index.py`　

- **干什么**：**产物字段索引生成器**：扫 `bridge/*.json` 抽出全部字段路径 → 落成 `0_core_shared/schema/fields.json`。用途：新增采集器要写字段前，先查已有路径能不能复用（「复用优先」规矩的字段级入口）
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：放 0 层是因为它是「契约的自我维护」，不属于任何业务层。踩过的坑：搬目录后 `Path(__file__).parent.parent` 会静默算错根目录 —— 本层两个生成器都已改成向上找 `.git`。
- 规模：165 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `bridge_dir` | 定位 bridge 目录：优先环境变量 `TPF2_MCP_MOD_DIR`，否则用本机 staging 默认路径。 | ↳ 同本文件 | （同上） | （同上） |
| `type_name` | 把 Python 值映射成 JSON 类型名（int/number/string/array/object/null）。 | ↳ 同本文件 | （同上） | （同上） |
| `walk` | 递归遍历产物，按 `a.b` / `a[]` 规则累积字段路径；数组最多采样 200 个元素、深度上限 7 层。 | ↳ 同本文件 | （同上） | （同上） |
| `main` | 逐文件解析并合并同名字段（记类型、来源、样本值）；`--check` 只打印统计不写盘。 | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/build/build-phase10-evidence.ps1`　

- **干什么**：Phase 10 证据集构建脚本
- **依据**：`SELF`｜关系：—｜置信度：中
- 规模：51 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `Tool` | — | ↳ 同本文件 | （同上） | （同上） |
| `Resource` | — | ↳ 同本文件 | （同上） | （同上） |
| `WriteJson` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/build/build-phase9-evidence.ps1`　

- **干什么**：Phase 9 证据集构建脚本
- **依据**：`SELF`｜关系：—｜置信度：中
- 规模：70 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `Get-ToolResult` | — | ↳ 同本文件 | （同上） | （同上） |
| `Get-ResourceResult` | — | ↳ 同本文件 | （同上） | （同上） |
| `Write-Json` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/build/build-release-package.py`　

- **干什么**：打可复现的发布包（单一 `tpf2-mcp/` 根）
- **依据**：`MD:publishing`｜关系：应用｜置信度：中
- 规模：38 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/build/build-workshop-package.ps1`　

- **干什么**：打自包含的创意工坊 mod 包（含**逐文件白名单**）
- **依据**：`MD:publishing`、`MD:modcomponents`、`MD:modvalidator`｜关系：引用｜置信度：高
- **备注**：官方三重对应物：modcomponents「只含必要文件」、**ModValidator 0.10.0 的 mod structure whitelist**、consoles「必要文件 + 200MB 未压缩上限」—— 与本项目 AGENTS.md 的白名单同向，可用 `TF2_ModValidator_Public.exe` 自动复核。
- 规模：149 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `Find-Tpf2StagingArea` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/build/collect-diagnostics.ps1`　

- **干什么**：收集诊断材料
- **依据**：`SELF`｜关系：—｜置信度：中
- 规模：81 行 / 0 个函数 ｜ **已登记**

#### `0_core_shared/build/install-mod.ps1`　

- **干什么**：把 mod 装进 staging（游戏真正加载的位置）
- **依据**：`MD:publishing`、`GM:modinstallation`｜关系：引用｜置信度：高
- **备注**：staging 路径 `Steam/userdata/<ID>/1066780/local/staging_area/`；**游戏只在启动时读 mod Lua** ⇒ 改完必须完全退出再启动。
- 规模：108 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `Find-Tpf2GameDirectory` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/checks/validate-snapshot.py`　

- **干什么**：校验世界快照是否符合 schema
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：55 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `check` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/checks/verify-network-semantics.py`　

- **干什么**：核对网络字段语义
- **依据**：`API:type`｜关系：校验｜置信度：中
- 规模：30 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/checks/verify-release-package.py`　

- **干什么**：解包、校验布局、跑离线测试
- **依据**：`MD:modvalidator`｜关系：应用｜置信度：中
- 规模：37 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/checks/verify-ui-ground-truth.py`　

- **干什么**：用游戏界面截图口径核对前端取数
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：38 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/index/build-code-wiki-index.py`　

- **干什么**：**本索引的生成器 + 覆盖率校验器**：扫源码/函数 → 按映射表生成 docs/CODE_WIKI_INDEX.md，并断言「每个文件都登记、每条出处都能落到真实文档」
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：623 行 / 15 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `read_text` | — | ↳ 同本文件 | （同上） | （同上） |
| `_comment_block` | 取第 i 行**之前**紧邻的注释块，拼成一行（做"这个函数干什么"的兜底说明）。 | ↳ 同本文件 | （同上） | （同上） |
| `_docstring_after` | Python 专用：函数体第一句 `\"\"\"...\"\"\"`。很多文件不写前置注释，只写 docstring。 | ↳ 同本文件 | （同上） | （同上） |
| `module_header` | 文件开头那段说明（Lua/PowerShell 是前导注释，Python 是模块 docstring）。 | ↳ 同本文件 | （同上） | （同上） |
| `extract_functions` | 返回 [{name, line, doc}]；line 是 1 起的行号（含 start_line 偏移）。 | ↳ 同本文件 | （同上） | （同上） |
| `iter_source_files` | ── 扫描 ──────────────────────────────────────────────────────────────────── | ↳ 同本文件 | （同上） | （同上） |
| `inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `resolve_doc` | ── 知识库校验 ────────────────────────────────────────────────────────────── | ↳ 同本文件 | （同上） | （同上） |
| `doc_title` | — | ↳ 同本文件 | （同上） | （同上） |
| `run_assertions` | ── 断言 ──────────────────────────────────────────────────────────────────── | ↳ 同本文件 | （同上） | （同上） |
| `collect_codes` | — | ↳ 同本文件 | （同上） | （同上） |
| `take` | — | ↳ 同本文件 | （同上） | （同上） |
| `render` | ── 渲染 ──────────────────────────────────────────────────────────────────── | ↳ 同本文件 | （同上） | （同上） |
| `skeleton` | 按当前源码生成/补全映射表骨架（保留已有内容）。 | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `0_core_shared/index/build-data-inventory.py`　

- **干什么**：生成「数据资产总账 + 交叉索引」→ `docs/DATA_INVENTORY.md`：引擎接口利用率、接口→使用者、产物→字段、字段→产物，以及**「我想要 → 现成接口」对照表**
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：用户 2026-10-03 的批评：「没有充分利用现有的接口和数据，总是造新的探针、新的字段出来，再整理一遍整个mod的架构，要交叉索引」。**批评成立**，证据是同一天两次：① `simPersonSystem.getSimPersonsForLine` 项目里 `line_demand.lua:157` 早在用，我却写新探针去问「乘客能不能读」；② `bridge/world-probe.json` 里早就 dump 了 31 个 system 的全部方法名与 102 个组件，我却靠猜字段名 + 写探针去验证。 ⇒ 根子是**没有一张「我手上到底有什么」的总账**。 首次跑出来的数字：31 个 system / **116 个方法**，项目只调用了 **28 个** ⇒ **88 个现成方法一次都没用过**；其中 `getVehicle2Cargo2SimEntitesMap`（每辆车装了什么）、`simPersonAtTerminalSystem.getNumFreePlaces`（车站候车/剩余容量，R8 卡了很久）、`lineSystem.getProblemLines`（有问题的线路）都是**想要却以为没有**的。 交叉索引的四个方向：接口→谁在用 / 产物→字段 / 字段→产物 / 代码→官方文档（最后一维直接并入已有的 `docs/CODE_WIKI_INDEX.md` 口径）。 🔴 **维护规矩**：源映射表（`WISH_LIST` 常量）手工维护；`used` 由脚本按代码实际调用**自动判定**；**凡是为了拿某个数据而写新采集/新探针之前，先查 `docs/DATA_INVENTORY.md` 第零节**。
- 规模：474 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `scan_calls` | 扫 Lua 源码抽出全部引擎接口调用（7 类正则：system/util/component/game.interface/res/type/顶层函数），跳过整行注释 | `SELF` | — | 高 |
| `load_available` | 读 `world-probe.json` 拿「实测可用的全部接口」：31 个 system 的方法、102 个组件、各命名空间的键 | `API:engine`、`API:type` | 引用 | 高 |
| `collect_keys` | 递归收集产物的键路径（限深度 4，数组只取第一项） | `SELF` | — | 高 |
| `scan_outputs` | 扫 bridge 的 42 个产物：文件名/大小/顶层键/字段路径；超 40MB 的只扫顶层键（bridge 共上百 MB） | `SELF` | — | 高 |
| `main` | 生成 `docs/DATA_INVENTORY.md`：第零节「我想要→现成接口」对照表（含自动判定的用了没）、一「没用过的接口全量」、二「接口→使用者」、三「产物→字段」、四「字段→哪些产物」、五「代码→官方文档」 | `SELF` | — | 高 |

#### `0_core_shared/index/index-tpf2-lua-sources.py`　

- **干什么**：给游戏本体 `res/scripts` 下的 Lua 源码建索引（查官方实现用）
- **依据**：`SRC`｜关系：—｜置信度：高
- 规模：62 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `line_symbols` | — | ↳ 同本文件 | （同上） | （同上） |
| `index_file` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

### 1_data_collection/　（10 个文件）

#### `1_data_collection/exporters/build-cargo-types.py`　

- **干什么**：从游戏文件抽货种定义 → `cargo-types.json`
- **依据**：`MD:cargotypes`｜关系：复刻｜置信度：高
- 规模：105 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/build-road-geometry.py`　

- **干什么**：抽公路边几何 → `road-edge-geometry.json`（路况图层用）
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：150 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `load_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `node_positions` | layer-road.json 的 nodes → {entity_id: (x, y)}。两种形状都吃。 | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/build-station-structures.py`　

- **干什么**：四类站结构反解：slotId → 网格坐标 → 世界坐标，输出 layers/station-structures.json（站台/轨道/站房/泊位/场坪的真实占地）
- **依据**：`MD:modularconstructions`、`SRC`、`PN`｜关系：复刻｜置信度：高
- **备注**：公式抄自游戏 `.con`（SRC），尺寸量自 `.module` 的 `config.extend` 与 `.mdl` 的 `boundingInfo`。🔴 四个已修正的坑：① `construction.transf` 是**列主序**（不是行主序，读错会把整个站场镜像）；② 火车站站房分**回侧/前侧**两套（前侧 slotId 带 +200000）；③ 码头的 `offset`/`shift` 是**带符号的四元素数组**（写成标量整体偏 12.5 m）；④ 汽车站的 x 是**累积量**，必须复现 `.con` 的布局循环并逐列判客运/货运。 ⑤ 出入口按模块名分**进/出/双向**，并给行人的**世界坐标方向向量**（箭头的指向是从 `.con` 自己的 y 分支推的，属推断，不是现成字段）。 ⑥ **站房 x 公式照抄 `.con` 的 `pos`**（`modular_station.con:688-733`）：回侧 `pos.x = minS[j]*5 − 10`、前侧 `pos.x = maxS[j]*5 + 10`；而 `minS[j]`/`maxS[j]` **就是槽位 ID 里编码的那个 `i`** ⇒ 直接用解出来的 i，不必去找站场最外一列。旧写法错在两处：把 −10（`mainBuildingPosition`）当「外移距离」用了两次；用全局列范围代替按排的 minS/maxS（某排列号不从 0 开始时整片挪错）。 ⑦ **从属楼（o=5）走 `tf1`，y 比主楼高 5 m**（`.con` 里是 `k*10 + 5`）。
- 规模：1327 行 / 35 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `load_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `building_box_of` | 站房模块名 → 槽位坐标系里的占地矩形（量自 `.module` 的 `config.extend` + `.mdl` 的 `boundingInfo`） | `SRC`、`MD:modularconstructions` | 复刻 | 高 |
| `load_preview` | 读作者那层的 `station-previews/<id>.json`（拿引擎给的 `scope` 站场坐标系） | `SELF` | 复刻 | 高 |
| `is_cargo_module` | 模块名带 `_cargo` 即货运站房（依据是 `res/construction` 下的模块文件命名） | `SRC` | 复刻 | 高 |
| `rail_base_of` | 按「离哪个基址最近」判槽位种类；主建筑要单独放宽窗口（前侧带 +200000） | `SRC` | 复刻 | 高 |
| `decode_grid` | `base + 1000*i + 10*j → (i,j)`，**处理负 j 的借位**（j 为负时借位写进末尾三位，朴素除法会解成 98/99 且 i 少算 1） | `SRC`、`PN` | 复刻 | 高 |
| `decode_building` | 主建筑/侧楼 `3400000 + 3000*i + 40*j + 10*k + o`；**前侧**版本 slotId 带 +200000 偏移 | `SRC`、`PN` | 复刻 | 高 |
| `apply_transf` | 4×4 矩阵 × 局部坐标 → 世界坐标。🔴 **列主序**（用引擎自己的 `scope.direction` 反证出来的，不是猜的） | `SRC`、`PN` | 复刻 | 高 |
| `poly_rect` | 带朝向的矩形 → 世界坐标四角（四角都过矩阵，矩形当刚体跟着站场转） | `SELF` | 复刻 | 高 |
| `street_demangle` | 汽车站 `200000×(j+100) + 100×(i+100) + v` → (i, j, 变体号) | `SRC` | 复刻 | 高 |
| `street_mangle` | — | ↳ 同本文件 | （同上） | （同上） |
| `street_layout` | 复现 `.con` 的 `coordI2varaintAndPos` 累积布局：**x 要按列累加**，逐列判客运/货运（判据 = 该列 j=0 处有没有 v=0） | `SRC` | 复刻 | 高 |
| `has` | — | ↳ 同本文件 | （同上） | （同上） |
| `half_of` | — | ↳ 同本文件 | （同上） | （同上） |
| `_module_info` | 模块文件名 → 尺寸/种类。表里既有精确键也有 `_building_20_20` 这种后缀键。 | ↳ 同本文件 | （同上） | （同上） |
| `_street_cells` | 汽车站：模块网格 → 多边形；出入口带 `dir`（进/出/双向）与 `arrow`（世界坐标行人方向） | `SRC` | 复刻 | 高 |
| `_water_sym` | — | ↳ 同本文件 | （同上） | （同上） |
| `_water_shift` | — | ↳ 同本文件 | （同上） | （同上） |
| `water_demangle` | 码头 `1000000×(i+100) + 100×(j+100) + facing` → (i, j, 朝向) | `SRC` | 复刻 | 高 |
| `water_local` | 码头槽位 → 局部坐标 + 朝向（查 `.con` 的 `slotDef` 表；offset/shift 是四元素数组，不是标量） | `SRC` | 复刻 | 高 |
| `_water_cells` | 码头：模块网格 → 多边形；行人出入口标双向（码头没有分进出的模块） | `SRC` | 复刻 | 高 |
| `air_local` | 机场槽位 → 局部坐标（`.con` 常数公式；两套 `.con` 编号空间不同，先看 construction.file_name） | `SRC` | 复刻 | 高 |
| `_air_cells` | 机场：模块网格 + `.con` 的场地矩形/跑道/滑行道 → 多边形 | `SRC` | 复刻 | 高 |
| `apply_transf_dir` | 只过矩阵的**线性部分**把方向从局部换到世界 —— 位置要带平移、方向不能带 | `SELF` | 复刻 | 高 |
| `entrance_dir` | 出入口模块名 → 进/出/双向（`entrance.module` / `exit.module` / `entrance_exit.module` 是三个不同的文件） | `SRC` | 复刻 | 高 |
| `build_cells` | 四类站总入口：按 kind 分派到各自的反解；输出前按「先铺底后盖顶」排序 | `MD:modularconstructions`、`SRC`、`PN` | 复刻 | 高 |
| `emit` | — | ↳ 同本文件 | （同上） | （同上） |
| `emit_box` | 按"槽位坐标系里的角点范围"画矩形 —— 四角都过矩阵，矩形跟着站场转。 | ↳ 同本文件 | （同上） | （同上） |
| `box_of` | 取占地包围盒（`BOUNDING_VOLUME`） | `API:type` | 引用 | 高 |
| `terminals_of` | 站台坐标；只有火车站读得出来（水运/道路/航空的 position 全是 0） | `API:type` | 引用 | 中 |
| `report_legend` | — | ↳ 同本文件 | （同上） | （同上） |
| `report_svg` | — | ↳ 同本文件 | （同上） | （同上） |
| `arrow_world` | 出入口格 → 箭头多边形（进/出单头、双向双头），核对报告与前端用同一套归一化轮廓 | `SELF` | 复刻 | 高 |
| `write_report` | 每个站型各出前 `per_kind` 张图 —— 不然火车站的格子最多，会把其它三类挤没。 | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/export-layer-map.py`　

- **干什么**：把 mod 自驱推送的图层数据切块成 manifest + tiles
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：449 行 / 11 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `read_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `shared_bounds` | 取全图层共用的全局 bounds（x/y 两轴）。取不到就返回 None，由调用方自行推算。 | ↳ 同本文件 | （同上） | （同上） |
| `bounds_from_payload` | 兜底：从本层数据自己推一个范围（只在没有铁路 manifest 时用）。 | ↳ 同本文件 | （同上） | （同上） |
| `tile_of` | — | ↳ 同本文件 | （同上） | （同上） |
| `grid_bounds` | 从网格参数推它自己的覆盖范围：origin + step × (cols-1)。 | ↳ 同本文件 | （同上） | （同上） |
| `export_whole_layer` | 整层输出：一个数据文件 + 一个 manifest，不切块。 | ↳ 同本文件 | （同上） | （同上） |
| `export_grid` | 网格图层（地形高度）：整层一个数据文件，**不分块**。 为什么不分块：等高线必须连续。按 tile 切开的话，同一条等高线会在边上断掉， 接缝处还得额外处理跨块连接 —— 而网格本身才几十 KB，整层加载的成本远低于 维护一套跨块接续逻辑。地图（水体/地形）这类"底图"性质的数据都适合这条路径， 与公路/产业/车辆那 | ↳ 同本文件 | （同上） | （同上） |
| `tile_bounds` | — | ↳ 同本文件 | （同上） | （同上） |
| `split_edge_graph` | 边图层：按边的中点决定归属 tile，再把该边用到的节点带进同一个 tile。 返回 (tiles, tile_edges, dropped)。dropped 是"端点缺失或坐标不全"被丢掉的边数 —— 静默丢边会让地图缺线而没人知道，所以一定要报出来。 | ↳ 同本文件 | （同上） | （同上） |
| `split_points` | 点图层：按点自身坐标决定归属 tile。返回 (tiles, tile_points, dropped)。 | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/export-physical-station-map.py`　

- **干什么**：归一化引擎观测到的铁路几何，给独立 SVG viewer 用
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：239 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `curve_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `platform_span_inside_bounds` | — | ↳ 同本文件 | （同上） | （同上） |
| `inside` | — | ↳ 同本文件 | （同上） | （同上） |
| `clipped_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `platform_chain_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `terminal_curve_to_throat_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/export-rail-network-map.py`　

- **干什么**：一次性引擎铁路导出 → 浏览器调度图的数据
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：1124 行 / 32 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `curve_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `shortest_edge_path` | — | ↳ 同本文件 | （同上） | （同上） |
| `ordered_route_points` | — | ↳ 同本文件 | （同上） | （同上） |
| `sampled_edge_path` | Sample the engine Hermite curves in path order instead of replacing them with chords. | ↳ 同本文件 | （同上） | （同上） |
| `simplify` | — | ↳ 同本文件 | （同上） | （同上） |
| `_clip_segment_to_bounds` | Liang-Barsky clip of one track chord to an observed station AABB. | ↳ 同本文件 | （同上） | （同上） |
| `clip_polyline_to_bounds` | — | ↳ 同本文件 | （同上） | （同上） |
| `platform_chain` | — | ↳ 同本文件 | （同上） | （同上） |
| `classify_terminal_station_model` | — | ↳ 同本文件 | （同上） | （同上） |
| `infer_platform_model_track_types` | Find platform-model track types without inferring a station's construction mod. | ↳ 同本文件 | （同上） | （同上） |
| `platform_model_chains` | — | ↳ 同本文件 | （同上） | （同上） |
| `point_polyline_distance` | — | ↳ 同本文件 | （同上） | （同上） |
| `offset_polyline_away_from_center` | Offset a terminal track toward the station exterior while following its curve. | ↳ 同本文件 | （同上） | （同上） |
| `offset_polyline_by_vector` | Translate a platform curve laterally without changing its shape. | ↳ 同本文件 | （同上） | （同上） |
| `modular_station_lateral_vector` | Recover the construction's increasing module-axis from terminal tags. Vanilla and CRST modular stations encode a track module index in tag // 2; even tags put t | ↳ 同本文件 | （同上） | （同上） |
| `offset_modular_station_platforms` | Separate vanilla/CRST modular platforms from their operating rails. | ↳ 同本文件 | （同上） | （同上） |
| `_nominal_module_span` | — | ↳ 同本文件 | （同上） | （同上） |
| `_extend_polyline_ends` | Extend a sampled centreline equally to the nominal platform module ends. | ↳ 同本文件 | （同上） | （同上） |
| `_normalize_modular_platform_span_group` | Give compatible modular terminals their shared longitudinal span. | ↳ 同本文件 | （同上） | （同上） |
| `normalize_modular_station_platform_spans` | Normalize one modular construction without mixing passenger and cargo. A switch inserted inside the construction can terminate one terminal's degree-2 operating | ↳ 同本文件 | （同上） | （同上） |
| `_fit_fixed_platform_centerline` | Fit a straight prefab platform to its nominal construction length. | ↳ 同本文件 | （同上） | （同上） |
| `normalize_fixed_construction_platform_lengths` | Use nominal platform lengths declared by known fixed station resources. | ↳ 同本文件 | （同上） | （同上） |
| `offset_crst_hm_platforms` | Reproduce the four fixed platform paths declared by CRST_HM.con. | ↳ 同本文件 | （同上） | （同上） |
| `mark_track_loading_terminals` | Do not invent a side platform where the construction defines none. | ↳ 同本文件 | （同上） | （同上） |
| `physical_overview_segments` | — | ↳ 同本文件 | （同上） | （同上） |
| `walk` | — | ↳ 同本文件 | （同上） | （同上） |
| `prepare_rail_depots` | — | ↳ 同本文件 | （同上） | （同上） |
| `_project_xy` | — | ↳ 同本文件 | （同上） | （同上） |
| `prepare` | — | ↳ 同本文件 | （同上） | （同上） |
| `build_manifest_and_tiles` | — | ↳ 同本文件 | （同上） | （同上） |
| `apply_station_model_ground_truth` | Apply save-specific user observations without presenting them as engine API data. | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/export-static-station-map.py`　

- **干什么**：导出只读的车站/线路邻域给独立 SVG UI
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：93 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `safe_line_name` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/extract-industry-icons.py`　

- **干什么**：从游戏资源里抽产业/货种**原版图标**（手写 TGA 解码）→ `icons/*.png`
- **依据**：`MD:resourcetypes_mdl`｜关系：复刻｜置信度：高
- **备注**：官方硬约束：游戏只认 `.tga`（无 RLE）/`.dds`（DXT1/3/5），**PNG 不可回灌游戏** ⇒ 这里的 PNG 只能用于外部预览（DG:03）。
- 规模：179 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `decode_tga` | 未压缩 32 位 TGA → (宽, 高, 每行 RGBA 字节)。原点在左下角时自动翻正。 | ↳ 同本文件 | （同上） | （同上） |
| `png_chunk` | — | ↳ 同本文件 | （同上） | （同上） |
| `write_png` | 最小 PNG 编码器：8 位 RGBA（颜色类型 6），不带调色板、不加隔行。 | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/exporters/extract-industry-recipes.py`　

- **干什么**：从游戏 `.con` 抽产业配方『原料 → 产品』＋ **每年最大产量** → `ui/rail-map/industry-recipes.json`（含 `capacity` / `levels` / `max_per_level`）
- **依据**：`GM:industriescargos`｜关系：复刻｜置信度：高
- **备注**： 🔴 2026-10-02 新增：`levels`（数 `["levelN"] = {` 这种**方括号键** —— 按 `levelN = {` 去搜一个都搜不到，踩过）与 `max_per_level`（第 N 级年产量上限 = capacity × Σ产出量 × N）。公式依据见 `count_levels` 的 docstring。 自检里钉了 7 条产量阶梯（煤矿 400 / 农田 200 / 钢铁 200·400 / 加工厂 100·200·300·400 …）——公式被改错（比如忘了乘等级）会立刻报出来。
- 规模：239 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `parse_amounts` | 把 `1,1` / `2` / 空 这种内层数组解成 [1,1] / [2] / []。 `.con` 里 `input = { { 1,1 } }` 的**内层**数组就是一次生产要消耗的量， 按位置对应 `stocks` 里的原料 —— `stocks = {"IRON_ORE","COAL"}` + `{{2,2 | ↳ 同本文件 | （同上） | （同上） |
| `count_levels` | 产业有几个生产等级（`.con` 里 `["level1"]`…`["levelN"]`）；等级就是年产量上限的乘数 | `SRC`、`MD:constructiontypes` | 复刻 | 高 |
| `parse_recipe` | 从 `local stockListConfig` 里取 原料 / 用量 / 产品 / 产出量 / 容量 / 等级数 | `SRC` | 复刻 | 高 |
| `names` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `side` | — | ↳ 同本文件 | （同上） | （同上） |

#### `1_data_collection/probes/collect-line-demand.py`　

- **干什么**：把乘客/货运需求采进本地 SQLite 历史
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：49 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

### 2_brain_analysis/　（6 个文件）

#### `2_brain_analysis/analyze-line-economics.py`　

- **干什么**：按官方收入公式算每条线的收入（权重分摊版）：直线距离 × 每公里价 × 载量 → 权重 → 把账本实测的运输总收入分摊到线
- **依据**：`GM:tipstricks`、`GM:linesvehicles`、`API:type`、`SRC`、`SAVE`｜关系：应用｜置信度：中
- **备注**：用户 2026-10-03 提的方向：「官方文档里面收入是怎么计算的，应该有一套公式，包含货种、数量、距离、速度等元素」。查完的官方口径（三方互证）：① `gamemanual:tipstricks` 原文 —— 收入只看两个量：「The faster people and cargo travel, the higher the revenue」「The farther …, the higher the revenue」，且距离按 「*as the crow flies* between the pick-up point and the drop-off point」= **直线距离**；② `community:gameplaytips-hardmode` —— 「Goods: distance covered. Passengers: distance covered multiplied by speed factor」，速度系数由「the maximum speed of the slowest vehicle on a line」决定 ⇒ **速度只影响客运**；③ `api:type` 的 `LineVehicleInfo.defaultPrice` 官方定义是「Default Ticket price for the line」，而 `gamemanual:linesvehicles` 说「Top speed is a factor in setting a train's transport price per Km」⇒ **defaultPrice 本身已含速度因素**，不要再乘一次速度。 🔴 **货种不影响价格**：实测 17 个 `res/config/cargo_types/*.cargo.lua` 里只有 `weight` （重量）与模型/图标，**没有价格系数**。 ⭐ 另一句关键官方要点：「you get paid by **aerial distance** … you pay maintenance for **real track length**」⇒ 收入按直线、维护费按实际轨道长度 —— **绕路白跑**。 ⚠️ **两个已知偏差**：① 载量用 `cargo_count`（线上在途货物实体数），而**乘客不是 SIM_CARGO** ⇒ 客运线一律 0，本脚本默认把 68 条客运线**排除**，却让货运线分摊了**全部**运输收入 ⇒ 货运数字整体偏高；② 正确做法是先用账本 `by_type_carrier`（2026-10-03 新增）拆出各载体的纯收入，再在载体内部按权重分摊 —— 该聚合**要部署 + 重启后才有数据**。 结果一律标「估算」不标「实测」。
- 规模：290 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `load` | 读 bridge 产物；读不到时提示要设 TPF2_MCP_MOD_DIR 指向 staging | `SELF` | 应用 | 高 |
| `xy` | 取站点的水平坐标（x/y）—— 收入按直线距离算，z 是高度不参与 | `SELF` | 应用 | 高 |
| `main` | 主流程：站点坐标 + defaultPrice + cargo_count → 逐段直线距离 → 权重 → 分摊账本总收入；自检「分摊比例之和 = 1」与「每条距离 > 0」 | `GM:tipstricks`、`API:type` | 应用 | 中 |

#### `2_brain_analysis/analyze-operational-telemetry.py`　

- **干什么**：把实时遥测发现结果汇总成一张「就绪矩阵」
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：75 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `observed_number` | — | ↳ 同本文件 | （同上） | （同上） |
| `observed_reference` | — | ↳ 同本文件 | （同上） | （同上） |
| `analyze` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `2_brain_analysis/build-line-timetable-plan.py`　

- **干什么**：从当前导出证据构一份**默认禁用**的时刻表方案
- **依据**：`GM:linesvehicles`｜关系：应用｜置信度：中
- 规模：67 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `read` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `2_brain_analysis/diagnose-industries.py`　

- **干什么**：产业运转诊断（2026-10-02 重写）：判「这家厂是在正常出货，还是货堆着没人运」，输出 停摆 / 无流量 / 没人运 / 运力不足 / 偏紧 / 正常 六档 + 汇总
- **依据**：`GM:industriescargos`、`GM:towns`｜关系：应用｜置信度：中
- **备注**：🔴 判据＝**堆压月数 = 出货侧 waiting ÷ 年产量上限**，标尺来自游戏本体：`.con` 的 `rule.capacity` × 产出量 × 等级。两条依据：官方 `modding/constructiontypes.md`『#### Rules』原话「The number of times that the rule can be processed per year is limited by `capacity`」＋ 游戏 `res/scripts/industryutil.lua` 里的 `capacity = … * currentLevel`。 上一版的『供应比＝入货÷需求』**已删** —— 实测 4425/4425 条 link 满足 `count = waiting + onboard + other`，`count` 是当前快照量而不是累计量，两个快照相除没有意义；进料侧只有 58/215 家有记录 ⇒ 改成『有数据才列、没数据明说缺口』。 ⚠️ 三个堆压阈值（1 个月 / 3 个月）是**本项目自定**，不是游戏给的；把 `SimBuilding.level` 当 0 起索引用属**推断**（只影响『几个月』的换算比例，不影响分档方向）。 自检：分档之和必须等于总家数。
- 规模：318 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `load` | — | ↳ 同本文件 | （同上） | （同上） |
| `kind_of` | 产业名 → 配方键（长词在前，与 industry-kinds.js 同表） | `SRC` | 复刻 | 高 |
| `main` | 主流程：聚合出货/进料流向 → 按等级取年产量上限 → 算堆压月数 → 分档；另把**一条流量记录都没有**的 75 家补进来（有存货＝没人运 / 零存货＝无流量） | `SELF`、`SRC` | 应用 | 高 |

#### `2_brain_analysis/find_deadlock_risks.py`　

- **干什么**：从拓扑找铁路**死锁风险**：单线走廊、站台净空、袋形股道
- **依据**：`GM:railwaysignals`、`DG:06`｜关系：应用｜置信度：高
- **备注**：两条判据直接来自官方：**不能出现「两个相邻单线车站之间没有会让线」**；**信号必须离道岔留够最长列车全长的净空**。官方还明确「加密信号不是解法」。
- 规模：655 行 / 15 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `load` | — | ↳ 同本文件 | （同上） | （同上） |
| `build_graph` | Undirected multigraph over rail edges that have readable endpoints. | ↳ 同本文件 | （同上） | （同上） |
| `find_bridges` | Tarjan 桥检测（找单线瓶颈） | `SELF` | 应用 | 高 |
| `visit` | — | ↳ 同本文件 | （同上） | （同上） |
| `chain_bridges` | — | ↳ 同本文件 | （同上） | （同上） |
| `other_end` | — | ↳ 同本文件 | （同上） | （同上） |
| `stop_at` | 链终止条件：道岔、站台或死端 | `SELF` | 应用 | 高 |
| `walk` | — | ↳ 同本文件 | （同上） | （同上） |
| `nearest_junction_distance` | 从轨道走到最近道岔的距离 —— 官方点名「信号必须离道岔留够最长列车全长的净空」 | `GM:railwaysignals` | 应用 | 高 |
| `platform_reach` | 站台净空：到最近道岔点的距离 vs 最长列车全长 | `GM:railwaysignals`、`DG:06` | 应用 | 高 |
| `edge_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `fouling_zones` | 短边成串的地方（站场咽喉），列车可能互相妨害 | `GM:railwaysignals` | 应用 | 中 |
| `main` | 主流程：从拓扑找单线走廊 / 站台净空 / 袋形股道 | `GM:railwaysignals` | 应用 | 中 |
| `length_of` | — | ↳ 同本文件 | （同上） | （同上） |
| `junction_count` | — | ↳ 同本文件 | （同上） | （同上） |

#### `2_brain_analysis/record-and-optimize-dwell.py`　

- **干什么**：录实时铁路帧 → 出保守的停站策略方案
- **依据**：`GM:stationsdepots`｜关系：应用｜置信度：中
- 规模：67 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `read_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `fetch_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

### 3_dashboard_ui/　（1 个文件）

#### `3_dashboard_ui/server/serve-rail-map.py`　

- **干什么**：本地只读 HTTP/SSE 服务，供铁路调度图页面取数
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：⚠️ 这个文件里有用户的 510 行未完成改动，动之前先问。🔴 2026-10-02 改了 `end_headers()`：静态缓存的 `Cache-Control: no-store` 原来**按文件名逐个列举**，只列了当时存在的那几个 JS ⇒ 后来新增的前端文件全漏在外面、被浏览器 heuristic 缓存（「刷新也不更新」）。改成**按后缀**匹配（`.html/.js/.css/.json` + 三个目录前缀），以后加文件不必回来改。
- 规模：1273 行 / 40 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `carrier_by_line` | 线路 id → 载具种类（AIR / WATER / ROAD / RAIL）。 ⚠ 每轮 live（约 1.5 s）都会调用 → **按 mtime 缓存**，不要每次重新解析整个文件。 `layer-lines.json` 是 mod 直接写出来的（271 条线，几十 KB），解析一次就够。 | ↳ 同本文件 | （同上） | （同上） |
| `build_other_vehicles` | 船和飞机走**单独一路**，不进 `normalize_live_state`。 原因（2026-09-29 实测）：它们的 `current_edge_id` **全为空** —— 不挂在 `BASE_EDGE_TRACK` / `BASE_EDGE_STREET` 上，所以既会被铁路线路过滤掉， 也没有轨道可以吸附 | ↳ 同本文件 | （同上） | （同上） |
| `game_clock_status` | 游戏内时间相对挂钟的推进速率。 本机 CPU 跟不上时，TPF2 的仿真会跑得比挂钟慢：引擎自己给出的 `simulation.deltas` 里同时含游戏毫秒与挂钟秒，两者之比就是速率。 速率 < 1 时，用挂钟测出的时长必须除以 wall_seconds_per_game_second 才是游戏内时间——运行图（相 | ↳ 同本文件 | （同上） | （同上） |
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_plan_path` | — | ↳ 同本文件 | （同上） | （同上） |
| `current_save_id` | — | ↳ 同本文件 | （同上） | （同上） |
| `_mtime` | — | ↳ 同本文件 | （同上） | （同上） |
| `read_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `status` | — | ↳ 同本文件 | （同上） | （同上） |
| `operations_context` | Return the compact operational subset needed by the station detail panel. | ↳ 同本文件 | （同上） | （同上） |
| `line_demand` | Capacity-side view: engine `line.rate` per line plus configured fleet capacity. CORRECTION (2026-09-27, measured on 271 lines): `line.rate` (the native UI field | ↳ 同本文件 | （同上） | （同上） |
| `_rail_line_ids` | — | ↳ 同本文件 | （同上） | （同上） |
| `_fleet_capacity` | {line_id: {seats, cargo, vehicles: {vehicle_id: {seats, cargo}}}} | ↳ 同本文件 | （同上） | （同上） |
| `_compact_demand` | — | ↳ 同本文件 | （同上） | （同上） |
| `side` | — | ↳ 同本文件 | （同上） | （同上） |
| `sample_line_demand` | — | ↳ 同本文件 | （同上） | （同上） |
| `live_game_seconds` | 当前游戏内时间（秒）。带 1 秒缓存，避免每次都读大文件。 | ↳ 同本文件 | （同上） | （同上） |
| `_record_cargo_history` | 记录货运队列的时间序列（调用方已持有 demand_lock）。 | ↳ 同本文件 | （同上） | （同上） |
| `_cargo_trend` | 从货运时间序列判断"运不走"的三条证据。 游戏逻辑：货运只要「每次都能运完、供给 ≥ 消耗、站点不溢出」就是健康的， 因此实载率、绝对候运量都不能作为判据；唯一有意义的是队列是否在**持续增长**， 以及车是否**真的在取货**（onboard 是否出现过 > 0）。 | ↳ 同本文件 | （同上） | （同上） |
| `persist_demand` | — | ↳ 同本文件 | （同上） | （同上） |
| `demand_live` | — | ↳ 同本文件 | （同上） | （同上） |
| `_bridge_ready` | — | ↳ 同本文件 | （同上） | （同上） |
| `start_demand_sweep` | — | ↳ 同本文件 | （同上） | （同上） |
| `_demand_sweep_worker` | — | ↳ 同本文件 | （同上） | （同上） |
| `vehicle_detail` | Compose one click-oriented vehicle view from cached motion and a bounded Bridge demand probe. | ↳ 同本文件 | （同上） | （同上） |
| `ai_suggestions` | Render bounded, evidence-backed templates only for work MCP cannot finish autonomously. | ↳ 同本文件 | （同上） | （同上） |
| `_task_audit_entries` | — | ↳ 同本文件 | （同上） | （同上） |
| `mcp_work_logs` | — | ↳ 同本文件 | （同上） | （同上） |
| `write_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `refresh_live` | — | ↳ 同本文件 | （同上） | （同上） |
| `refresh_save_scope` | Detect an in-game save switch and refresh all save-bound static data. | ↳ 同本文件 | （同上） | （同上） |
| `regenerate_if_changed` | — | ↳ 同本文件 | （同上） | （同上） |
| `regenerate_layers_if_changed` | bridge/layer-*.json 有变动就重切图块。 与 regenerate_if_changed 的区别：那个盯单个铁路文件，这里盯一组图层文件， 且用"文件名→修改时间"的整体签名判断，避免同一轮里重复切块。 | ↳ 同本文件 | （同上） | （同上） |
| `watch` | — | ↳ 同本文件 | （同上） | （同上） |
| `handler_factory` | — | ↳ 同本文件 | （同上） | （同上） |
| `log_message` | — | ↳ 同本文件 | （同上） | （同上） |
| `end_headers` | — | ↳ 同本文件 | （同上） | （同上） |
| `send_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `do_GET` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

### 4_execution_control/　（21 个文件）

#### `4_execution_control/acceptance/test-dispatch-hold-live.py`　

- **干什么**：单个车辆「扣住再放行」的实机最小复现
- **依据**：`API:cmd`｜关系：校验｜置信度：中
- 规模：90 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-dispatch-task-live.py`　

- **干什么**：通过 Task 层验证扣住/放行
- **依据**：`API:cmd`｜关系：校验｜置信度：中
- 规模：80 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |
| `run` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-final-planner-live.py`　

- **干什么**：采集只读证据供「自动选线路」规划用
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：29 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-final-task-gate-live.py`　

- **干什么**：验证「改线/排班/买车/卖车」只能走 Task 闸门
- **依据**：`API:cmd`｜关系：校验｜置信度：高
- 规模：95 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |
| `run` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-live-bridge.ps1`　

- **干什么**：bridge 连通性实机测试
- **依据**：`SELF`｜关系：—｜置信度：中
- 规模：55 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `Show-FailureDiagnostics` | — | ↳ 同本文件 | （同上） | （同上） |
| `Invoke-BridgeCli` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-live-mcp.ps1`　

- **干什么**：MCP 工具集实机测试
- **依据**：`SELF`｜关系：—｜置信度：中
- 规模：205 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `Invoke-Mcp` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-phase11-live.py`　

- **干什么**：Phase 11 改名/回滚验收（**仅专用存档**）
- **依据**：`API:cmd`｜关系：校验｜置信度：中
- 规模：66 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-phase12-live.py`　

- **干什么**：Phase 12 任务编排验收（仅专用存档）
- **依据**：`SELF`｜关系：—｜置信度：中
- 规模：56 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `save` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-phase13-assign-live.py`　

- **干什么**：一次性 ASSIGN_VEHICLE 探针（**从不重试**）
- **依据**：`API:cmd`｜关系：校验｜置信度：高
- 规模：22 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `dump` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-phase13-buy-live.py`　

- **干什么**：一次性 BUY_VEHICLE 探针（从**不重试**命令）
- **依据**：`API:cmd`｜关系：校验｜置信度：高
- 规模：31 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `dump` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-phase20-configure-goal-live.py`　

- **干什么**：在授权测试存档上验收「建线并配置」目标
- **依据**：`API:cmd`｜关系：校验｜置信度：中
- 规模：79 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-phase20-scheduling-live.py`　

- **干什么**：建一条一次性线路，验证一次停站策略更新
- **依据**：`API:cmd`｜关系：校验｜置信度：中
- 规模：61 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/test-phase20-sell-live.py`　

- **干什么**：一次性 SELL_VEHICLE 验收（仅专用存档）
- **依据**：`API:cmd`｜关系：校验｜置信度：高
- 规模：68 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/acceptance/watch-operations-until.py`　

- **干什么**：持续观察并在一个截止时间前保守地操作一个存档
- **依据**：`API:cmd`｜关系：应用｜置信度：中
- 规模：180 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `fetch` | — | ↳ 同本文件 | （同上） | （同上） |
| `emit` | — | ↳ 同本文件 | （同上） | （同上） |
| `run_tool` | — | ↳ 同本文件 | （同上） | （同上） |
| `resume_game_window` | Toggle pause only through the exact Transport Fever 2 top-level window. | ↳ 同本文件 | （同上） | （同上） |
| `deadline_today` | — | ↳ 同本文件 | （同上） | （同上） |
| `plan_summary` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/actions/apply-dwell-optimization.py`　

- **干什么**：站停优化方案：先 dry-run，再执行可执行条目
- **依据**：`GM:stationsdepots`、`MD:vehicletypes`｜关系：应用｜置信度：中
- 规模：119 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `write` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/actions/apply-line-timetable.py`　

- **干什么**：预览/应用/清除一条线路的常驻时刻表
- **依据**：`GM:linesvehicles`｜关系：应用｜置信度：中
- 规模：45 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/actions/operate-assign-vehicle.py`　

- **干什么**：把一个闲置车辆分配到线路（走 Task 闸门）
- **依据**：`API:cmd`｜关系：引用｜置信度：高
- 规模：51 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/actions/operate-expand-line.py`　

- **干什么**：给线路加一辆已验证的模板车（走 Task 闸门）
- **依据**：`API:cmd`｜关系：引用｜置信度：高
- 规模：107 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `save` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/actions/operate-sell-vehicle.py`　

- **干什么**：卖掉一个明确指定的车辆（走 Task 闸门）
- **依据**：`API:cmd`｜关系：引用｜置信度：高
- 规模：48 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/actions/replace-line-fleet.py`　

- **干什么**：整线换车队：**先加后卖**（先验证替换车到位，再卖原车）
- **依据**：`API:cmd`｜关系：应用｜置信度：高
- 规模：91 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot` | — | ↳ 同本文件 | （同上） | （同上） |
| `run` | — | ↳ 同本文件 | （同上） | （同上） |

#### `4_execution_control/actions/run-operational-telemetry.py`　

- **干什么**：跑全部有界实时遥测分区并合并输出
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：70 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

### mcp_server/　（52 个文件）

#### `mcp_server/src/tpf2_mcp/__init__.py`　

- **干什么**：包标记
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：6 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/src/tpf2_mcp/analytics/__init__.py`　

- **干什么**：分析包标记
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：6 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/src/tpf2_mcp/analytics/evidence.py`　

- **干什么**：分析结论的「证据对象」：每个字段标出**来源与可信级别**
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：值得保留的做法：字段来源分 UI_CROSS_VERIFIED / ENGINE_VERIFIED / DERIVED 三档 —— 与本索引的「置信度」是同一个思路。
- 规模：23 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `evidence` | — | ↳ 同本文件 | （同上） | （同上） |
| `unavailable` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/analytics/network_index.py`　

- **干什么**：快照绑定的网络智能索引：线路/车站指标、分位数、离群、枢纽排名、可达性
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：149 行 / 16 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_line_metrics` | — | ↳ 同本文件 | （同上） | （同上） |
| `_station_metrics` | — | ↳ 同本文件 | （同上） | （同上） |
| `_envelope` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_profile` | — | ↳ 同本文件 | （同上） | （同上） |
| `classify_lines` | — | ↳ 同本文件 | （同上） | （同上） |
| `add` | — | ↳ 同本文件 | （同上） | （同上） |
| `_percentile` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_outliers` | — | ↳ 同本文件 | （同上） | （同上） |
| `similar_lines` | — | ↳ 同本文件 | （同上） | （同上） |
| `station_profile` | — | ↳ 同本文件 | （同上） | （同上） |
| `rank_station_hubs` | — | ↳ 同本文件 | （同上） | （同上） |
| `reachability` | — | ↳ 同本文件 | （同上） | （同上） |
| `isolated_clusters` | — | ↳ 同本文件 | （同上） | （同上） |
| `recommendations` | — | ↳ 同本文件 | （同上） | （同上） |
| `analyze` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/bridge.py`　

- **干什么**：bridge 的 Python 侧：写命令文件 → 等 mod 回应 → 读响应（单槽邮箱）
- **依据**：`MD:gamescripts`、`SELF`｜关系：对照｜置信度：高
- **备注**：官方只规定「引擎线程 ↔ UI 线程靠事件与 `save`/`load` 互传」；本项目用**文件邮箱**实现，属自创。单槽争锁是本项目已知痛点。
- 规模：194 行 / 16 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_mailbox_lock` | Serialize the bridge's single command slot across UI and MCP processes. | ↳ 同本文件 | （同上） | （同上） |
| `_read_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `_atomic_json_write` | — | ↳ 同本文件 | （同上） | （同上） |
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_prepare_directory` | — | ↳ 同本文件 | （同上） | （同上） |
| `status` | — | ↳ 同本文件 | （同上） | （同上） |
| `call` | — | ↳ 同本文件 | （同上） | （同上） |
| `ping` | — | ↳ 同本文件 | （同上） | （同上） |
| `game_state` | — | ↳ 同本文件 | （同上） | （同上） |
| `towns` | — | ↳ 同本文件 | （同上） | （同上） |
| `town` | — | ↳ 同本文件 | （同上） | （同上） |
| `export_rail_network` | Request the one-shot full physical railway sidecar export. | ↳ 同本文件 | （同上） | （同上） |
| `operational_telemetry` | Run one bounded section of the unified read-only telemetry probe. | ↳ 同本文件 | （同上） | （同上） |
| `timetable_status` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_demand` | — | ↳ 同本文件 | （同上） | （同上） |
| `vehicle_dispatch_state` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/cargo.py`　

- **干什么**：货种注册表（从世界快照取，动态）
- **依据**：`MD:cargotypes`、`API:res`｜关系：引用｜置信度：高
- 规模：30 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__post_init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `from_snapshot` | — | ↳ 同本文件 | （同上） | （同上） |
| `list` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/cli.py`　

- **干什么**：命令行入口
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：26 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/config.py`　

- **干什么**：定位游戏目录 / mod · staging / bridge / state 目录
- **依据**：`GM:gamefilelocations`、`MD:publishing`｜关系：引用｜置信度：高
- **备注**：staging 路径 `Steam/userdata/<ID>/1066780/local/staging_area/` 出自 MD:publishing；存档/工作目录结构出自 GM:gamefilelocations。
- 规模：136 行 / 8 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_unique_existing_directories` | — | ↳ 同本文件 | （同上） | （同上） |
| `_steam_roots` | Return Steam library roots without assuming a drive letter. | ↳ 同本文件 | （同上） | （同上） |
| `game_dir` | Locate the TPF2 installation from explicit config or Steam libraries. | ↳ 同本文件 | （同上） | （同上） |
| `mod_dir` | Locate the installed TPF2 MCP mod and return its root directory. | ↳ 同本文件 | （同上） | （同上） |
| `bridge_dir` | Return the bridge beside the installed mod unless explicitly overridden. | ↳ 同本文件 | （同上） | （同上） |
| `state_dir` | Local MCP state, intentionally separate from the mod bridge protocol. | ↳ 同本文件 | （同上） | （同上） |
| `mock_enabled` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot_cache_seconds` | Return a bounded read-only MCP snapshot cache duration. | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/demand_history.py`　

- **干什么**：按线路的引擎需求采样历史（有界持久化）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：72 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_connect` | — | ↳ 同本文件 | （同上） | （同上） |
| `record` | — | ↳ 同本文件 | （同上） | （同上） |
| `query` | — | ↳ 同本文件 | （同上） | （同上） |
| `histories` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/dispatch.py`　

- **干什么**：调度（把发车控制接到 bridge）
- **依据**：`API:cmd`｜关系：应用｜置信度：中
- 规模：87 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_vehicle_count` | — | ↳ 同本文件 | （同上） | （同上） |
| `vehicle_dispatch_state` | — | ↳ 同本文件 | （同上） | （同上） |
| `agent_operations_guide` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/dwell_optimizer.py`　

- **干什么**：站停时长优化建议
- **依据**：`MD:vehicletypes`、`GM:stationsdepots`｜关系：应用｜置信度：中
- **备注**：两个官方输入：`transportVehicle.loadSpeed`（每条车门通道算 1 单位）与 `departureDelay`（MD:vehicletypes / DG:02）；「站台短于列车 → 装卸被拖慢」出自 GM:stationsdepots。
- 规模：203 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_percentile` | — | ↳ 同本文件 | （同上） | （同上） |
| `_round_15` | — | ↳ 同本文件 | （同上） | （同上） |
| `_station_and_platform_index` | — | ↳ 同本文件 | （同上） | （同上） |
| `_line_stop_kind` | — | ↳ 同本文件 | （同上） | （同上） |
| `optimize_dwell_times` | Build a conservative, reversible stop-policy plan from live movement frames. | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/fleet_policy.py`　

- **干什么**：保守的车队规模建议（基于已验证的需求采样）
- **依据**：`GM:linesvehicles`｜关系：应用｜置信度：中
- 规模：47 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `evaluate_fleet_adjustment` | — | ↳ 同本文件 | （同上） | （同上） |
| `metrics` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/graph.py`　

- **干什么**：车站/线路**连通性**图（不是物理走行图）
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：物理路径要以引擎的 `MovePath.path.edges` 为准（DG:08 建议的改法），本文件只做连通性。
- 规模：98 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_other` | — | ↳ 同本文件 | （同上） | （同上） |
| `degree` | — | ↳ 同本文件 | （同上） | （同上） |
| `connected_components` | — | ↳ 同本文件 | （同上） | （同上） |
| `route` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/journal.py`　

- **干什么**：只追加的本地日志（**故意放在 bridge 目录之外**）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：34 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `append` | — | ↳ 同本文件 | （同上） | （同上） |
| `latest` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/lines/__init__.py`　

- **干什么**：线路包标记
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：5 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/src/tpf2_mcp/lines/models.py`　

- **干什么**：线路/站点的数据模型
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：14 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `normalized_stop_sequence` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/lines/stop_resolver.py`　

- **干什么**：把站点解析成引擎实体
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：22 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `resolve_station_stop` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/__init__.py`　

- **干什么**：受控操作层包标记（在引擎 API 未经验证前**故意不含写传输**）
- **依据**：`API:cmd`｜关系：对照｜置信度：高
- 规模：11 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/src/tpf2_mcp/operations/capabilities.py`　

- **干什么**：写能力注册表（保守：一种操作单独验证过才登记）
- **依据**：`API:cmd`、`DG:09`｜关系：引用｜置信度：高
- **备注**：官方共 **34 条写命令**（33 条 `make.*` + 全局 `sendCommand`），本项目只启用了其中少数几条。
- 规模：165 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `capabilities` | Return copies so callers cannot mutate the registry. | ↳ 同本文件 | （同上） | （同上） |
| `capability` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/controller.py`　

- **干什么**：「先出提案再执行」的控制器：逐条验证过的操作才能落地
- **依据**：`API:cmd`、`DG:09`｜关系：应用｜置信度：高
- 规模：319 行 / 14 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_timestamp` | — | ↳ 同本文件 | （同上） | （同上） |
| `_line` | — | ↳ 同本文件 | （同上） | （同上） |
| `_simulation_running` | — | ↳ 同本文件 | （同上） | （同上） |
| `propose` | — | ↳ 同本文件 | （同上） | （同上） |
| `_store_proposal` | — | ↳ 同本文件 | （同上） | （同上） |
| `_persist` | — | ↳ 同本文件 | （同上） | （同上） |
| `validate` | — | ↳ 同本文件 | （同上） | （同上） |
| `execute` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify` | — | ↳ 同本文件 | （同上） | （同上） |
| `rollback` | — | ↳ 同本文件 | （同上） | （同上） |
| `get` | — | ↳ 同本文件 | （同上） | （同上） |
| `recent` | — | ↳ 同本文件 | （同上） | （同上） |
| `_public` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/diff.py`　

- **干什么**：操作前后的状态差异
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：11 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `entity_diff` | Small, explicit entity diff; other world changes are correlation only. | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/__init__.py`　

- **干什么**：操作处理器注册表包标记
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：6 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/src/tpf2_mcp/operations/handlers/assign_vehicle.py`　

- **干什么**：把车辆分配到线路
- **依据**：`API:cmd`｜关系：引用｜置信度：中
- 规模：17 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/base.py`　

- **干什么**：处理器基类
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：14 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/buy_vehicle.py`　

- **干什么**：买车（对应官方 `buyVehicle`）
- **依据**：`API:cmd`｜关系：引用｜置信度：高
- **备注**：🟡 **属 L2 操作**：走官方接口、游戏自己会校验 → 可下放，但必须先报备、用户审核通过才动。
- 规模：14 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/create_line.py`　

- **干什么**：建线（对应官方 `make.line` 一系）
- **依据**：`API:cmd`、`DG:09`｜关系：引用｜置信度：高
- 规模：74 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `resolve` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/registry.py`　

- **干什么**：处理器注册
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：13 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `get` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/sell_vehicle.py`　

- **干什么**：卖车（对应官方 `sellVehicle`）
- **依据**：`API:cmd`｜关系：引用｜置信度：高
- 规模：31 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/set_line_stop_policy.py`　

- **干什么**：改线路停站策略
- **依据**：`API:cmd`｜关系：引用｜置信度：中
- 规模：37 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |
| `_policy` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/set_line_stops.py`　

- **干什么**：改线路站点（对应官方 `setLine` / `updateLine`）
- **依据**：`API:cmd`｜关系：引用｜置信度：高
- 规模：25 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/handlers/vehicle_departure.py`　

- **干什么**：强制发车
- **依据**：`API:cmd`｜关系：引用｜置信度：中
- 规模：42 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `validate_parameters` | — | ↳ 同本文件 | （同上） | （同上） |
| `expected_effect` | — | ↳ 同本文件 | （同上） | （同上） |
| `verify_postcondition` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/operations/models.py`　

- **干什么**：操作提案/结果的数据模型
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：19 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `value` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/overtake_planner.py`　

- **干什么**：待避/越行规划
- **依据**：`GM:railwaysignals`｜关系：应用｜置信度：中
- **备注**：官方口径：列车备用站台的决策点 = **进站前最后一个信号**，且所有备用站台必须从该信号可达（DG:06）。
- 规模：76 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_cyclic_contains_in_order` | — | ↳ 同本文件 | （同上） | （同上） |
| `plan_overtakes` | Find structural overtaking candidates; never authorizes a hold itself. | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/planning/__init__.py`　

- **干什么**：规划包标记
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：5 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/src/tpf2_mcp/planning/decision_support.py`　

- **干什么**：确定性的拓扑 what-if 规划（**从不写 bridge**）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：268 行 / 23 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_baseline_edges` | — | ↳ 同本文件 | （同上） | （同上） |
| `_adjacency` | — | ↳ 同本文件 | （同上） | （同上） |
| `_other` | — | ↳ 同本文件 | （同上） | （同上） |
| `_components` | — | ↳ 同本文件 | （同上） | （同上） |
| `_topology_summary` | — | ↳ 同本文件 | （同上） | （同上） |
| `detect_problems` | — | ↳ 同本文件 | （同上） | （同上） |
| `_component_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `problem_impact` | — | ↳ 同本文件 | （同上） | （同上） |
| `route` | — | ↳ 同本文件 | （同上） | （同上） |
| `build` | — | ↳ 同本文件 | （同上） | （同上） |
| `resilience` | — | ↳ 同本文件 | （同上） | （同上） |
| `visit` | — | ↳ 同本文件 | （同上） | （同上） |
| `_apply_mutations` | — | ↳ 同本文件 | （同上） | （同上） |
| `simulate` | — | ↳ 同本文件 | （同上） | （同上） |
| `simulate_connection` | — | ↳ 同本文件 | （同上） | （同上） |
| `simulate_line_failure` | — | ↳ 同本文件 | （同上） | （同上） |
| `simulate_station_failure` | — | ↳ 同本文件 | （同上） | （同上） |
| `planning_options` | — | ↳ 同本文件 | （同上） | （同上） |
| `new_line_candidates` | Rank topology gaps without claiming demand or physical reachability. | ↳ 同本文件 | （同上） | （同上） |
| `terminal_evidence` | — | ↳ 同本文件 | （同上） | （同上） |
| `compare_scenarios` | — | ↳ 同本文件 | （同上） | （同上） |
| `analyze_and_plan` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/protocol.py`　

- **干什么**：bridge 请求/响应/心跳的封包与解包
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：协议 schema 在本仓库 `protocol/*.schema.json`，是上游作者自定的，不是游戏官方格式。
- 规模：20 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `request` | — | ↳ 同本文件 | （同上） | （同上） |
| `error_response` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/rail_crossings.py`　

- **干什么**：从引擎给的 XYZ 几何里检出**立体交叉**（公铁立交）
- **依据**：`SELF`｜关系：—｜置信度：中
- 规模：171 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_position` | — | ↳ 同本文件 | （同上） | （同上） |
| `_distance_xy` | — | ↳ 同本文件 | （同上） | （同上） |
| `_canonical_direction` | — | ↳ 同本文件 | （同上） | （同上） |
| `_cubic_point` | — | ↳ 同本文件 | （同上） | （同上） |
| `_cross` | — | ↳ 同本文件 | （同上） | （同上） |
| `_segment_intersection` | — | ↳ 同本文件 | （同上） | （同上） |
| `detect_grade_separated_crossings` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/rail_live.py`　

- **干什么**：铁路实时帧（供浏览器高频图层用）
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：356 行 / 15 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_field` | — | ↳ 同本文件 | （同上） | （同上） |
| `_project` | — | ↳ 同本文件 | （同上） | （同上） |
| `_edge_position` | Evaluate the same cubic Hermite curve used by the static rail renderer. | ↳ 同本文件 | （同上） | （同上） |
| `_edge_param_from_position` | Find the nearest parameter on one known rail edge's Hermite curve. | ↳ 同本文件 | （同上） | （同上） |
| `distance2` | — | ↳ 同本文件 | （同上） | （同上） |
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `snap` | — | ↳ 同本文件 | （同上） | （同上） |
| `_object_position` | — | ↳ 同本文件 | （同上） | （同上） |
| `normalize_signals` | — | ↳ 同本文件 | （同上） | （同上） |
| `derive_blocks` | — | ↳ 同本文件 | （同上） | （同上） |
| `walk` | — | ↳ 同本文件 | （同上） | （同上） |
| `_line_progress` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_diagnostics` | — | ↳ 同本文件 | （同上） | （同上） |
| `_simulation_state` | — | ↳ 同本文件 | （同上） | （同上） |
| `normalize_live_state` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/save_scope.py`　

- **干什么**：「一个存档谱系一个本地库」的作用域键
- **依据**：`GM:gamefilelocations`｜关系：应用｜置信度：中
- **备注**：存档是「.sav + .sav.lua + .jpg」三件套（GM:gamefilelocations）⇒ 谱系判定按这套结构走。
- 规模：31 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `snapshot_save_id` | Derive a stable world fingerprint without mutable line/vehicle state. TPF2's verified snapshot API does not expose the save filename or a UUID. Player and town  | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/server.py`　

- **干什么**：MCP stdio 服务（JSON-RPC，一行一消息），把工具暴露给桌面端
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：MCP 是外部协议、不属 TPF2 官方；这里没有任何游戏机制。
- 规模：591 行 / 12 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_bridge` | — | ↳ 同本文件 | （同上） | （同上） |
| `_tool_result` | — | ↳ 同本文件 | （同上） | （同上） |
| `_error` | — | ↳ 同本文件 | （同上） | （同上） |
| `_index` | Use one bridge snapshot for a read-only MCP interaction window. Lua independently refreshes its source snapshot at a short interval. The longer Python window pr | ↳ 同本文件 | （同上） | （同上） |
| `_collection` | — | ↳ 同本文件 | （同上） | （同上） |
| `_intelligence` | — | ↳ 同本文件 | （同上） | （同上） |
| `_planning` | — | ↳ 同本文件 | （同上） | （同上） |
| `_operations` | One in-memory journal per bridge with a mediated bridge executor. | ↳ 同本文件 | （同上） | （同上） |
| `_tasks` | — | ↳ 同本文件 | （同上） | （同上） |
| `_entity` | — | ↳ 同本文件 | （同上） | （同上） |
| `handle` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/snapshot.py`　

- **干什么**：世界快照（schema v2）的索引与只读网络分析
- **依据**：`API:type`、`SELF`｜关系：应用｜置信度：中
- **备注**：字段归一化照引擎的组件/类型定义（API:type）；schema 本身是本项目自定的。
- 规模：312 行 / 39 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_items` | — | ↳ 同本文件 | （同上） | （同上） |
| `__post_init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_by_id` | — | ↳ 同本文件 | （同上） | （同上） |
| `collection` | — | ↳ 同本文件 | （同上） | （同上） |
| `cargo_types` | — | ↳ 同本文件 | （同上） | （同上） |
| `entity` | — | ↳ 同本文件 | （同上） | （同上） |
| `mode` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_summary` | — | ↳ 同本文件 | （同上） | （同上） |
| `network_summary` | — | ↳ 同本文件 | （同上） | （同上） |
| `lines_without_vehicles` | — | ↳ 同本文件 | （同上） | （同上） |
| `unassigned_vehicles` | — | ↳ 同本文件 | （同上） | （同上） |
| `suspicious_lines` | — | ↳ 同本文件 | （同上） | （同上） |
| `world_snapshot` | — | ↳ 同本文件 | （同上） | （同上） |
| `overview` | — | ↳ 同本文件 | （同上） | （同上） |
| `capabilities` | — | ↳ 同本文件 | （同上） | （同上） |
| `_number` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_scorecard` | — | ↳ 同本文件 | （同上） | （同上） |
| `_diagnostic` | — | ↳ 同本文件 | （同上） | （同上） |
| `diagnose_line_structure` | — | ↳ 同本文件 | （同上） | （同上） |
| `diagnose_transport_network` | — | ↳ 同本文件 | （同上） | （同上） |
| `compare_lines` | — | ↳ 同本文件 | （同上） | （同上） |
| `rank_lines` | — | ↳ 同本文件 | （同上） | （同上） |
| `graph` | — | ↳ 同本文件 | （同上） | （同上） |
| `station_connectivity` | — | ↳ 同本文件 | （同上） | （同上） |
| `rank_transfer_stations` | — | ↳ 同本文件 | （同上） | （同上） |
| `find_station_route` | — | ↳ 同本文件 | （同上） | （同上） |
| `fleet_summary` | — | ↳ 同本文件 | （同上） | （同上） |
| `fleet_profile` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_fleet_profile` | — | ↳ 同本文件 | （同上） | （同上） |
| `rank_vehicles_by_capacity` | — | ↳ 同本文件 | （同上） | （同上） |
| `vehicle_operating_state` | — | ↳ 同本文件 | （同上） | （同上） |
| `station_operating_state` | — | ↳ 同本文件 | （同上） | （同上） |
| `line_operating_summary` | — | ↳ 同本文件 | （同上） | （同上） |
| `low_load_vehicles` | — | ↳ 同本文件 | （同上） | （同上） |
| `high_waiting_stations` | — | ↳ 同本文件 | （同上） | （同上） |
| `stations_without_lines` | — | ↳ 同本文件 | （同上） | （同上） |
| `_line` | — | ↳ 同本文件 | （同上） | （同上） |
| `_station` | — | ↳ 同本文件 | （同上） | （同上） |
| `_vehicle` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/station_log.py`　

- **干什么**：车站停站/通过事件日志（从实时轨道帧推出）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：153 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_connect` | — | ↳ 同本文件 | （同上） | （同上） |
| `record_frame` | — | ↳ 同本文件 | （同上） | （同上） |
| `query` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/station_preview.py`　

- **干什么**：每座车站生成一份复用的物理预览（`platform_centerline` / `scope` 站场坐标系）
- **依据**：`API:type`、`SRC`｜关系：复刻｜置信度：高
- **备注**：`scope`（origin + direction/normal + along/across）是**引擎自己给的站场坐标系** —— 前端判断斜站场的位置必须以它为准，不能只看世界坐标（2026-10-02 的教训）。
- 规模：726 行 / 30 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_xy` | — | ↳ 同本文件 | （同上） | （同上） |
| `_station_track_points` | — | ↳ 同本文件 | （同上） | （同上） |
| `_station_direction` | — | ↳ 同本文件 | （同上） | （同上） |
| `_project_frame` | — | ↳ 同本文件 | （同上） | （同上） |
| `_edge_samples` | — | ↳ 同本文件 | （同上） | （同上） |
| `_segment_intersects_rectangle` | — | ↳ 同本文件 | （同上） | （同上） |
| `_point_in_scope` | — | ↳ 同本文件 | （同上） | （同上） |
| `_edge_intersects_scope` | — | ↳ 同本文件 | （同上） | （同上） |
| `_edge_intersects` | — | ↳ 同本文件 | （同上） | （同上） |
| `_polyline_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `_sample_polyline` | — | ↳ 同本文件 | （同上） | （同上） |
| `_aligned_samples` | — | ↳ 同本文件 | （同上） | （同上） |
| `_operating_track_centerline` | — | ↳ 同本文件 | （同上） | （同上） |
| `_polyline_midpoint` | — | ↳ 同本文件 | （同上） | （同上） |
| `_island_pair_distance` | — | ↳ 同本文件 | （同上） | （同上） |
| `_terminal_lateral_order` | — | ↳ 同本文件 | （同上） | （同上） |
| `_platform_faces_gap` | Return whether an explicit platform surface lies on the requested rail side. | ↳ 同本文件 | （同上） | （同上） |
| `_terminal_reference` | — | ↳ 同本文件 | （同上） | （同上） |
| `_offset_unpaired_centerline` | — | ↳ 同本文件 | （同上） | （同上） |
| `build_station_platforms` | Reconstruct side and island platforms from terminal operating tracks. | ↳ 同本文件 | （同上） | （同上） |
| `_shared_construction_groups` | — | ↳ 同本文件 | （同上） | （同上） |
| `_combined_station_bounds` | — | ↳ 同本文件 | （同上） | （同上） |
| `_combined_physical_platforms` | — | ↳ 同本文件 | （同上） | （同上） |
| `_station_scope` | — | ↳ 同本文件 | （同上） | （同上） |
| `world` | — | ↳ 同本文件 | （同上） | （同上） |
| `_scope_bounds` | — | ↳ 同本文件 | （同上） | （同上） |
| `build_station_previews` | — | ↳ 同本文件 | （同上） | （同上） |
| `_write_json_atomic` | — | ↳ 同本文件 | （同上） | （同上） |
| `write_station_previews` | — | ↳ 同本文件 | （同上） | （同上） |
| `main` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/tasks/__init__.py`　

- **干什么**：任务编排包标记（有界、提案优先）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：6 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/src/tpf2_mcp/tasks/goals.py`　

- **干什么**：目标定义
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：187 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_goal_status` | — | ↳ 同本文件 | （同上） | （同上） |
| `goal_capabilities` | — | ↳ 同本文件 | （同上） | （同上） |
| `goal_capability` | — | ↳ 同本文件 | （同上） | （同上） |
| `satisfied` | — | ↳ 同本文件 | （同上） | （同上） |
| `scope_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `planned_steps` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/tasks/orchestrator.py`　

- **干什么**：任务编排器（分步推进 + 人工审批闸门）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：218 行 / 12 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_now` | — | ↳ 同本文件 | （同上） | （同上） |
| `_event` | — | ↳ 同本文件 | （同上） | （同上） |
| `create` | — | ↳ 同本文件 | （同上） | （同上） |
| `plan` | — | ↳ 同本文件 | （同上） | （同上） |
| `approve` | — | ↳ 同本文件 | （同上） | （同上） |
| `continue_task` | — | ↳ 同本文件 | （同上） | （同上） |
| `cancel` | — | ↳ 同本文件 | （同上） | （同上） |
| `get` | — | ↳ 同本文件 | （同上） | （同上） |
| `recent` | — | ↳ 同本文件 | （同上） | （同上） |
| `explain` | — | ↳ 同本文件 | （同上） | （同上） |
| `_public` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/tasks/policy.py`　

- **干什么**：任务策略常量
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：11 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `can_auto_execute` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/timetable_planner.py`　

- **干什么**：线模板循环时刻表规划（基于已验证的快照/实时字段）
- **依据**：`GM:linesvehicles`｜关系：应用｜置信度：中
- 规模：490 行 / 16 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `_percentile` | — | ↳ 同本文件 | （同上） | （同上） |
| `_terminal_kind` | — | ↳ 同本文件 | （同上） | （同上） |
| `_platform_fit` | — | ↳ 同本文件 | （同上） | （同上） |
| `_line_kind` | — | ↳ 同本文件 | （同上） | （同上） |
| `_leg_weights` | — | ↳ 同本文件 | （同上） | （同上） |
| `_round_seconds` | — | ↳ 同本文件 | （同上） | （同上） |
| `_capacity_map` | — | ↳ 同本文件 | （同上） | （同上） |
| `_fleet_demand_profile` | — | ↳ 同本文件 | （同上） | （同上） |
| `_parallel_service_diagnostics` | — | ↳ 同本文件 | （同上） | （同上） |
| `station_pairs` | — | ↳ 同本文件 | （同上） | （同上） |
| `cargo_supported` | — | ↳ 同本文件 | （同上） | （同上） |
| `_event_times` | — | ↳ 同本文件 | （同上） | （同上） |
| `_coordinate_station_phases` | Shift lower-priority line templates to reduce station/throat slot collisions. | ↳ 同本文件 | （同上） | （同上） |
| `score` | — | ↳ 同本文件 | （同上） | （同上） |
| `plan_line_timetables` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/vehicle_length.py`　

- **干什么**：按车辆实际使用的模型资源解析编组长度
- **依据**：`MD:vehicletypes`、`API:res`｜关系：引用｜置信度：高
- **备注**：⚠️ 必须计入 `fakeBogies`（它会改写模型节点树，每节点最多 2 个），否则长度偏小（DG:02）。
- 规模：83 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `model_length` | — | ↳ 同本文件 | （同上） | （同上） |
| `_length_from_source` | — | ↳ 同本文件 | （同上） | （同上） |
| `enrich_snapshot` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/src/tpf2_mcp/work_log.py`　

- **干什么**：给铁路图界面看的「调整日志」（持久化）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：155 行 / 8 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `__init__` | — | ↳ 同本文件 | （同上） | （同上） |
| `_connect` | — | ↳ 同本文件 | （同上） | （同上） |
| `_timestamp` | — | ↳ 同本文件 | （同上） | （同上） |
| `_insert` | — | ↳ 同本文件 | （同上） | （同上） |
| `record_verified_action` | — | ↳ 同本文件 | （同上） | （同上） |
| `sync_task_journal` | Import only postcondition-verified task steps; proposals are never logged as work done. | ↳ 同本文件 | （同上） | （同上） |
| `sync_timetable_plan` | — | ↳ 同本文件 | （同上） | （同上） |
| `query` | — | ↳ 同本文件 | （同上） | （同上） |

#### `mcp_server/start_server.py`　

- **干什么**：不装包直接起 MCP 服务的启动器
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：28 行 / 0 个函数 ｜ **已登记**

#### `mcp_server/start_ui.py`　

- **干什么**：起铁路图 HTTP 服务的启动器
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：24 行 / 0 个函数 ｜ **已登记**

### protocol/　（6 个文件）

#### `protocol/error.schema.json`　

- **干什么**：bridge 错误 schema
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：6 行 / 0 个函数 ｜ **已登记**

#### `protocol/heartbeat.schema.json`　

- **干什么**：心跳 schema（`last_update` 推进 = 游戏真在跑）
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：7 行 / 0 个函数 ｜ **已登记**

#### `protocol/operational-telemetry.schema.json`　

- **干什么**：运营遥测 schema
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：36 行 / 0 个函数 ｜ **已登记**

#### `protocol/request.schema.json`　

- **干什么**：bridge 请求 schema
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：15 行 / 0 个函数 ｜ **已登记**

#### `protocol/response.schema.json`　

- **干什么**：bridge 响应 schema
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：12 行 / 0 个函数 ｜ **已登记**

#### `protocol/snapshot.schema.json`　

- **干什么**：世界快照 schema v2
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：7 行 / 0 个函数 ｜ **已登记**

### tpf2_mod/　（53 个文件）

#### `tpf2_mod/mod.lua`　

- **干什么**：mod 元数据 + `runFn` 入口（资源加载前那一档）
- **依据**：`MD:scriptingbasics`｜关系：引用｜置信度：高
- **备注**：官方两个入口：`runFn`（资源加载前）/ `postRunFn`（加载后）。本 mod 只用前者，所以不能在 `runFn` 里用 `repository.add`。
- 规模：17 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `data` | — | ↳ 同本文件 | （同上） | （同上） |
| `runFn` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/config/game_script/tpf2_mcp.lua`　

- **干什么**：GameScript 入口：`load`/`save`/`update`/`handleEvent` 四个引擎回调 + `guiInit` UI 回调
- **依据**：`MD:gamescripts`｜关系：引用｜置信度：高
- **备注**：官方明说引擎线程（模拟）与 UI 线程（可视化）严格分离、不能共享变量。`update` 是引擎回调 ⇒ 「游戏暂停就收不到命令」由此完全说得通（本项目的轮询式 bridge 就挂在这里）。
- 规模：52 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `data` | — | ↳ 同本文件 | （同上） | （同上） |
| `load` | `load` is invoked repeatedly across UI and engine contexts. Starting file I/O here caused repeated Probe runs and log/CPU pressure. | ↳ 同本文件 | （同上） | （同上） |
| `save` | — | ↳ 同本文件 | （同上） | （同上） |
| `guiInit` | Resource repositories are exposed in the GUI context, while the bridge collector runs in the simulation context. Transfer the runtime track-id -> resource-file  | ↳ 同本文件 | （同上） | （同上） |
| `handleEvent` | — | ↳ 同本文件 | （同上） | （同上） |
| `update` | `update` is the engine callback; runtime.tick initializes once per engine script instance before polling the bridge. | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/api_inventory.lua`　

- **干什么**：运行时把 `api.type` / `api.cmd` 的成员清单导出（Phase 18 用）
- **依据**：`API:cmd`、`API:type`｜关系：引用｜置信度：高
- 规模：22 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.type_inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.command_inventory` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/bridge_io.lua`　

- **干什么**：mod 沙箱内唯一可靠的写盘出口（`write_text` / `write_json` / 图层文件命名）
- **依据**：`MD:scriptingbasics`、`SELF`｜关系：对照｜置信度：高
- **备注**：沙箱没有 `io`/`os`，官方没给写文件的正规 API ⇒ 这条是绕出来的，属本项目自创，不是官方做法。
- 规模：54 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.bridge_dir` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.write_text` | 写纯文本。返回 ok, err | ↳ 同本文件 | （同上） | （同上） |
| `M.write_json` | 写 JSON 文件（先编码再落盘，编码失败不会写坏已有文件）。返回 ok, err | ↳ 同本文件 | （同上） | （同上） |
| `M.layer_file` | 图层文件的统一命名：layer-road.json / layer-industry.json / layer-vehicles.json | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/cargo.lua`　

- **干什么**：货种字典：`api.res.cargoTypeRep` → id/名称/图标
- **依据**：`API:res`、`MD:cargotypes`｜关系：引用｜置信度：高
- 规模：31 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `call` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/common.lua`　

- **干什么**：读引擎字段的通用工具：`pick`（getter→pairs 两条路）、`flatten`、`components_of`、`carrier` 归一、`structure_of`（地面/桥/隧道）
- **依据**：`API:type`、`DG:08`｜关系：应用｜置信度：高
- **备注**：`structure_of` 的判据不是官方文档，是游戏自己的源码（SRC:res/scripts/selectortooltip.lua:70-88）。
- 规模：240 行 / 18 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.clock` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.entity_id` | 实体 id 归一；⚠️ nil 必须短路成 nil（老写法会把 nil 变成字符串 "nil"） | `API:type` | 引用 | 高 |
| `M.structure_of` | 边结构类型 0=地面 / 1=桥 / 2=隧道；判据来自游戏源码 `res/scripts/selectortooltip.lua:70-88` | `SRC` | 复刻 | 高 |
| `M.carrier_name` | carrier 数字/字符串 → 名字（`ROAD/TRAM/RAIL/WATER/AIR`），认不出返回 nil 不猜 | `API:type` | 引用 | 高 |
| `M.majority_key` | 统计表里票数最多的键；并列或空表返回 nil。 | ↳ 同本文件 | （同上） | （同上） |
| `M.component_type` | 解析组件类型常量 | `API:engine` | 引用 | 高 |
| `M.safe_get_component` | 读组件并容错，不污染调用方的 errors | `API:engine` | 引用 | 高 |
| `M.safe_for_each_entity` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.safe_collect` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.name_from_component` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.field` | pcall 包住的字段读取（读不到只返回 nil，不拖垮采集器） | `API:type` | 引用 | 高 |
| `M.array_count` | 用 `#value` 数长度。⚠️ `#` 对 **map（非连续整数 key）** 返回 0 ⇒ 这份返回值**不能当「空」用**，这是本项目踩过的坑 | `API:type` | 对照 | 高 |
| `M.sequence_values` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.safe_type` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.probe_fields` | 字段探测（开发期诊断用） | `SELF` | 应用 | 高 |
| `M.components_of` | 一个实体挂了哪些组件：**按常量名逐个试**（`pairs(ComponentType)` 枚举不出来） | `API:type` | 引用 | 高 |
| `M.flatten` | 把引擎组件（userdata）摊成普通 table | `API:type` | 引用 | 高 |
| `M.pick` | 读字段：**先 getter，再 pairs 兜底**，两条都拿不到才算 nil | `API:type`、`PN` | 复刻 | 高 |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/company.lua`　

- **干什么**：公司组件采集（快照用）
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：51 行 / 3 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `component_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/component_access.lua`　

- **干什么**：组件类型解析（`api.type.ComponentType[name]`）+ 缓存
- **依据**：`API:engine`｜关系：引用｜置信度：高
- 规模：42 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.type` | 解析组件类型（带缓存）。解析不到返回 nil。 | ↳ 同本文件 | （同上） | （同上） |
| `M.get` | 读组件。读不到返回 nil，不抛错、不写任何错误数组。 | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/context_probe.lua`　

- **干什么**：调用上下文 / 返回形状探针（判断「可调用对象还是描述表」）
- **依据**：`API:engine`、`PN`｜关系：校验｜置信度：中
- 规模：90 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `method` | — | ↳ 同本文件 | （同上） | （同上） |
| `call` | — | ↳ 同本文件 | （同上） | （同上） |
| `vehicle_samples` | — | ↳ 同本文件 | （同上） | （同上） |
| `entity_samples` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/demand_probe.lua`　

- **干什么**：乘客/货物流量的事件式采集（挂引擎事件，累计计数）
- **依据**：`MD:gamescripts`｜关系：应用｜置信度：高
- **备注**：依据是游戏自带脚本 SRC:res/scripts/mission/arrivaltracker.lua —— 它证明引擎会派发 `SimPersonSystem.OnCompletedLineUsage` / `SimCargoSystem.OnToArriveAtDestination`。
- 规模：235 行 / 11 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `note_error` | — | ↳ 同本文件 | （同上） | （同上） |
| `bridge_dir` | — | ↳ 同本文件 | （同上） | （同上） |
| `write_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `describe` | 把任意 Lua 值转成可 JSON 序列化的结构（深度与宽度受限） | ↳ 同本文件 | （同上） | （同上） |
| `tally` | — | ↳ 同本文件 | （同上） | （同上） |
| `tally_numeric` | 遍历实体的一层/两层字段，把数值字段计入直方图 | ↳ 同本文件 | （同上） | （同上） |
| `safe_get` | — | ↳ 同本文件 | （同上） | （同上） |
| `snapshot_entity` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.handle_event` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.tick` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.summary` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/dynamic_probe.lua`　

- **干什么**：动态运输来源诊断探针（限 3 辆车，只输出原语值）
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：131 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `cargo_info_samples` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.vehicle_load` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.station_terminal_mapping` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.town_station_relation` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.industry_semantics` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.all` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua`　

- **干什么**：经济探针：公司账本（按 type/carrier/maintenance 聚合）+ 每条线的维护费/运价/车辆数/货运数 + 全局运输统计
- **依据**：`API:type`、`GM:companyandfinances`｜关系：引用｜置信度：高
- **备注**：🔴 账本条目里**没有「哪条线」字段** ⇒ 公司账本只能按 carrier 聚合，线路级亏盈只能靠维护费+运价侧路估算。这条限制来自官方数据结构，不是采集没写全。 🔴 2026-10-03 新增 `by_type_carrier` 交叉聚合：原来 by_type 与 by_carrier 是两个独立汇总，只能拿到 by_carrier.RAIL 的**净额**（INCOME 与 MAINTENANCE 混在一起），判不了「铁路纯收入多少」。`Account.journal` 每条都带 category.type + category.carrier，交叉一次即可拆开。⚠️ 按**具体某条线**仍拆不出（条目没有线路引用）。 🔴 2026-10-03 再补一项：**`person_count`（这条线上在途的乘客实体数）**。原来只采了货（`getSimCargosForLine`），客运线的载量一律 0 —— 于是按收入公式算分摊时68 条客运线被整个排除、货运线数字整体偏高（见 `tools/analyze-line-economics.py`）。 人与货是**同构**的一对接口：`simPersonSystem.getSimPersonsForLine` ↔ `simCargoSystem.getSimCargosForLine`（项目里 `line_demand.lua:157` 早就在用人那条，只是没并进这个批量采集）。 ⚠️ 命名坑：引擎里**乘客叫 `PERSON` 不叫 `PASSENGER`** —— 组件是 `SIM_PERSON` / `SIM_PERSON_AT_VEHICLE` / `SIM_PERSON_AT_TERMINAL`，system 是 `simPersonSystem`，函数是 `getSimPersonsForLine`。按 `passenger` 搜什么都搜不到（只有 `passengersTransported` 这个全局累计量是个例外）。 ⚠️ 两个 count 都是**瞬时快照**（当前在途实体数），不是累计运量。
- 规模：457 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `push_error` | — | ↳ 同本文件 | （同上） | （同上） |
| `call` | 裹 pcall 调用。返回 value；失败返回 nil（错误信息由调用方按需记）。 | ↳ 同本文件 | （同上） | （同上） |
| `each_index` | 遍历"引擎集合"。它们可能是 userdata（不是普通 table），可能是 0 基。 返回 发出的个数, 引擎报的总数。 | ↳ 同本文件 | （同上） | （同上） |
| `present_components` | 某个实体挂了哪些组件。 ⚠️ 2026-09-30 首次实测教训：原本写的 `for name in pairs(api.type.ComponentType) do ... end` **枚举不出任何东西**（返回空数组）—— 本机 `pairs(ComponentType)` 不工作。 改成走 `common.co | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |
| `bump` | — | ↳ 同本文件 | （同上） | （同上） |
| `flatten` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/field_probe.lua`　

- **干什么**：组件字段可用性诊断：钉死「组件视图 vs `game.interface` 聚合表」字段名完全不同这件事
- **依据**：`API:type`、`PN`｜关系：校验｜置信度：高
- **备注**：本项目的核心坑：读字段有**三条取值路**（getter / pairs / 聚合表），少走一条就漏数据。
- 规模：71 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.describe` | 试读一个组件对象，返回命中的字段（只保留能读出来、且不是 nil 的）。 每个键都用 common.field 包了 pcall，读不出来就跳过，不会打断采集。 | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/industry.lua`　

- **干什么**：产业组件采集（快照用）
- **依据**：`API:type`、`GM:industriescargos`｜关系：引用｜置信度：中
- 规模：33 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_freight.lua`　

- **干什么**：产业链物流关系：遍历 `SIM_CARGO` 按 (source, target, cargoType) 聚合成边，带关联交通与站序
- **依据**：`API:type`、`PN`｜关系：应用｜置信度：高
- **备注**：🔴 `SIM_CARGO.sourceEntity` **不是产业实体**，是产业的**库存实体**（= `SIM_BUILDING.stockList`，实测 97/97 零误差）。官方只写 `Entity`、没说是建筑，光看文档必然踩坑。
- 规模：376 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `vec_at` | 读一个 vec3 字段（x/y/z）。z 缺省补 0。取法照 layer_industry.lua，保持一致。 | ↳ 同本文件 | （同上） | （同上） |
| `entity_by_id` | 按 id 取实体。⚠️ 只能用 game.interface.getEntity(id)（项目里 demand_probe / context_probe / dynamic_probe 三处先例）；api.engine.getEntity(edgeId, cargoType) 是**完全不同的东西** （官方定义：" | ↳ 同本文件 | （同上） | （同上） |
| `first_id` | 取实体句柄的数值 id。字段可能是 number、也可能是单元素序列/map（引擎绑定不一致）， 所以三条路都试，全部包 pcall —— 拿不到就返回 nil，绝不让采集器崩。 | ↳ 同本文件 | （同上） | （同上） |
| `bucket_to_array` | 把去重桶转成排好序的定长数组（桶是 string→true 的 map，为了去重） | ↳ 同本文件 | （同上） | （同上） |
| `stopping_bucket_to_array` | 站点桶 → 数组。桶里装的是 { line, wait_stop, dest_stop } 记录（去重靠调用方给的 key）。 排序只为输出稳定（便于 diff 两次采集的差异），不代表业务优先级。 | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_industry.lua`　

- **干什么**：产业图层：`SIM_BUILDING` 等级/库存指针 + 厂区占地包围盒 + 实时库存
- **依据**：`API:type`、`GM:industriescargos`｜关系：引用｜置信度：高
- **备注**：库存读法反复改过：最终用「数 `SIM_ENTITY_AT_STOCK` 实体」，引擎 API 那条降级为形状诊断。
- 规模：280 行 / 8 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `bounds_for` | 位置走 `BOUNDING_VOLUME` 包围盒中心（`SIM_BUILDING` 的组件视图里没有 position） | `API:type` | 引用 | 高 |
| `number_or_nil` | — | ↳ 同本文件 | （同上） | （同上） |
| `pairs_flat` | **实时库存**：数 `SIM_ENTITY_AT_STOCK` 实体（旧版读法实测正确：153,892 件） | `API:type`、`GM:industriescargos` | 应用 | 高 |
| `stock_api_shape` | 只看引擎 API 的形状、**不用它算数**（任何失败都吞掉，绝不影响主路） | `API:type` | 校验 | 高 |
| `by_stock_counts` | 按库存实体计数 | `API:type` | 引用 | 中 |
| `probe_stock_entities` | 库存实体枚举探针 | `API:type` | 引用 | 中 |
| `M.collect` | 产业图层采集主流程（等级 / 库存指针 / 厂区占地） | `API:type`、`GM:industriescargos` | 引用 | 高 |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_lines.lua`　

- **干什么**：全方式线路图层：线路真实颜色 + `stops[]`（真实下标 + 车站 id）
- **依据**：`API:type`｜关系：引用｜置信度：高
- **备注**：不依赖铁路节点 ⇒ 水运/航空/公路线路都能进来（`rail_network.lua` 只能采纯铁路）。
- 规模：267 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `bounds_center` | — | ↳ 同本文件 | （同上） | （同上） |
| `terminal_position` | 站台位置。terminal.vehicleNodeId.entity 是一个 BASE_NODE —— 铁路、公路、水运、航空 站台都有这个节点，所以这里能通吃；rail_network.lua 之所以只拿到铁路站台，是因为它 把这个节点拿去查"铁路节点表"了，查不到就丢。 | ↳ 同本文件 | （同上） | （同上） |
| `carrier_from_file` | — | ↳ 同本文件 | （同上） | （同上） |
| `count_up` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_passenger.lua`　

- **干什么**：**客流图层（流式）**：把客流从「外部主动拉」改成「mod 自驱推」。遍历玩家全部线路，用 `line_demand` 同一套取数逻辑采每线的乘客/货物统计（等候/车上/中位等待/OD 明细），写 `bridge/layer-passenger.json`。替代手动脚本 `collect-line-demand.py` 那条「Python 主动发命令」的旧路。
- **依据**：`API:engine`、`SELF`｜关系：引用｜置信度：高
- **备注**：架构边界：只读 + 机械整理，不做业务判据。必须是流式 —— 一条线要遍历它车上+候车的全部实体，273 条线一次做完会卡帧。
- 规模：187 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `game_time_ms` | 取游戏时间（毫秒）。与 `line_demand.lua` 的同名函数重复，待提进 0 层 common。 | ↳ 同本文件 | （同上） | （同上） |
| `collect_lines` | 玩家全部线路。🔴 用 `pairs` 收成数组，**不能用 `#`** —— 引擎可能返回 map / Sol2 proxy，`#` 会给 0（`line_finance_probe` 踩过）。 | ↳ 同本文件 | （同上） | （同上） |
| `summarize_side` | 把 line_demand 的完整结果裁成汇总：`by_journey` 只留前 12 条，其余字段名原样保留（不新造字段）。 | ↳ 同本文件 | （同上） | （同上） |
| `start_job` | 开一次采集任务：取线路表，准备逐条累加。 | ↳ 同本文件 | （同上） | （同上） |
| `finish` | 收尾：组装 payload（含 `counts.total` 供 layer_registry 记状态）。 | ↳ 同本文件 | （同上） | （同上） |
| `M.advance` | 流式入口：每帧采 BATCH=4 条线；返回 nil = 还没完，返回 table = 产物。签名与 `layer_terrain.advance` 一致。 | ↳ 同本文件 | （同上） | （同上） |
| `M.shape` | 上一次产物的 counts，供人工排查。 | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_registry.lua`　

- **干什么**：图层自驱派发：每 tick 按周期触发各层采集并写文件（Python 侧退化成纯读）
- **依据**：`MD:gamescripts`｜关系：应用｜置信度：高
- **备注**：官方没有「自驱推送」这种用法，但挂载点（引擎 `update` 回调）是官方的；这套节奏是本项目设计的。
- 规模：187 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `publish_payload` | — | ↳ 同本文件 | （同上） | （同上） |
| `publish` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.tick` | 每 tick 调用一次（由 runtime.lua 传入全局 update_count） | ↳ 同本文件 | （同上） | （同上） |
| `M.force` | 手动触发（供将来加显式命令用；不参与自驱节奏） | ↳ 同本文件 | （同上） | （同上） |
| `M.status` | 各层最近一次采集结果。由 runtime.lua 的 heartbeat() 带出去， 这样心跳文件里就能看到图层状态，不用额外开命令通道。 | ↳ 同本文件 | （同上） | （同上） |
| `M.set_enabled` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.layer_names` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_road.lua`　

- **干什么**：公路网图层：`BASE_EDGE_STREET` 边 + 端点坐标
- **依据**：`API:type`、`MD:tracksstreets`｜关系：引用｜置信度：高
- **备注**：必须用 `BASE_EDGE_STREET` 遍历 —— `track` 字段只存在于聚合表，组件视图读不到；`streetType` 同理。
- 规模：173 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `text` | — | ↳ 同本文件 | （同上） | （同上） |
| `street_type_of` | 道路类型（streetType）。组件视图里**没有**这个字段（实测 field_probe 只探到 type / typeIndex / node0 / node1 / tangent），它只存在于 game.interface.getEntity 的聚合表视图 —— 和 position 那批字段一样的"两套 A | ↳ 同本文件 | （同上） | （同上） |
| `node_reader` | 端点节点坐标读取器（照 rail_network.lua 的 base_node()，带去重缓存）。 读不到时只记一条样例错误 —— 否则 9793 个节点会把 errors 撑爆。 | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_road_traffic.lua`　

- **干什么**：道路交通图层：NPC 车流 → 路段聚合（车数/均速/分位）→ 绿黄橙红分档，不逐辆渲染
- **依据**：`DG:08`、`GM:statisticsdatalayers`｜关系：应用｜置信度：高
- **备注**：分档做法对齐游戏自带的 **Street Traffic** 数据图层（官方 `gui.layers.streetTraffic` 三色，见 MD:baseconfig）；车辆定位最终改用**坐标匹配**，因为「传输网边下标 → 实体」那条链形状始终没探明。
- 规模：715 行 / 25 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `push_error` | — | ↳ 同本文件 | （同上） | （同上） |
| `call` | — | ↳ 同本文件 | （同上） | （同上） |
| `each_index` | 引擎集合可能是 userdata、可能 0 基。**先走 getter 拿长度，拿不到再靠 pairs 数**。 | ↳ 同本文件 | （同上） | （同上） |
| `present_components` | — | ↳ 同本文件 | （同上） | （同上） |
| `first_number` | — | ↳ 同本文件 | （同上） | （同上） |
| `keys_of` | — | ↳ 同本文件 | （同上） | （同上） |
| `meta_of` | 路段静态属性（street_type / 有没有公交电车），读一次缓存 | `API:type` | 引用 | 中 |
| `build_edge_index_map` | 某张传输网的「边下标 → BASE_EDGE 实体」表。 没有文档，靠"候选字段必须真是 BASE_EDGE"来验证。**无论成不成，都把首元素的字段形状报出去** —— 第一次实测就吃了"读法不对"的亏（`edges` 只读出 4~26 条，其实是字段路径不对）。 | ↳ 同本文件 | （同上） | （同上） |
| `edge_map_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `aggregate_of` | 读实体的**聚合表**（`game.interface.getEntity(id)`）—— 这是唯一能读到车辆运行字段的路 | `API:engine`、`PN` | 应用 | 高 |
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `vehicle_center` | 车辆的世界坐标：BOUNDING_VOLUME 的 bbox 中心。读法照抄 layer_vehicles（已验证可行）。 | ↳ 同本文件 | （同上） | （同上） |
| `point_segment_distance` | 点到线段距离（纯几何） | `SELF` | 应用 | 高 |
| `build_street_index` | 全部路段几何 + 空间网格索引（读法照抄 `layer_road`） | `API:type` | 引用 | 高 |
| `node_position` | — | ↳ 同本文件 | （同上） | （同上） |
| `attach` | — | ↳ 同本文件 | （同上） | （同上） |
| `nearest` | 最近路段：查所在格 + 8 个邻格（车贴着格子边界时，属边在隔壁） | ↳ 同本文件 | （同上） | （同上） |
| `locate_vehicle` | 车辆定位：**坐标匹配**（90 m 外丢弃）。原来的「传输网边下标 → 实体」那条链形状始终没探明 | `SELF` | 应用 | 高 |
| `probe_vehicle_structure` | 定位失败时的结构深挖（宁可产物大一点，也别瞎猜） | `SELF` | 应用 | 高 |
| `percentile` | 加权重分位 | `SELF` | 应用 | 高 |
| `game_time_now` | 游戏内时间（用作采样节流基准） | `API:engine` | 引用 | 高 |
| `wall_clock` | 挂钟时间（节流兜底） | `SELF` | 应用 | 高 |
| `sample` | 采一次。这是本层的真正工作函数。 | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | 本层主流程：NPC 车流 → 路段聚合 → 分档 | `SELF` | 应用 | 高 |
| `M.last_sample_age` | 供外部/诊断用：上一次采样到现在过了多久 | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_stations.lua`　

- **干什么**：车站互通站群：`catchmentAreaSystem.getStation2stationsAndDistancesMap()` + 并查集求连通分量
- **依据**：`API:engine`、`GM:stationsdepots`｜关系：引用｜置信度：高
- **备注**：「互通」的权威定义就是引擎这张辐射表（乘客能在辐射区重叠的站之间换乘），不是我们按距离猜的。
- 规模：563 行 / 13 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `bounds_center` | — | ↳ 同本文件 | （同上） | （同上） |
| `sample_height` | 并查集：互通是传递关系，站群就是连通分量 取某点的地形高度（米）。参数形式按游戏源码里的用法逐个试，写法照抄 layer_terrain.lua。 🔴 地下站判定必须用「在站台上直接采样」的结果，不能拿地形层的网格插值代替： 那张网格 170 m 一格，落在山谷里的站会被相邻格点的山坡拉高， 实测 24 个普通站因此被 | ↳ 同本文件 | （同上） | （同上） |
| `get_height_function` | — | ↳ 同本文件 | （同上） | （同上） |
| `make_union_find` | — | ↳ 同本文件 | （同上） | （同上） |
| `find` | — | ↳ 同本文件 | （同上） | （同上） |
| `add` | — | ↳ 同本文件 | （同上） | （同上） |
| `union` | — | ↳ 同本文件 | （同上） | （同上） |
| `parse_link_entry` | 从一行键值里抽出"另一个车站"和"距离"。 value 可能是： * 数组：{ {station=..., distance=...}, ... } * 映射：{ [otherStation] = distance } * 数组：{ {otherStation, distance}, ... }（裸数组对） 三种都试， | ↳ 同本文件 | （同上） | （同上） |
| `describe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |
| `dump_shape` | 联通关系探针（2026-09-29） 游戏里**选中车站**会把"与它联通"的产业 / 货场高亮成浅白色。判定这些关系的接口都在 `stationSystem` 下（getStation2TownMap / getStation2edgesMap / getPersonNodeId2StationTerminalsMa | ↳ 同本文件 | （同上） | （同上） |
| `probe_map` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_terrain.lua`　

- **干什么**：地形图层：`game.interface.getHeight({x,y})` 采样 → 等高线 / 水深
- **依据**：`API:engine`、`DG:04`｜关系：引用｜置信度：高
- **备注**：用法取自游戏自带战役 mod（SRC:res/scripts/mission/*.lua 里 20 余处 `getHeight`），可据此确定海平面 = 0。
- 规模：346 行 / 10 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `vec` | 基础读取 | ↳ 同本文件 | （同上） | （同上） |
| `get_height_function` | — | ↳ 同本文件 | （同上） | （同上） |
| `sample_height` | 取某点的地形高度（米）。参数形式按游戏源码里的用法逐个试： getHeight({v.x, v.y}) / getHeight({e.position[1], e.position[2]}) 返回 nil 表示这一点取不到。 | ↳ 同本文件 | （同上） | （同上） |
| `probe_water_surface` | 水体采样：WATER_MESH 的 pos 里应当带水面高度。只读前几个当诊断 —— 海平面是 0 的话，height < 0 就够判水；若水面普遍不为 0，下一版再按 mesh 高度算水深。 | ↳ 同本文件 | （同上） | （同上） |
| `activity_bounds` | 采样范围：所有 BASE_NODE 的包围盒并集。 BASE_NODE 覆盖道路与铁路的全部节点（本存档 9793 个），所以它的范围就是 "玩家铺出去的世界" —— 城镇、产业、路网都落在这个范围里。 | ↳ 同本文件 | （同上） | （同上） |
| `start_job` | 建网格 | ↳ 同本文件 | （同上） | （同上） |
| `probe_axis` | 边界探测：沿四个方向往外走到失效，用来核对采样范围是否合理 （如果四个方向都能走很远，说明 getHeight 在地图外也返回值，探测结果不能用） | ↳ 同本文件 | （同上） | （同上） |
| `finish` | 出结果 | ↳ 同本文件 | （同上） | （同上） |
| `M.advance` | 对外接口（流式） registry 每个 update 调一次。 should_start : 调度相位是否已到（能不能起新一轮） 返回 nil 表示"还在采，别写文件"；返回 table 表示"这一轮采完了，这是产物"。 | ↳ 同本文件 | （同上） | （同上） |
| `M.busy` | 当前是否正在采（供诊断/状态用） | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_town.lua`　

- **干什么**：城镇图层：`TOWN.name` / `TOWN.position` / `Town.cargoNeeds`（城镇要什么货）
- **依据**：`API:type`、`GM:towns`｜关系：引用｜置信度：高
- **备注**：官方 API 只给了字段，**「城镇为什么要货、要了会怎样」在 GM:towns**（三因子 Destinations/Supply/Quality）。本项目「城镇发展优先」的运营前提就建在这页上。
- 规模：314 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `describe` | ── 递归描述一个值。探针专用：宁可啰嗦，也要把"它到底是什么"看清楚。────────────── array 走 sequence_values（依赖 ），map 走 pairs —— **map 这条路是本文件的重点**。 | ↳ 同本文件 | （同上） | （同上） |
| `point_at` | 读一个 vec3（position）。两种形状都要认： ① map { x = …, y = …, z = … } ② 数组 [ x, y, z ] ← 实测 TOWN.position 就是这个形状 （world-probe：`"position": {"type":"table","length":3}` —— l | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |
| `flat_table` | — | ↳ 同本文件 | （同上） | （同上） |
| `pick` | — | ↳ 同本文件 | （同上） | （同上） |
| `pick_parsed` | 取值 + **当场解析**：getter 有可能返回一个"非 nil 但解析不出内容"的空壳 （position 就是这种），只看"非 nil"会误判成已经拿到，从而不再去试 pairs。 2026-09-30 实测：`with_name = 27` 但 `with_position = 0`，就是卡在这一步。 | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_vehicles.lua`　

- **干什么**：车辆图层：`TRANSPORT_VEHICLE` 组件，位置走 `BOUNDING_VOLUME` 包围盒中心
- **依据**：`API:type`｜关系：引用｜置信度：高
- **备注**：组件视图里读不到 position/name/speed ⇒ 位置必须绕包围盒。字段可用性见 PN。
- 规模：159 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `carrier_name` | carrier 的数字→名称映射放在 common（layer_lines 也要用同一份，避免两处各写一遍漂移）。 推导过程见 common.CARRIER_NAMES 处的注释。 | ↳ 同本文件 | （同上） | （同上） |
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `bounds_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `position_for` | 车辆位置。优先 BOUNDING_VOLUME 的包围盒中心；拿不到时退回 `game.interface.getEntity(id).position`。 🔴 为什么必须有这条回退（2026-09-29 实测）：**28 辆列车全部没有包围盒**， 于是地图上一辆列车都不显示，连带所有铁路线路都显示成"没有车"。 而 | ↳ 同本文件 | （同上） | （同上） |
| `number_or_nil` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/line.lua`　

- **干什么**：线路组件采集（快照用）：站点服务、备用站台、UI 指标
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：103 行 / 6 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `optional_number` | — | ↳ 同本文件 | （同上） | （同上） |
| `stop_service` | — | ↳ 同本文件 | （同上） | （同上） |
| `alternative_terminals` | — | ↳ 同本文件 | （同上） | （同上） |
| `add_ui_metrics` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua`　

- **干什么**：「建线」API 形状探针：只构造对象，**从不调用 createLine/updateLine/sendCommand**
- **依据**：`API:type`、`API:cmd`、`DG:09`｜关系：校验｜置信度：高
- **备注**：这是写通道的前置侦察：官方 `buildProposal` 无回滚 ⇒ 摸清形状之前不碰。
- 规模：150 行 / 8 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `attempt_line_shape` | — | ↳ 同本文件 | （同上） | （同上） |
| `attempt_stop_descriptor` | — | ↳ 同本文件 | （同上） | （同上） |
| `attempt_native_stop_copy` | — | ↳ 同本文件 | （同上） | （同上） |
| `attempt_color` | — | ↳ 同本文件 | （同上） | （同上） |
| `nested_stop_type_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `attempt_constructed_native_stop` | This is the exact prerequisite for arbitrary CREATE_LINE. It creates no entity and sends no command: only a Line.Stop userdata is built and placed into a tempor | ↳ 同本文件 | （同上） | （同上） |
| `attempt_mutable_native_stop_vector` | The API's standalone Line.Stop wrapper is not assignable in this build. Test whether a copied engine-native stop vector remains writable inside a temporary Line | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_demand.lua`　

- **干什么**：线路需求：候车/在途占比、等待时长分位
- **依据**：`API:type`｜关系：引用｜置信度：中
- **备注**：线路需求：候车/在途占比、等待时长分位。 🔴 2026-10-03 注意：本文件的 `M.collect(line_id)` **同时采人和货** —— `simPersonSystem.getSimPersonsForLine` ＋ `simCargoSystem.getSimCargosForLine`，是**按需单线**采集（走 MCP 的 `get_line_demand`）。批量版（273 条线一起）在 `economy_probe.lua` 里 —— 那边直到 2026-10-03 才补上人那一半。
- 规模：169 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `entity_number` | — | ↳ 同本文件 | （同上） | （同上） |
| `game_time_ms` | — | ↳ 同本文件 | （同上） | （同上） |
| `sequence_count` | — | ↳ 同本文件 | （同上） | （同上） |
| `cargo_type_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `classify` | — | ↳ 同本文件 | （同上） | （同上） |
| `wait_percentile` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_finance_probe.lua`　

- **干什么**：只读探针：线路/车辆层面的「收入」—— 游戏 UI 那条曲线引擎给不给 mod 读，以及能不能用车辆装载量自己算
- **依据**：`GM:statisticsdatalayers`、`API:type`、`API:engine`｜关系：校验｜置信度：高
- **备注**：用户 2026-10-02 原话：「我在游戏里可以单独查看每个线路的盈亏啊，查」。官方手册 `gamemanual:statisticsdatalayers.md`「Line Details」确实写了：线路窗口有 overview / vehicle list / **FINANCES** / charts 四个标签页，FINANCES 页画的是「actual income from the transported cargo」与「maintenance cost of rolling stock」两条，线路统计表还有 Balance 列 =「the current annual profit or loss」⇒ **数一定存在**。 已排除的三条路（全部实测，不是推断）：① 31 个 system 没有任何财务/统计/账本接口（`bridge/world-probe.json` → `system_methods`，lineSystem 的 9 个方法全是线→站/线→车的连接查询）；② `Line` 组件两条读取路都没有钱 —— 组件视图只有 stops/waitingTime，聚合表只有 itemsTransported/frequency/rate/stops/name/id/type；③ 玩家账本 `ACCOUNT.journal` 5 万条，每条只有 {amount, position, time, category}，category 只有 type/construction/maintenance/other/carrier 五个维度 ⇒ 无线路引用。 ★ 只剩一个没验证过的可能：`LOG_BOOK` 组件（=74）。`type.LogBook` 的 `name2log` 是 {[string]=LogBook.Log}，而 Log 有 times/values —— 官方原文「keeps track of the evolution of data in time」「e.g. amounts of money」，**正是图表数据源该长的样子**；但 world-probe 里它是 walked:false（从没成功遍历到挂它的实体）。本探针去问它。 顺带读 `game.config`（只有 45 个键，全量导出）—— 里面有 `chargeMaintenanceInterval`，正是维护费**周期**那个一直标「待实测」的缺口。 ⚠️ 本探针**尚未在游戏里跑过**：Lua 改动需部署 staging + **完全退出游戏重启**（读档不重载）。 自检做到了「引用的引擎接口逐个对照实测清单验证存在」——`api.engine.system.lineSystem.getLines` / `transportVehicleSystem.getVehicles` / `stockListSystem.getCargoType2stockList2sourceAndCount` 三个在 `world-probe.json` 的 `system_methods` 里确认存在；`api.engine.util.getPlayer` / `api.engine.getComponent` / `game.interface.getEntity` / `game.config.chargeMaintenanceInterval` / `game.config.economy` 在 `registries` 段确认存在。 🔴 2026-10-03 扩了两处：① **车辆类组件也排除了** —— `TRANSPORT_VEHICLE` / `TRAIN` / `SHIP` / `AIRCRAFT` / `RAIL_VEHICLE` 的聚合表**都只有同样 14 个通用字段**（allCapacities / capacities / cargoLoad / carrier / depot / id / line / name / position / speed / state / stopIndex / type / vehicles），**没有钱**；组件视图更空。② **但「基于交通工具算收入」这条路没堵死** —— 缺的不是收入而是**运量**，而运量可能藏在车辆的 `cargoLoad` / `capacities` 里。world-probe 报它们 `length: 0`，⚠️ 那是用 `#` 数的 —— **map 用 `#` 就是 0**（本项目老坑）⇒ 本探针改用 `dump_pairs()`（pairs 枚举、打出键值对）重问一次。若能读出「货种 → 数量」，则「每辆车运了多少 × 运价」成立，按车辆的 `line` 字段汇总就是**每条线的收入**。
- 规模：470 行 / 10 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `describe` | 一个值长什么样（类型 / pairs 计数 / # / 前几个键 / 首元素）。🔴 **不能只用 `#` 数长度** —— `#` 对 map 返回 0，本项目踩过（空数组被当成「读不到」） | `SELF` | 校验 | 高 |
| `read_config` | 导出 `game.config` 全部 45 个键的值。一直缺的维护费**周期**就在 `chargeMaintenanceInterval` | `SRC` | 复刻 | 高 |
| `describe_logbook` | 读 `LOG_BOOK` 组件的 `name2log`：键名清单 + 每条序列的 times/values 形状与前几个点 | `API:type` | 引用 | 高 |
| `hunt_logbook` | 对给定实体试 LOG_BOOK 组件；命中就把 name2log 摊出来（这是「图表数据源」的最后一种可能） | `API:type` | 引用 | 高 |
| `hunt_maintenance` | 对给定实体试 MAINTENANCE_COST 组件（定义就是「对象的维护成本」= UI 那条维护费曲线） | `API:type` | 引用 | 高 |
| `dump_pairs` | 按 pairs 枚举一个集合，打出键值对。**不用 `#`** —— map 用 `#` 会得到 0，本项目因此误判过 cargoLoad「空」 | `SELF` | 校验 | 高 |
| `probe_vehicle_load` | 一辆车的装载与容量：组件视图 + 聚合表两条路的 `cargoLoad` / `capacities` / `allCapacities` 全部用 pairs 摊开；另记 `line` / `name` / `state` 便于归线 | `API:type`、`API:engine` | 校验 | 高 |
| `probe_one_line` | 一条线的两条读取路一起走：组件视图（逐个试组件名 + 已知组件全字段）＋ 聚合表（`game.interface.getEntity`）—— 本项目「组件视图空、聚合表有」的老坑必须两条都走 | `API:type`、`API:engine`、`PN` | 校验 | 高 |
| `M.collect` | 主流程：读配置 → 细查 6 条线 → 扫 420 条线统计两组件覆盖 → 在线路/玩家/车辆上猎捕 LOG_BOOK 与 MAINTENANCE_COST → 出结论段 | `GM:statisticsdatalayers`、`API:type` | 校验 | 高 |
| `try_entity` | 对一个实体同时试两个关键组件，并记录试过哪几类 | `SELF` | 校验 | 高 |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_raw_probe.lua`　

- **干什么**：线路描述符字段/类型探针（不序列化引擎 userdata）
- **依据**：`API:type`｜关系：校验｜置信度：中
- 规模：32 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/operational_telemetry.lua`　

- **干什么**：运营遥测：信号、在途车辆、站台需求、仿真时钟，分区采集
- **依据**：`API:type`、`DG:08`｜关系：引用｜置信度：中
- 规模：394 行 / 19 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `entity_id` | — | ↳ 同本文件 | （同上） | （同上） |
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `bounds_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `model_name` | — | ↳ 同本文件 | （同上） | （同上） |
| `model_instances_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `looks_like_signal` | — | ↳ 同本文件 | （同上） | （同上） |
| `component_inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `member_inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `systems_inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `interface_call` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_signals` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_track_edge_objects` | — | ↳ 同本文件 | （同上） | （同上） |
| `path_edges_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_vehicles` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_live_vehicles` | Compact production frame for the browser's high-frequency live layer. The documented MOVE_PATH.dyn fields are the authoritative source here: dyn.pathPos selects | ↳ 同本文件 | （同上） | （同上） |
| `collect_simulation_clock` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_station_demand` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_clock_inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/operations_probe.lua`　

- **干什么**：运营相关组件探针（车辆/车站/产业/公司/货种的写侧字段形状）
- **依据**：`API:type`、`API:cmd`｜关系：校验｜置信度：中
- 规模：89 行 / 8 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `component` | — | ↳ 同本文件 | （同上） | （同上） |
| `samples` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.vehicle` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.station` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.industry` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.company` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.cargo_registry` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.all` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/rail_network.lua`　

- **干什么**：物理铁路图一次性导出：轨道边/节点、站台、线路站点序列，另带站台周边地形剖面与「正上方有没有贴地公路」
- **依据**：`API:type`、`MD:tracksstreets`｜关系：引用｜置信度：高
- **备注**：逐边限速的权威算法在 MD:tracksstreets（`speedLimit` + 曲线 `speedCoeffs`），拥堵系数的理论走行时间必须按它算。
- 规模：585 行 / 21 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.set_track_resources` | — | ↳ 同本文件 | （同上） | （同上） |
| `entity_id` | — | ↳ 同本文件 | （同上） | （同上） |
| `number` | — | ↳ 同本文件 | （同上） | （同上） |
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `position_from_node` | — | ↳ 同本文件 | （同上） | （同上） |
| `bounds_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_tracks` | — | ↳ 同本文件 | （同上） | （同上） |
| `load_track_resources` | — | ↳ 同本文件 | （同上） | （同上） |
| `track_resource` | — | ↳ 同本文件 | （同上） | （同上） |
| `base_node` | — | ↳ 同本文件 | （同上） | （同上） |
| `terminal_key` | — | ↳ 同本文件 | （同上） | （同上） |
| `alternative_terminals` | — | ↳ 同本文件 | （同上） | （同上） |
| `sample_height` | 取某点的地形高度（米）。参数形式按游戏源码里的用法逐个试，写法同 layer_terrain.lua。 | ↳ 同本文件 | （同上） | （同上） |
| `get_height_function` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_stations` | — | ↳ 同本文件 | （同上） | （同上） |
| `annotate_surroundings` | 采站台周围的**横向 / 纵向地形剖面**。 用户（2026-09-29）给了两件事： ① 第三条判据：原版站（下凹 / 上凸）周围高程是**连续变化**的（地形被游戏改造过， 有平滑过渡坡）；mod 建的地下站没有这个特征 —— 周围都是**实心土**。 ② 采样方式：**站台是长方形的 —— 沿铁路方向变化小、垂直 | ↳ 同本文件 | （同上） | （同上） |
| `trace` | — | ↳ 同本文件 | （同上） | （同上） |
| `annotate_overhead` | 给每个车站标注"正上方有没有贴地的公路"。 为什么要这个：光看"站台比地表低多少"分不开两类东西 —— * 真地下站：站台埋在地下，**上面盖着地面道路/建筑** * 下凹式地面站：站台只是沉在凹地里，**上空是空的**，或者只有很高的桥 （判据是用户 2026-09-29 给的：「地下站一般上面还有东西比如建筑和公路 | ↳ 同本文件 | （同上） | （同上） |
| `collect_lines` | — | ↳ 同本文件 | （同上） | （同上） |
| `collect_depots` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/route_probe.lua`　

- **干什么**：水运/航空航路接口探针 v2：六个 system 的成员逐个试调（不要求 `type=="function"`）
- **依据**：`API:engine`、`DG:09`｜关系：校验｜置信度：中
- **备注**：v1 因为「回报 available:false、member_type:table」就判定不能用，是**把可调用对象当成没有** —— 这条教训已写进 PN §五。
- 规模：509 行 / 13 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `safe_members` | 枚举一个值上能看到的成员（pairs → metatable.__index 两条路都试）。 | ↳ 同本文件 | （同上） | （同上） |
| `shape` | 描述返回值形状。深度受限：userdata 只到"类型 + 一层成员"。 | ↳ 同本文件 | （同上） | （同上） |
| `describe_member` | 一个成员自己长什么样：成员名 + metatable 的 __index / __call 情况。 目的：判断"这是个可调用对象，还只是个描述表"。 | ↳ 同本文件 | （同上） | （同上） |
| `probe_call_value` | ★ v2 的关键：**不管什么类型都试调**。含 nil 的参数一律跳过 （`table.unpack({nil})` 会变成"0 个参数"，那不叫"用实体调"）。 | ↳ 同本文件 | （同上） | （同上） |
| `probe_for_each` | 遍历式接口（forEach 这类）：同样不要求 type == "function"。 | ↳ 同本文件 | （同上） | （同上） |
| `pick_vehicle_targets` | 从 TRANSPORT_VEHICLE 里挑一艘船、一架飞机（判据：带 SHIP / AIRCRAFT 组件）。 | ↳ 同本文件 | （同上） | （同上） |
| `scan_components` | — | ↳ 同本文件 | （同上） | （同上） |
| `probe_api_types` | — | ↳ 同本文件 | （同上） | （同上） |
| `dump_fields` | dump 一个值的前 limit 个字段（键名 / 类型 / 值）。 为什么需要它：现有的 scan_components 只报"这个组件能不能读"（resolved / value_type / walked）， 报**不出内容**。而用户要的"飞机航道 / 跑到占用 / 排队"恰恰是**字段内容** （AIRCRA | ↳ 同本文件 | （同上） | （同上） |
| `first_from_for_each` | 用 forEach 回调拿"第一个实体"。 🔴 为什么非得这样拿（2026-09-30 排错结论）： 上一轮（v2）isReserved / getAirCraftInfo / getShipInfo **全部失败**， 错误是 "expected userdata, received no value" —— 看着像 | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |
| `system_report` | ② 六个 system：成员逐个试调 | ↳ 同本文件 | （同上） | （同上） |
| `variants_for` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/simulation.lua`　

- **干什么**：仿真时钟采集（游戏内时间基准）
- **依据**：`API:engine`｜关系：引用｜置信度：中
- 规模：31 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/station.lua`　

- **干什么**：车站组件采集（快照用）
- **依据**：`API:type`｜关系：引用｜置信度：中
- 规模：22 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_geometry.lua`　

- **干什么**：某个站群周边的物理铁路子图（独立于世界快照 schema）
- **依据**：`API:engine`｜关系：引用｜置信度：高
- **备注**：曾写死站群 id `552273`（该存档里根本不存在）导致产物永远是空壳，已改成现找一个真实站群。
- 规模：291 行 / 17 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `number` | — | ↳ 同本文件 | （同上） | （同上） |
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `entity_id` | — | ↳ 同本文件 | （同上） | （同上） |
| `node_id` | — | ↳ 同本文件 | （同上） | （同上） |
| `bbox_center` | — | ↳ 同本文件 | （同上） | （同上） |
| `position_from_node` | — | ↳ 同本文件 | （同上） | （同上） |
| `normalize_ref` | — | ↳ 同本文件 | （同上） | （同上） |
| `serialize_geometry` | — | ↳ 同本文件 | （同上） | （同上） |
| `network_data` | — | ↳ 同本文件 | （同上） | （同上） |
| `dist2` | — | ↳ 同本文件 | （同上） | （同上） |
| `construction_for` | — | ↳ 同本文件 | （同上） | （同上） |
| `system_map` | — | ↳ 同本文件 | （同上） | （同上） |
| `map_entity` | — | ↳ 同本文件 | （同上） | （同上） |
| `track_graph` | — | ↳ 同本文件 | （同上） | （同上） |
| `base_node` | — | ↳ 同本文件 | （同上） | （同上） |
| `pick_station_group` | 挑一个**真实存在**的站群。 🔴 这个模块原来是写死站群 id 552273 叫进来的。那个组在这个存档里根本不存在， 于是产物永远是 76 字节的 STATION_GROUP_UNAVAILABLE —— 脚本每次都在跑、 数据永远空着，还白搭一次遍历（2026-09-30 全量核对时发现）。 改成现找一个挂了 S | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua`　

- **干什么**：车站结构探针 v3：四类站的**模块网格**（`pairs(params.modules)`）全量导出
- **依据**：`MD:modularconstructions`、`PN`｜关系：复刻｜置信度：高
- **备注**：官方写明 `params.modules` 的索引是 `slotId`、值是 4 字段模块对象；但**格子几何不在组件里**（在构建期 `result.slots[].transf`）⇒ 位置只能靠反解各 `.con` 的打包公式。见 PN §十二/§十三。
- 规模：813 行 / 22 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `vec` | — | ↳ 同本文件 | （同上） | （同上） |
| `kind_of` | — | ↳ 同本文件 | （同上） | （同上） |
| `read_matrix` | — | ↳ 同本文件 | （同上） | （同上） |
| `read_cell` | — | ↳ 同本文件 | （同上） | （同上） |
| `read_cells` | 全量格子清单。 🔴 只给"有多少格"是画不出结构的。要画真实结构，得知道**每格放了什么模块**， 再按 slotId 反解出网格坐标（i, j）—— 各站型的编码不一样，抄自各自的 .con： 火车站 slotId = 基址 + 1000*i + 10*j 格宽 5 m、格长 40 m 码头 slotId = 100 | ↳ 同本文件 | （同上） | （同上） |
| `read_module_grid` | — | ↳ 同本文件 | （同上） | （同上） |
| `preview` | ===================================================================== 通用小工具 ===================================================================== | ↳ 同本文件 | （同上） | （同上） |
| `try_pairs` | — | ↳ 同本文件 | （同上） | （同上） |
| `try_ipairs` | — | ↳ 同本文件 | （同上） | （同上） |
| `meta_info` | — | ↳ 同本文件 | （同上） | （同上） |
| `expand_value` | ===================================================================== ★ 核心：模块对象里到底是什么？ ===================================================================== 把一个 | ↳ 同本文件 | （同上） | （同上） |
| `deep_module_object` | — | ↳ 同本文件 | （同上） | （同上） |
| `deep_modules` | 模块网格：列出全部键；对前几个模块对象深挖。 | ↳ 同本文件 | （同上） | （同上） |
| `deep_params` | params 自身：pairs 是唯一正确读法（size 被容器方法遮蔽）。 | ↳ 同本文件 | （同上） | （同上） |
| `deep_res` | res 层：getAll 给的是路径字符串数组；试传**下标**给 get()。 | ↳ 同本文件 | （同上） | （同上） |
| `safe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | ===================================================================== collect ===================================================================== | ↳ 同本文件 | （同上） | （同上） |
| `construction_entity_for` | 站 → 建筑实体 id（比 getStation2ConstructionMap 干净） | ↳ 同本文件 | （同上） | （同上） |
| `all_full` | 全量口径：采到 FULL_STATION_LIMIT 座站才收工（不再是"每类 2 座就满"）。 | ↳ 同本文件 | （同上） | （同上） |
| `describe` | with_probe：是否带上"字段探针"。**只有每类首例需要** —— 探针的用途是"把字段名探出来"， 全量输出时每座站都带一份纯属浪费体积（565 座 × 4 段探针 ≈ 几百 KB 无用数据）。 | ↳ 同本文件 | （同上） | （同上） |
| `method_names` | ④ 两个 system 的方法名（一次列全） | ↳ 同本文件 | （同上） | （同上） |
| `try_call` | 把任意返回值 dump 成"类型 / 条数 / 前几项"的形状；出错也不炸。 | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/terminal_waiting_probe.lua`　

- **干什么**：**站台候车人数 / 剩余位数探针**（只读、极度克制）。回答 R8 缺的那半：`simPersonAtTerminalSystem.getNumFreePlaces` 能不能读、参数什么形状、返回值是「人」还是「车位」。容量那一半已经有了（`layer-stations.json` 的 `capacity_passenger` / `capacity_cargo`）。
- **依据**：`API:engine`、`SELF`｜关系：引用｜置信度：中
- **备注**：🔴 车站侧接口有**原生崩溃前科** —— operational_telemetry.lua 里留着 `unsafe game.interface station sampling disabled after native crash`，且 context_probe 实测 `getStations()` 的 `waiting` / `capacity` 都是 nil。所以本探针**不遍历 565 个站**。🔴 调用必须写成**完整链式** `api.engine.system.<system>.<method>(...)` —— 接口闸门只认这个形状，少一段就漏检（等于绕过闸门）。挂在 `get_game_state` 上触发，内部缓存只真跑一次。
- 规模：197 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `shape_of` | 描述一个返回值：类型 + 数值 + 表的键。**不序列化 userdata**（这是踩过的坑）。 | ↳ 同本文件 | （同上） | （同上） |
| `method_names` | 只 `pairs` 枚举 system 上的方法名，**不调用**。 | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | 四步：① 两个 system 在不在、有哪些方法；② 只取**第 1 个**带站台的站；③ 对**前 2 个**站台试 `getNumFreePlaces`（userdata / 数字 id 两种形状）；④ 货物侧 `getCount` / `getMaxCount` 对照。**调用上限 6 次**，超了立刻停。 | ↳ 同本文件 | （同上） | （同上） |
| `attempt` | — | ↳ 同本文件 | （同上） | （同上） |
| `try_method` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/town.lua`　

- **干什么**：城镇组件采集（快照用）
- **依据**：`API:type`、`GM:towns`｜关系：引用｜置信度：中
- 规模：27 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/ui_source_probe.lua`　

- **干什么**：UI 数据源探针（找游戏界面用的取数接口）
- **依据**：`API:gui`、`DG:10`｜关系：校验｜置信度：中
- 规模：45 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `callable_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/vehicle.lua`　

- **干什么**：车辆物理参数：编组、车长、最高速度、按货种容量
- **依据**：`API:type`、`MD:vehicletypes`｜关系：引用｜置信度：高
- **备注**：⚠️ `fakeBogies` 会改写模型节点树 ⇒ 用节点树推轴数/车长必须计入，否则站台占用长度估算偏小（DG:02 点名的「本项目最易踩的坑」）。
- 规模：167 行 / 10 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `numeric_sequence` | — | ↳ 同本文件 | （同上） | （同上） |
| `capacity_total` | — | ↳ 同本文件 | （同上） | （同上） |
| `capacity_by_cargo` | — | ↳ 同本文件 | （同上） | （同上） |
| `model_name` | — | ↳ 同本文件 | （同上） | （同上） |
| `model_length_m` | — | ↳ 同本文件 | （同上） | （同上） |
| `consist_parts` | — | ↳ 同本文件 | （同上） | （同上） |
| `model_top_speed_mps` | — | ↳ 同本文件 | （同上） | （同上） |
| `consist_top_speed_kmh` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.collect` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/vehicle_write_probe.lua`　

- **干什么**：车辆写 API 形状探针：列可调用成员、可构造对象，但不发命令
- **依据**：`API:cmd`、`DG:09`｜关系：校验｜置信度：高
- 规模：95 行 / 4 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `shallow_members` | — | ↳ 同本文件 | （同上） | （同上） |
| `documentation` | — | ↳ 同本文件 | （同上） | （同上） |
| `empty_constructor_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.probe` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/world_probe.lua`　

- **干什么**：世界探针 v4：全组件字段枚举 + `game.interface.getEntity(id)` 聚合表全字段
- **依据**：`API:engine`、`API:type`、`PN`｜关系：校验｜置信度：高
- **备注**：「字段到底叫什么」这类问题的第一手来源。v3 的 9373 条通用字段探测里只有 94 条非 nil ⇒ 靠猜字段名行不通。
- 规模：469 行 / 10 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `upper_snake` | ===== 1. 名字推导 ======================================================== PascalCase -> UPPER_SNAKE（v3 验证 100% 成立，无例外） | ↳ 同本文件 | （同上） | （同上） |
| `safe_members` | ===== 4. 工具 ============================================================ 枚举一个 table 的成员；pairs 不行就退到 metatable.__index。 | ↳ 同本文件 | （同上） | （同上） |
| `resolve_component` | — | ↳ 同本文件 | （同上） | （同上） |
| `probe_non_nil` | 只保留非 nil 的字段（v3 的输出 99% 是 {"type":"nil"}，白占体积） | ↳ 同本文件 | （同上） | （同上） |
| `describe_metatable` | 探测一个对象的 metatable：__name（C++ 类型名）+ __index 的键名 | ↳ 同本文件 | （同上） | （同上） |
| `describe_aggregate` | ★ v4 核心：`game.interface.getEntity(id)` 的聚合表全字段枚举 这是从官方 mod 源码里挖出来的入口：getEntity 返回的是一张可 pairs() 的聚合表， 键是小驼峰组件名（stationGroup / simBuildings / vehicles / ...）。 | ↳ 同本文件 | （同上） | （同上） |
| `sample_entity` | ===== 5. 组件遍历 ======================================================== | ↳ 同本文件 | （同上） | （同上） |
| `walk_component` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.probe` | ===== 6. 主流程 ========================================================== | ↳ 同本文件 | （同上） | （同上） |
| `add` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/collectors/write_api_probe.lua`　

- **干什么**：写 API 形状探针（只观察，不调用）
- **依据**：`API:cmd`、`DG:09`｜关系：校验｜置信度：高
- 规模：24 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `kind` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.probe` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/config.lua`　

- **干什么**：模块路径归一（`require` 前缀拼装）
- **依据**：`MD:scriptingbasics`｜关系：引用｜置信度：中
- 规模：46 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `normalize` | — | ↳ 同本文件 | （同上） | （同上） |
| `module_path` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/json.lua`　

- **干什么**：自带 JSON 编解码（沙箱里没有 `json` 库）
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：沙箱约束见 MD:scriptingbasics（Lua 无全局变量、require 根为 res/scripts）。
- 规模：101 行 / 10 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.object` | — | ↳ 同本文件 | （同上） | （同上） |
| `escape` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.encode` | — | ↳ 同本文件 | （同上） | （同上） |
| `decoder` | — | ↳ 同本文件 | （同上） | （同上） |
| `skip` | — | ↳ 同本文件 | （同上） | （同上） |
| `parse_string` | — | ↳ 同本文件 | （同上） | （同上） |
| `parse_array` | — | ↳ 同本文件 | （同上） | （同上） |
| `parse_object` | — | ↳ 同本文件 | （同上） | （同上） |
| `parse_value` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.decode` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua`　

- **干什么**：发车控制（故意 fail-closed：bridge 挂了绝不让列车无限等待）
- **依据**：`API:cmd`、`MD:gamescripts`｜关系：应用｜置信度：高
- 规模：226 行 / 9 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `now` | — | ↳ 同本文件 | （同上） | （同上） |
| `send_departure_command` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.departure_control` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.tick` | Fail safe: a bridge/browser failure must never hold a train indefinitely. | ↳ 同本文件 | （同上） | （同上） |
| `reject` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.dispatch` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.save_state` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.load_state` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.timetable_status` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/operations/line_stop_builder.lua`　

- **干什么**：构造 `Line.Stop` / 线路站点序列（复用观察到的原生描述符，userdata 不过桥）
- **依据**：`API:type`、`DG:09`｜关系：引用｜置信度：高
- **备注**：官方文档定义 `Line.Stop` 是原生配置类型；本 build 里 `api.type.Line.Stop.new()` 给的是包装 userdata，`Line.stops` 拒收 ⇒ 得绕。
- 规模：110 行 / 5 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `M.build_stop` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.construct_stop` | API documentation defines Line.Stop as the native configuration type. The binding name differs across game builds, so this is fail-closed: it only returns a con | ↳ 同本文件 | （同上） | （同上） |
| `M.build_route` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.build_line` | In this TPF2 build api.type.Line.Stop.new() exposes a wrapper userdata that Line.stops rejects. A LINE component's stops vector is accepted natively. Build a te | ↳ 同本文件 | （同上） | （同上） |
| `M.build_line_with_stop_policy` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/operations/timetable_controller.lua`　

- **干什么**：时刻表控制器（发车时刻、挂钟↔游戏时间换算）
- **依据**：`API:cmd`、`GM:linesvehicles`｜关系：应用｜置信度：中
- 规模：235 行 / 19 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `wall_time` | — | ↳ 同本文件 | （同上） | （同上） |
| `entity_number` | — | ↳ 同本文件 | （同上） | （同上） |
| `game_time_seconds` | — | ↳ 同本文件 | （同上） | （同上） |
| `send` | — | ↳ 同本文件 | （同上） | （同上） |
| `release` | — | ↳ 同本文件 | （同上） | （同上） |
| `normalized_offsets` | — | ↳ 同本文件 | （同上） | （同上） |
| `validate` | — | ↳ 同本文件 | （同上） | （同上） |
| `external_timetable_active` | — | ↳ 同本文件 | （同上） | （同上） |
| `minimum_headway` | — | ↳ 同本文件 | （同上） | （同上） |
| `target_key` | — | ↳ 同本文件 | （同上） | （同上） |
| `next_target` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.apply` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.clear` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.controls_line` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.tick` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.record_error` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.status` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.save` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.load` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/runtime.lua`　

- **干什么**：bridge 运行时：轮询命令文件、执行探针、写响应、写 `heartbeat.json`
- **依据**：`MD:gamescripts`｜关系：应用｜置信度：高
- **备注**：轮询挂在引擎 `update` 回调上（官方唯一的引擎线程周期入口）⇒ 游戏不跑（或暂停）就不推进。
- 规模：328 行 / 19 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `path` | — | ↳ 同本文件 | （同上） | （同上） |
| `now` | — | ↳ 同本文件 | （同上） | （同上） |
| `read_file` | — | ↳ 同本文件 | （同上） | （同上） |
| `write_file` | — | ↳ 同本文件 | （同上） | （同上） |
| `write_json` | — | ↳ 同本文件 | （同上） | （同上） |
| `log` | — | ↳ 同本文件 | （同上） | （同上） |
| `probe_call` | — | ↳ 同本文件 | （同上） | （同上） |
| `raw_write` | — | ↳ 同本文件 | （同上） | （同上） |
| `run_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `heartbeat` | — | ↳ 同本文件 | （同上） | （同上） |
| `response` | — | ↳ 同本文件 | （同上） | （同上） |
| `write_response` | — | ↳ 同本文件 | （同上） | （同上） |
| `validate_command` | — | ↳ 同本文件 | （同上） | （同上） |
| `handle` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.start` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.set_track_resources` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.save` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.load` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.tick` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/res/scripts/tpf2_mcp/state.lua`　

- **干什么**：探针注册表：一张「探针名 → 入口函数」的表，供 bridge 命令派发
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**： ⚠️ 2026-10-03 给 `lines[].throughput` 的来源说明加了警告：`rate` 这个字段**官方没有任何定义**（`api.type.Line` 里根本没有），它只存在于聚合表，throughput 是本项目自己的命名。实测 273 条线 Σ(rate × defaultPrice) = 5.5e6，而账本 INCOME 累计 3.24e11 —— 差 5 个数量级 ⇒ **不能当运量用**。
- 规模：268 行 / 27 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `now` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.snapshot` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.company_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.write_api_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.vehicle_write_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.semantic_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `run` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.operations_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.ui_source_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.context_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.dynamic_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.line_raw_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.line_creation_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.route_probe` | 水运 / 航空航路探针（只读）：船和飞机不挂在 BASE_EDGE_* 上，它们的路径 在引擎的 shipMoveSystem / aircraftMoveSystem / runwaySystem / tpNetLinkSystem 里。 航路属于**基础设施**（跑道、泊位、网络链接），一次进程内不变 → 成功后缓 | ↳ 同本文件 | （同上） | （同上） |
| `M.station_struct_probe` | 车站结构探针（只读）：四类站（铁路/汽车/码头/机场）都是"一个 .con + 若干 .module 格子"， 这个探针回答"模块网格能不能从 Lua 读出来"，以及"水运/公路/航空站的 STATION.terminals 是否存在"。 结论一次进程内不变 → 成功后缓存；失败不缓存，下次 get_game_stat | ↳ 同本文件 | （同上） | （同上） |
| `M.economy_probe` | 经济探针（只读）：公司账本（整体收支）+ 每条线的维护费/运价/运量。 用户 2026-09-30 定的运营前提是"城镇发展优先、保证整体盈利"，所以判据的红线在**整体盈亏**； 而账本/维护费在现有产物里都没有，靠这个探针补。同样成功后缓存（一次进程内不变）。 | ↳ 同本文件 | （同上） | （同上） |
| `M.line_finance_probe` | 线路财务探针（只读）：用户 2026-10-02 问「游戏里能单独看每条线的盈亏，引擎给不给 mod 读」。 已排除 system 接口 / Line 组件两条路 / 玩家账本三个方向，只剩 `LOG_BOOK` 组件没验证过 —— 本探针去问它，顺带把 `game.config` 里维护费周期（chargeMaint | ↳ 同本文件 | （同上） | （同上） |
| `M.terminal_waiting_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.api_type_inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.api_command_inventory` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.world_probe` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.station_geometry` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.rail_network` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.set_track_resources` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.operational_telemetry` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.line_demand` | — | ↳ 同本文件 | （同上） | （同上） |
| `M.vehicle_dispatch_state` | — | ↳ 同本文件 | （同上） | （同上） |

#### `tpf2_mod/strings.lua`　

- **干什么**：本地化字符串表（`data()` 返回）
- **依据**：`MD:localizations`｜关系：引用｜置信度：高
- 规模：37 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `data` | — | ↳ 同本文件 | （同上） | （同上） |

### ui/　（19 个文件）

#### `ui/rail-map/app.js`　

- **干什么**：独立版站图应用外壳
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：826 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/bridge-crossings.js`　

- **干什么**：公铁立交图层渲染
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：840 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `publishRailBridgeCrossings` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/dispatch-pages.js`　

- **干什么**：调度页面（含挂钟↔游戏时间换算）
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：游戏内时间与挂钟的比例是**动态的**，用挂钟测时长必须除以实测比例。
- 规模：781 行 / 7 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `table` | — | ↳ 同本文件 | （同上） | （同上） |
| `kpis` | — | ↳ 同本文件 | （同上） | （同上） |
| `clockRateText` | 游戏内时间相对挂钟的速率：低于 1 表示本机仿真跑不满实时， 此时用挂钟测出的时长必须除以 wall_seconds_per_game_second 才是游戏时间。 | ↳ 同本文件 | （同上） | （同上） |
| `toolbar` | — | ↳ 同本文件 | （同上） | （同上） |
| `joinLines` | — | ↳ 同本文件 | （同上） | （同上） |
| `scheduleRefresh` | — | ↳ 同本文件 | （同上） | （同上） |
| `showTimetable` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/freight-flow.js`　

- **干什么**：产业链流向渲染：选中产业 → 画上下游去向线（终点是**车站**）+ 明细浮层；支持**在地图上点产业图标选中**
- **依据**：`GM:industriescargos`｜关系：引用｜置信度：中
- **备注**：边的终点从「城镇」改成「车站」是用户 2026-09-30 定的调。🔴 2026-10-02 加了：监听 `tpf2industry:select`（地图点图标 → 同一条选中路径）+ 面板勾选记忆 + `revealSelected` 把选中行滚进视野。 🔴 2026-10-02：收到 `tpf2industry:select` 后**给一句回执**（写进面板底部提示行），选中不到也把原因写出来 —— 原来只 `console.warn`，用户看不到控制台，等于静默失败，表现就是「点了没反应」。清掉选择时把提示行写回默认文案（`HINT_DEFAULT`）。
- 规模：763 行 / 35 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `boot` | — | ↳ 同本文件 | （同上） | （同上） |
| `optionalJson` | — | ↳ 同本文件 | （同上） | （同上） |
| `reportCoverage` | 自检日志 顺便把"数据到不到位"讲清楚：这份 freight 如果是旧切块（没有 stopovers）， 流向线一条都定位不到终点 —— 与其让用户对着空白地图猜，不如日志里直说。 | ↳ 同本文件 | （同上） | （同上） |
| `buildPanel` | 面板 | ↳ 同本文件 | （同上） | （同上） |
| `onChange` | — | ↳ 同本文件 | （同上） | （同上） |
| `renderList` | 列表项很多（最多 215 个）。只在搜索词 / 选中项变化时重建，不做每帧更新。 | ↳ 同本文件 | （同上） | （同上） |
| `revealSelected` | 在图上点中产业后，把列表里对应的那一行滚进视野 —— 用户本来就说"在列表里根本不知道是哪一个"，点完能看到它在列表的哪儿，比只高亮更有用。 | ↳ 同本文件 | （同上） | （同上） |
| `setHint` | — | ↳ 同本文件 | （同上） | （同上） |
| `selectIndustry` | 选中一个产业 | ↳ 同本文件 | （同上） | （同上） |
| `collectEdges` | 选中产业的边：下游 = 我发出去的货（source_industry 是我）；上游 = 别人发给我的货（target_industry 是我）。 | ↳ 同本文件 | （同上） | （同上） |
| `renderLines` | 流向线 | ↳ 同本文件 | （同上） | （同上） |
| `stationOf` | 终点 = 那批货要下车/装车的车站。 链路：边.stopovers[0] → 用它的 line 找线路 → 用 dest_stop 当下标取 line.stops[dest_stop] → 拿该站 (x,y,z)。 | ↳ 同本文件 | （同上） | （同上） |
| `tierOf` | — | ↳ 同本文件 | （同上） | （同上） |
| `rebuildMarks` | 产业高亮标记（屏幕坐标，每帧重算位置） | ↳ 同本文件 | （同上） | （同上） |
| `addMark` | — | ↳ 同本文件 | （同上） | （同上） |
| `paintMarks` | 每帧只干这一件事：把世界坐标换成屏幕坐标，改写 transform。 标记数量有上限（≤61 个），每帧几十次 setAttribute 无所谓。 | ↳ 同本文件 | （同上） | （同上） |
| `buildDetailPanel` | 明细浮层 绝对定位在 board-wrap 里（那个容器主文件已经设成 position:relative）。 **不动主侧栏**：主侧栏归主文件管，我们从旁边插一块自己的浮层，互不干扰。 | ↳ 同本文件 | （同上） | （同上） |
| `show` | — | ↳ 同本文件 | （同上） | （同上） |
| `hide` | — | ↳ 同本文件 | （同上） | （同上） |
| `setTitle` | — | ↳ 同本文件 | （同上） | （同上） |
| `setInfo` | — | ↳ 同本文件 | （同上） | （同上） |
| `setSummary` | — | ↳ 同本文件 | （同上） | （同上） |
| `setRows` | — | ↳ 同本文件 | （同上） | （同上） |
| `setFoot` | — | ↳ 同本文件 | （同上） | （同上） |
| `renderDetail` | — | ↳ 同本文件 | （同上） | （同上） |
| `total` | — | ↳ 同本文件 | （同上） | （同上） |
| `buildInfoNodes` | 选中一个产业时，先说清"这厂是干什么的"：等级 + 配方（几个什么原料 → 几个什么产品）。 配方来自 industry-recipes.json（tools/extract-industry-recipes.py 从游戏 .con 里抽的）， 按产业**名字**判类型去查 —— 类型表在 industry-kinds | ↳ 同本文件 | （同上） | （同上） |
| `appendCargoChip` | 一个"货种图标 + 数量 + 中文名"的小块。图标是游戏原版的（icons/cargo/）。 | ↳ 同本文件 | （同上） | （同上） |
| `detailRow` | — | ↳ 同本文件 | （同上） | （同上） |
| `el` | 小工具 建 HTML 元素（面板 / 浮层用）。SVG 元素一律走 api.S，不要混。 | ↳ 同本文件 | （同上） | （同上） |
| `rowStyle` | — | ↳ 同本文件 | （同上） | （同上） |
| `cargoName` | — | ↳ 同本文件 | （同上） | （同上） |
| `fmt` | — | ↳ 同本文件 | （同上） | （同上） |
| `gameSpan` | 游戏内秒 → 人看得懂的跨度。**不是现实时间**，所以措辞里点明"游戏"。 | ↳ 同本文件 | （同上） | （同上） |
| `noop` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/industry-icons.js`　

- **干什么**：产业图标层：用游戏原版图标画「原料 → 产品」；**点击图标即选中该产业**（与产业链层用事件广播解耦）
- **依据**：`GM:industriescargos`｜关系：引用｜置信度：中
- **备注**： 🔴🔴 **2026-10-02 点击链路的真根因**：用户反馈「点产业没反应」。原因是主文件在 svg 的 `pointerdown` 里调了 `svg.setPointerCapture()` —— **指针捕获会把随后的 pointerup / mouseup 重定向到捕获元素（svg）**，浏览器据此算出的 `click` 目标是 svg，挂在图标 `<g>` 上的 click 永远收不到。**反证在主文件自己身上**：站点标记的 group 之所以点得动，是因为它挂了一句 `pointerdown → stopPropagation()`，pointerdown 传不到 svg、捕获就不会被设上。本层为了不挡地图拖拽**故意没拦**，正好掉进陷阱。⇒ 改成自己做「按下记候选、松手看位移」：pointerdown 在图标上先触发、pointerup 在 window 的捕获阶段收、位移 ≤5px 才算点击；另留一条 click 兜底，按**手势**去重（不是时间窗口 —— 早先写的时间窗口会把连续两次点击吃掉一次）。 自检：`node _tmpdb/test_industry_pick.js`（假 DOM 把本文件真加载起来，12 项断言）。
- 规模：464 行 / 15 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `kindOf` | — | ↳ 同本文件 | （同上） | （同上） |
| `cargoIconFile` | 货物名（"IRON_ORE"）→ 图标文件（"cargo_iron_ore"）。 游戏这两套命名是对齐的：cargo_types 目录下就是 iron_ore.cargo.lua，图标就是 cargo_iron_ore。 | ↳ 同本文件 | （同上） | （同上） |
| `emitSelect` | 广播「选中这个产业」（`tpf2industry:select`）。所有触发路径都走这里，好在一处统一处理 | `SELF` | 引用 | 高 |
| `boot` | 注册选中链路：window 捕获阶段的 pointerdown 清状态、pointerup 判定是否算点击、pointercancel/blur 清理。**不走 click 主路径**，原因见本文件 note | `SELF` | 引用 | 高 |
| `buildLayer` | 画图标并挂事件：子 `<g>` 自己开 `pointer-events:all`；pointerdown 只记候选、不拦传播（拦了地图就拖不动），点击判定交给 window 上那对 pointerdown/pointerup | `SELF` | 引用 | 高 |
| `widthOf` | — | ↳ 同本文件 | （同上） | （同上） |
| `holder` | — | ↳ 同本文件 | （同上） | （同上） |
| `updatePositions` | ===== 位置：每帧重算 ======================================================= | ↳ 同本文件 | （同上） | （同上） |
| `applyVisibility` | ===== 可见性 =============================================================== | ↳ 同本文件 | （同上） | （同上） |
| `hideAll` | 整层收起 / 展开（缩到全局总览时用）。 ⚠️ 这里必须用 display，绝不能用 visibility。visibility 是**继承**属性， 而 applyVisibility() 会给每个图标显式写 visibility="visible" —— 子元素显式设的值会盖过父元素的 hidden，于是父级那层的 | ↳ 同本文件 | （同上） | （同上） |
| `showAll` | — | ↳ 同本文件 | （同上） | （同上） |
| `buildPanel` | ===== 图层面板 ============================================================= | ↳ 同本文件 | （同上） | （同上） |
| `onChange` | — | ↳ 同本文件 | （同上） | （同上） |
| `makeButton` | — | ↳ 同本文件 | （同上） | （同上） |
| `setBoxes` | ⚠️ 这两个按钮**不再直接改 state**：改成拨一下勾选框 + 派发 change 事件， 让面板统一的那条路（写记忆 → 应用）跑一遍。 直接改 state 会出现两种错位：① 界面显示"没勾"、其实生效了； ② 勾选状态记不下来（2026-10-02 加了勾选记忆之后，这一条才成问题）。 | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/industry-kinds.js`　

- **干什么**：产业类型表（从产业名字反推类别），供图标层与流向层共用
- **依据**：`GM:industriescargos`｜关系：引用｜置信度：中
- 规模：59 行 / 2 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `of` | — | ↳ 同本文件 | （同上） | （同上） |
| `byKey` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/network-app.js`　

- **干什么**：铁路图主渲染（**上游作者的核心文件**，2286 行）：地图、图层、站台线、站点标记、侧栏
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：原作者画站台用的是 `platform_centerline`（引擎给的站台真实中心线）+ 6 px 粗线。**我们后加的图层必须沿用这套写法**，另造一套会和它互相压（2026-10-02 的教训）。🔴 `addOption` 现在接**勾选记忆**（键＝面板显式分组名/条目名）；「重置勾选」按钮走 ui-persist.js；动作按钮（只看客运/还原）绕过了 change 事件，靠 `persistAllBoxes` 补写。 🔴 2026-10-02 新增「面板可调」（用户：「侧边栏过宽，加一个可以拖动和收起的功能」）：`#layer-panel` 改成三层（`.layer-panel-head` 标题条 ＋ `.layer-panel-body` 内容区 ＋ `.layer-panel-resizer` 右缘把手），宽度写 `--layer-panel-w`、位置写 left/top，都记 localStorage（`tpf2map.layerPanel.*`）；标题条可拖动搬走、双击复位，折叠按钮收起。右侧栏同样可拖（把手 `.sidebar-resizer` 是 `.workspace` 的子元素，**不是** aside 的 —— aside 是 `overflow:auto` 的滚动容器，把手放进去会跟着内容滚），宽度写 `--sidebar-w`。两处共用 `installColResize()`：**拖动期间必须 setPointerCapture**，否则指针一离开把手就被地图 svg 的 pointermove 抢走。本文件整体是一个巨型 `renderRailNetwork()`，所以函数抽取只认得出它。
- 规模：2490 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `renderRailNetwork` | 全网图的全部初始化与渲染。含 2026-10-02 新增的 `uiPref` / `clampNumber` / `installColResize` / `applySidebarWidth` / 图层面板骨架与拖拽 | `SELF` | — | 高 |

#### `ui/rail-map/network-page.js`　

- **干什么**：网络图页面装配
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：84 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/rail-graph.js`　

- **干什么**：铁路图数据装配
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：128 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/rail-network-data.js`　

- **干什么**：**生成物**：由 `tools/export-rail-network-map.py` 写出的数据壳
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：2 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/rail-network-manifest.js`　

- **干什么**：**生成物**：铁路图数据清单
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：2 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/road-congestion.js`　

- **干什么**：路况色带图层：按聚合速度给路段涂绿/黄/橙/红，放大才显示
- **依据**：`GM:statisticsdatalayers`、`MD:baseconfig`｜关系：复刻｜置信度：高
- **备注**：配色与语义对齐游戏自带的 **Street Traffic** 图层（官方 `gui.layers.streetTraffic` 三色在 base_config 里，见 MD:baseconfig / DG:09）。
- 规模：336 行 / 15 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `byId` | — | ↳ 同本文件 | （同上） | （同上） |
| `text` | — | ↳ 同本文件 | （同上） | （同上） |
| `hint` | — | ↳ 同本文件 | （同上） | （同上） |
| `fetchJson` | ===== 数据 ===== | ↳ 同本文件 | （同上） | （同上） |
| `buildPaths` | 把「每段一条曲线」合并成「每等级一条 path」，对齐游戏自带 Street Traffic 图层的表达 | `GM:statisticsdatalayers` | 复刻 | 高 |
| `render` | — | ↳ 同本文件 | （同上） | （同上） |
| `ensureRendered` | 只在"开着 + 数据齐"时才真的去拼路径（默认关着，不该让人白等一次渲染） | ↳ 同本文件 | （同上） | （同上） |
| `applyZoom` | 只有一条按缩放走的显示规则（放大才显示，对应官方图层的行为） | `GM:statisticsdatalayers` | 复刻 | 中 |
| `buildPanel` | ===== 面板 ===== | ↳ 同本文件 | （同上） | （同上） |
| `onChange` | — | ↳ 同本文件 | （同上） | （同上） |
| `loadGeometry` | ===== 载入 ===== | ↳ 同本文件 | （同上） | （同上） |
| `stampOf` | — | ↳ 同本文件 | （同上） | （同上） |
| `loadTraffic` | — | ↳ 同本文件 | （同上） | （同上） |
| `schedule` | — | ↳ 同本文件 | （同上） | （同上） |
| `start` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/station-struct.js`　

- **干什么**：车站结构渲染：站台客/货分色、站房按真实尺寸画、**出入口按进/出/双向分色并画道路式箭头**；火车站只补站房（站台/轨道归原作者那层），水/路/空三类站画整座站场
- **依据**：`MD:modularconstructions`、`PN`｜关系：复刻｜置信度：高
- **备注**：站台/轨道的**画法**沿用原作者那层，不重复画（重复画会两套线互压）。另外三类站作者那层没有数据（station-previews 只覆盖铁路），所以整座站场自己画。 🔴 **2026-10-02 栽过一个作用域坑**：`arrowPath` 是模块级函数，却在里面裸用了 `map`（`const map = state.map` 只在 `buildShapes` 内）⇒ 第一个出入口格抛 `ReferenceError`，异常穿透 `list.forEach` 把整个站点循环打断。JSON 里铁路站在前 ⇒ 现象是「铁路有结构、码头/汽车站/机场完全没有」。修法：`map` 当参数传；并给每个站加了 try/catch ——**一个站画挂了不该把整层拖没**。
- 规模：753 行 / 21 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `arrowPath` | 出入口的方向箭头轮廓（进/出单头、双向双头）。🔴 **`map` 必须当参数传进来** —— 模块级作用域没有它 | `SELF` | 复刻 | 高 |
| `typeOf` | 站类型判据：只看 construction 文件（铁路/道路/水运/航空） | `MD:modularconstructions` | 复刻 | 高 |
| `capacityOf` | 容量按服务的 cargo 真假分开累加（对应引擎的 `Station.pool.moreCapacity`） | `PN` | 应用 | 高 |
| `isUnderground` | 地下站判据（阈值 3 m，**按全量数据跑出来 484/565，明显把嵌进地形的普通站台也算进来了** ⇒ 数值不太可信） | `SELF` | 复刻 | 低 |
| `radiusOf` | 按容量分四档定标记大小（0 单独一档） | `SELF` | 复刻 | 高 |
| `start` | — | ↳ 同本文件 | （同上） | （同上） |
| `loadStations` | 车站结构数据是 network-app.js 自己异步拉的，刚就绪时 stationData() 还是 null， 而且它拉完不会广播任何事件，只能自己等。 用**有次数上限**的 setTimeout 递进重试：只解决"数据到没到"，跟重绘没关系 —— 重绘一律走 onViewport（见 updatePositio | ↳ 同本文件 | （同上） | （同上） |
| `build` | ===== 建图层 ============================================================== | ↳ 同本文件 | （同上） | （同上） |
| `makeMarker` | — | ↳ 同本文件 | （同上） | （同上） |
| `loadShapes` | 载入 `layers/station-structures.json`（真实占地的世界坐标多边形） | `MD:modularconstructions` | 复刻 | 高 |
| `buildShapes` | 画格子：火车站只画站房（暖白/砖红），其余三类站画全部格子。**每个站包在 try/catch 里**，坏站只坏它自己 | `MD:modularconstructions`、`SRC`、`PN` | 复刻 | 高 |
| `updatePositions` | 每帧重算屏幕坐标 —— 唯一的重绘入口，由 TPF2Map.onViewport 驱动。 | ↳ 同本文件 | （同上） | （同上） |
| `applyVisibility` | — | ↳ 同本文件 | （同上） | （同上） |
| `buildPanel` | ===== 图层面板 ============================================================ | ↳ 同本文件 | （同上） | （同上） |
| `onChange` | — | ↳ 同本文件 | （同上） | （同上） |
| `ensureDetailPanel` | ===== 详情浮层 ============================================================ 自己做一个浮层贴在 board-wrap 里（主侧栏归主文件管，不去动它，免得两边打架）。 样式全部内联：network.css 是主文件的地盘，一行都不改。 | ↳ 同本文件 | （同上） | （同上） |
| `closeDetail` | — | ↳ 同本文件 | （同上） | （同上） |
| `openDetail` | — | ↳ 同本文件 | （同上） | （同上） |
| `row` | — | ↳ 同本文件 | （同上） | （同上） |
| `sectionTitle` | — | ↳ 同本文件 | （同上） | （同上） |
| `hint` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/template-runtime.js`　

- **干什么**：HTML 模板运行时
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：49 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/terrain-contour.js`　

- **干什么**：等高线生成（Marching squares），纯计算不碰 DOM
- **依据**：`GM:statisticsdatalayers`｜关系：复刻｜置信度：中
- **备注**：对齐游戏自带的 **Contour Lines** 数据图层（DG:06 列了官方 9 个数据图层的语义）。
- 规模：112 行 / 1 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `buildContours` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/timetable-page.js`　

- **干什么**：时刻表页面入口
- **依据**：`SELF`｜关系：—｜置信度：高
- 规模：4 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/timetable.js`　

- **干什么**：时刻表页面逻辑
- **依据**：`GM:linesvehicles`｜关系：应用｜置信度：中
- 规模：263 行 / 0 个函数 ｜ **已登记**

#### `ui/rail-map/town-layer.js`　

- **干什么**：城镇图层：27 个城镇的名字 + 「它要什么货」
- **依据**：`GM:towns`｜关系：引用｜置信度：高
- **备注**：`needs` 三元素按官方语义依次是 **住宅 / 商业 / 工业** 三个区（GM:towns 的 land use 与需求规则）。
- 规模：216 行 / 9 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `boot` | — | ↳ 同本文件 | （同上） | （同上） |
| `getJson` | — | ↳ 同本文件 | （同上） | （同上） |
| `build` | ===== 建图层 ============================================================== | ↳ 同本文件 | （同上） | （同上） |
| `drawTown` | — | ↳ 同本文件 | （同上） | （同上） |
| `updatePositions` | ===== 每帧定位 ============================================================ 唯一的重绘入口，由 TPF2Map.onViewport 驱动。**别**用 rAF / setInterval —— 那样会跟地图的绘制节奏错开一帧，拖动时标签会滞后。 | ↳ 同本文件 | （同上） | （同上） |
| `applyVisibility` | ===== 显隐 ================================================================ 🔴 整层收起来必须用 display。visibility 是**继承**属性，子元素只要显式设了 visible 就会盖过父元素的 hidden —— 父级那层等于没藏住 | ↳ 同本文件 | （同上） | （同上） |
| `applyNeeds` | — | ↳ 同本文件 | （同上） | （同上） |
| `buildPanel` | ===== 图层面板 ============================================================ | ↳ 同本文件 | （同上） | （同上） |
| `onChange` | — | ↳ 同本文件 | （同上） | （同上） |

#### `ui/rail-map/ui-persist.js`　

- **干什么**：面板勾选项的本地记忆（localStorage）：把每个勾选框的状态记下来，下次打开还是上次那样；reset() 清空并刷新
- **依据**：`SELF`｜关系：—｜置信度：高
- **备注**：用户 2026-10-02 要求「做个机制记住我勾选了啥，除非手动重置」。键规则是 `tpf2map.ui.<分组名>/<条目名>` —— **改面板文案等于换键**（旧值被忽略、退回默认），这是故意的。只记勾选状态，不碰任何游戏数据。
- 规模：122 行 / 9 个函数 ｜ **已登记**

| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |
|---|---|---|---|---|
| `flush` | 按登记顺序跑攒下的恢复动作；某个抛错不拖累后面的 | `SELF` | — | 高 |
| `parse` | — | ↳ 同本文件 | （同上） | （同上） |
| `key` | 分组名 + 条目名 → 存储键 | `SELF` | — | 高 |
| `get` | 读；没存过返回 fallback（**不写入**，所以「没动过」和「存了默认值」分得开） | `SELF` | — | 高 |
| `set` | 写；存不下（隐私模式）静默退化成不记忆 | `SELF` | — | 高 |
| `has` | 这个键存过没有 | `SELF` | — | 高 |
| `defer` | 攒一个「等面板全建完再应用」的动作 —— 立刻应用会踩到「别处还没初始化」 | `SELF` | — | 高 |
| `reset` | 清掉所有 `tpf2map.ui.*` 并刷新页面（选刷新而不是就地改回：有的项要等数据到齐，就地恢复会漏） | `SELF` | — | 高 |
| `dump` | 诊断用：列出当前存了哪些键（控制台 `__uiState.dump()`） | `SELF` | — | 中 |

