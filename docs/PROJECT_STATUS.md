# TPF2Mcp 项目状态与需求总表

> **这是本项目唯一的现状入口。** 新会话先读这一页，再去读具体报告。
> 最后更新：2026-09-30 23:20 ｜ 维护约定：每次实质改动后，更新「二、需求清单」的状态列与「三、开发进度」两节。

---

## ⓪、阶段定位（**先看这条，它决定优先级**）

🔴 **当前阶段 = mod 开发（尚未结束）。游戏内运营还没开始。**

- **存档只是"测试数据"** —— 拿它验证 mod 的功能：采集器读不读得到字段、图层数据对不对、
  前端画得对不对、探针能不能打通。**它不是一个"运营优化项目"的现场。**
- 所以**需求以 mod 能力为主**：数据能不能采、能不能画、能不能算、工具好不好用。
  真正的运营动作（哪条线加车、哪里铺轨、哪个厂该建线）属于**后续阶段**，现在不拍。
- **09-27 那 12 篇运营分析是当时方向下的探索**，价值在**口径与实测方法**
  （客货判据分开、时间基准换算、站台容量算法、堵车归因），**不在"照着执行"**。
  到运营阶段时数据要重新取（余额等已经漂移）。
- 因此：**遇到"要不要改游戏状态"的岔路口，默认答案是"不改"** —— 先把"能看见、能算准"做扎实。

---

## 〇、这个仓库里的文档怎么分工（先搞清这个，不然会串台）

| 位置 | 份数 | 谁写的 | 性质 | 怎么用 |
|---|---|---|---|---|
| `agents/` | 24 份 / 33,199 行 | **上游作者** | Phase 1→20 开发计划 + 各阶段验收、最终目标需求、实施计划 | **只作参考**。是原作者在**他自己的机器/存档**上的工作笔记，里面的路径与存档都不是本机的 |
| `docs/`（英文那批） | 35 份 / 1,083 行 | **上游作者** | 架构、bridge、快照 schema v2–v5、UI 取数追踪、各阶段验收 | **只作参考**（时效不明，部分结论可能已不准） |
| `reports/` | 33 份 / 5,930 行 | **我们** | 运营/技术分析报告 + 交接 1–5 | 现行。**我们的进度原先只写在交接 N 里，现改由本页汇总** |
| 根目录 | 3 份 | **上游** | `AGENTS.md`（打包与路径规约）、`README.md`（项目简介）、`ui/rail-map/README.md` | `AGENTS.md` 是硬规约，要遵守；README 是上游的宣传文案 |
| **本页** | 1 份 | 我们 | 需求 + 进度 + 文档地图 | **入口** |

⚠️ **两套"进度"不要混**：`agents/` 里的 Phase 1→20 是**上游的**进度（止于 Phase 20 车辆生命周期）；
**我们的进展在「四、开发进度」**（fork 分支 `feature/multi-layer-map`）。

---

## 一、当前底数与分工（一句话）

- **当前存档**（2026-09-30）：**27 城镇 / 215 产业 / 565 车站 / 273 线路 / 1,370 车辆 / 余额 1,209 亿、无贷款**。
  🔴 **它就是 `交接_2` 讲的那个档**（数字逐个一致，余额从 1136 亿涨到 1209 亿；档里有 `京广客运`/`JY客运`/`JI线路`）。
  ⚠️ 但**它是拿来验证 mod 功能的测试数据** —— 09-27 那批运营探索（京广、JY、走廊、客流）
  的价值在**口径与实测方法**，不是待执行的运营清单（**运营尚未开始**，见 §⓪）。
- **另一个档（09-28，16 城镇 / 140 线路 / 664 车 / 余额 362 亿）当前没在用** —— 只有 `交接_1` 讲它。
- **分工**：用户 = 拍板 + **游戏内施工**；AI = 摸底数 · 算方案 · 出施工单 + 施工后验收。
- **授权**：改游戏状态前必须报备 → 用户审核 → 才动手。分级 L0 只读 / L1 只读探针 / L2 官方接口常规操作（改线路·加车·调速度）/ ★L3 绕过游戏接口改数据文件（**不碰**）。
  ⚠️ **L2 的写操作依赖 DLL 注入通道**（上游声明：远程线程注入 `tpf2_control.dll` 到游戏进程）—— **只读不依赖**。
  当前 `allow_write_operations=false`、本机未装该 DLL，写通道**尚未启用**（开发阶段以只读为主）。
- **运营战略前提**：**城镇发展优先，保证整体盈利**。客运线亏损**不算病灶**（亏损不是关停/减车的依据）；唯一红线是**整体盈利**。

---

## 二、需求清单（按阶段分）

状态图例：✅ 已生效（游戏里跑过）｜🟡 已写好、**未部署**（等一次 bat + 重启）｜🔧 做了一部分｜❌ 未做｜🗄 已归档

### 2.1 当前阶段：mod 开发（**主线在这一节**）

| # | 需求 | 状态 | 落地物 / 出处 |
|---|---|---|---|
| R1 | 在原 mod 基础上做**多图层地图**（公路/产业/车辆/线路/车站/城镇） | ✅ | `layer-*.json` 8 层 + `ui/rail-map/` 各图层文件 |
| R2 | 线路用**游戏里的真实颜色**，不要自造 | ✅ | `layer_lines.lua` 的 `color` 字段 |
| R3 | **产业链**：选中产业 → 高亮上下游 + 流向线**落到具体车站** + 明细 | ✅ | `freight-flow.js`、`layer-freight.json`（4,312 条边带 `stopovers`） |
| R4 | 产业的**形状**（按厂区实际占地画，不是小方块） | ✅ | `extent` 字段 + `network-app.js` 范围框 |
| R5 | 产业的**图标**（用游戏原版）+ **配方**「原料 ＋ 原料 → 产品」 | ✅ | `industry-icons.js`、`industry-recipes.json`、`icons/cargo/*.png`（16 个，手写 TGA 解码提取） |
| R6 | **城镇需求**（城名 + 它要什么货） | ✅ | **2026-10-02 核实已生效**：`bridge/layer-town.json` 27 个城镇全带 `x/y/z` + `needs`（三区需求）；前端 `town-layer.js` |
| R7 | 车站的**真实结构**（模块格子级：站台/站房，不是外围大框） | ✅ | **2026-10-02 核实已生效**，且已扩到**四类站**（见 R21）：286 座 / 5492 格，自检 286/286 |
| R8 | 车站容量显示 + **超容报警** | 🔧 | 容量已生效；**候车量仍缺**（报警缺一半依据） |
| R9 | 工厂/线路**诊断能力**：缺货还是满足、要不要**新建线路或加车**（客货分别） | ✅ | **2026-10-02 重写**。判据＝**堆压月数**（出货侧 waiting ÷ 年产量上限）→ 六档，**215 家全覆盖**：停摆 1 / 无流量 75 / 没人运 7 / 运力不足 52 / 偏紧 38 / 正常 42。旧「供应比」**已删**（实测 `count` 是当前快照量而非累计量，两个快照相除无意义）。⚠️ 只覆盖**产出侧**；「进料够不够」仍缺数据（见 O1） |
| R10 | 经济数据能力：**整体盈利**、每条线的开销与运价 | 🔧 | 采集 ✅：`bridge/economy-probe.json` 有公司账本（按 type / carrier / maintenance 聚合）＋ 273 条线的维护费 / 运价 / 车辆数 / 货运数。**线路级盈亏：引擎不给原值** —— 2026-10-02 查穿三条路（31 个 system 无财务接口／`Line` 组件两条读取路都没有钱／玩家账本 5 万条无线路引用），只剩 `LOG_BOOK` 组件未验证 ⇒ 已写只读探针 `line_finance_probe.lua`（**待部署 + 重启游戏**）。**分析脚本 ❌ 未写**（`tools/` 里没有任何 econ / finance 脚本） |
| R11 | **实时的原料数量**（要能分货种） | 🔧 | **总量 ✅**（`layer_industry.json` 的 `stock_count` 已生效）；**分货种 ❌**：现在只数总件数，没按货种拆 —— 官方接口是 `simEntityAtStockSystem.getStockCount(stockEntity, stockId)`，要补采集 |
| R12 | **道路交通**：公路上所有玩家与 NPC 载具的数据 + **寻路逻辑** | 🔧 | 载具数据 ✅（`layer_road_traffic.lua`，10,658 辆全定位）；**寻路逻辑 ❌ 未做** —— 全项目搜不到 `pathfinding` / `findPath`（官方接口是 `util.pathfinding.findPath(…, CAR)`） |
| R13 | **道路拥堵图层**：像高德那样（色带 / 5 分钟刷新 / 放大才显示 / 可开关 / 静态 / **不画车**） | ✅ | **2026-10-02 核实已生效**：`bridge/layer-road-traffic.json` 今日跑过 —— **10,658 辆路车全部定位**、4,101 路段、报警 115 / 警告 216；前端 `road-congestion.js` |
| R14 | **「局部」页 → 改造成「枢纽」页**（2026-10-03 用户定调：「我要的是枢纽，不是站群」） | 🔧 | **第一刀已下**：`app.js` 的站场几何（`station-previews/station-<id>.json`）从**必需降级为可选** —— 它只覆盖 **73 / 565** 座站、09-29 生成后再没更新，且带 `save_id` 校验；旧代码在这两处都 **`throw`** ⇒ 整个页面挂掉、**后面的枢纽逻辑一行都执行不到**（**这就是「关联车站做了半天没做出来」的根因**）。同时：按钮「局部」→「枢纽」、车站侧边栏加「**查看整个枢纽**」入口（原来只能双击地图，没有任何可见入口）。**剩余**：枢纽页的侧边栏仍是「单站」结构，要改成**枢纽总览 + 成员站按四类模式分组** |
| R15 | 机场吞吐分析 | 🔧 | 分步来；结构解析已完成（交接 4 附篇） |
| R17 | **授权分级**：改游戏状态前必须报备 → 审核 → 才动（工作方式） | ✅ | 记忆 `MEMORY.md`（L0–L3） |
| R19 | 项目要有**单一入口文档**（需求 + 进度） | ✅ | 本页 `docs/PROJECT_STATUS.md`（2026-09-30 建） |
| R20 | **代码 ↔ 官方 wiki 索引**：每份源码落到官方出处；新代码必须登记 | ✅ | `docs/CODE_WIKI_INDEX.md`（自动生成）＋ 映射表 `docs/code-wiki-map.json` ＋ 校验器 `0_core_shared/index/build-code-wiki-index.py`。规则已写进 `AGENTS.md` |
| R21 | 三类站结构（**码头 / 汽车站 / 机场**）按真实占地画出 | ✅ | `build-station-structures.py` 已接入三类站反解；**286 座站 / 5492 格**，自检 286/286 落在引擎占地框内。前端 `station-struct.js` 对这三类**画整座站场**（火车站仍只补站房） |
| R22 | 出入口要分**进 / 出 / 双向**，并用**道路式箭头**画出行人方向 | ✅ | 判据＝模块名（`entrance` / `exit` / `entrance_exit`）；生成端输出 `cell.dir` + `cell.arrow`（世界坐标方向）。前端与核对报告都画箭头。⚠️ **箭头的指向是从 `.con` 的 y 分支推的，属推断**，不是游戏现成字段 |
| R23 | 产业要能**在地图上直接点选**（不在左侧列表里找）+ **记住勾选状态**，除非手动重置 | ✅ | 点图标选中：`industry-icons.js` 挂点击 → 广播 `tpf2industry:select` → `freight-flow.js` 走同一条选中路径（并把列表里那行滚进视野）。勾选记忆：`ui-persist.js`（localStorage，键＝面板分组名/条目名），`addOption` 自动接入；**「重置勾选」按钮**在图层面板动作条里 |
| R24 | 广州北站房位置不对 | ✅ | 站房 x 公式照抄 `.con` 的 `pos`：回侧 `minS[j]*5 − 10`、前侧 `maxS[j]*5 + 10`，而 `minS[j]`/`maxS[j]` **就是槽位 ID 里编码的 `i`** ⇒ 直接用解出的 i，不再去找「站场最外一列」。旧写法把 `−10`（`mainBuildingPosition`）当了两次外移、且用了全局列范围 ⇒ 整栋偏 7.5 m 起、列号大时偏上百米。顺带修：从属楼（o=5）走 `.con` 的 `tf1`，y 比主楼**高 5 m** |
| R25 | 码头 / 汽车站 / 机场**硬刷新也不出现结构** | ✅ | 根因＝`station-struct.js` 的 `arrowPath()` 是模块级函数却裸用了 `map`（`const map = state.map` 只在 `buildShapes` 内）⇒ 第一个出入口格抛 `ReferenceError`，异常穿透 `list.forEach` 把整层打断；JSON 里铁路站在前 ⇒ **铁路画完、三类新站一个没画**。修：`map` 当参数传 ＋ **每个站包 try/catch**（坏站只坏它自己）。另修 `serve-rail-map.py`：静态缓存 `no-store` 从「按文件名列举」改成**按后缀**，新增前端文件不再漏（⚠️ 需重启地图服务生效） |
| R26 | **枢纽监控**：铁路 / 公交 / 水运 / 航空**四类一起**看（容量 vs 占用 ＋ 超容报警） | ⏳ | 用户 2026-10-03：「**运营枢纽是很重要的一环，不仅是铁路，公交站，码头和机场也是如此**」。**骨架已有**：`layer-stations.json` 的 `clusters`（**170 个枢纽**，用的是引擎「乘客能在辐射区重叠的车站之间换乘」的权威定义，**不是按距离猜**）＋ 四类判据（`station-struct.js:146`）＋ `capacity_passenger` / `capacity_cargo`。**唯一缺口 = 当前候车 / 占用**，卡在 `terminal_waiting_probe` 的验证（有崩溃前科，探针已写得极度克制） |
| R26 | **侧边栏过宽**：要能拖动改宽、能收起 | ✅ | `#layer-panel` 改成「标题条 ＋ 内容区 ＋ 右缘把手」三层：拖右缘改宽、拖标题条搬位置（双击复位）、按钮收起；宽度/位置/收起状态都记 localStorage。右侧栏同样可拖（把手 `.sidebar-resizer` 是 `.workspace` 的子元素，**不是** aside 的 —— aside 是滚动容器，把手放进去会跟内容滚）。两处共用 `installColResize()`，拖动期间 `setPointerCapture`（否则指针一离开把手就被地图 svg 抢走） |
| R27 | 产业**点击没反应** | ✅ | 根因＝主文件在 svg 的 `pointerdown` 里调 `setPointerCapture()`，**指针捕获把随后的 pointerup/mouseup 重定向到 svg** ⇒ 浏览器算出的 `click` 目标是 svg，挂在图标 `<g>` 上的 click 永远收不到。**反证**：站点标记点得动，是因为它 `pointerdown → stopPropagation()`（pointerdown 传不到 svg、捕获就不会被设上）；本层为不挡地图拖拽故意没拦，正好掉进陷阱。修：自建「按下记候选、松手看位移 ≤5px」，另留 click 兜底按**手势**去重。自检 `node _tmpdb/test_industry_pick.js`（12 项断言） |
| R28 | 产业的**等级** ＋ **每个等级对应的最大产量** | ✅ | 等级本就在采（`SimBuilding.level`，实测 0..3）；**每级最大产量 2026-10-02 算出**：`capacity × 产出量 × 等级`。依据：官方 `modding/constructiontypes.md`「#### Rules」——「每年能跑多少次这条规则由 `capacity` 限制」；游戏 `res/scripts/industryutil.lua` ——`capacity = … * currentLevel`。16 类全出：原料类 **1 级**（煤/铁/油/林/石 400、农田 200）／锯木·钢铁·炼油 **2 级**（200·400）／化工·建材·食品·燃料·加工·机械·工具 **4 级**（100·200·300·400）。产物：`industry-recipes.json` 的 `levels` / `max_per_level` |
| R29 | **数据资产总账 + 交叉索引**：一张「我手上到底有什么」的账，四维互通（引擎接口／代码／官方文档／产物字段），并附「我想要 → 现成接口」对照表 | ✅ | `docs/DATA_INVENTORY.md`（自动生成）＋ `0_core_shared/index/build-data-inventory.py`。首次跑出来：31 个 system / **116 个方法**，项目只用了 **28 个** ⇒ **88 个现成方法没用过**；其中 `getVehicle2Cargo2SimEntitesMap`（每辆车装了什么）、`simPersonAtTerminalSystem.getNumFreePlaces`（车站候车/剩余容量，R8 卡了很久）、`lineSystem.getProblemLines`（有问题的线路）都是「想要却以为没有」的。🔴 规矩：**写新采集/新探针之前，先查这份总账第零节** |
| R30 | **客流改为自动采集**（用户 2026-10-03 指出「采集客流不应该是自动的吗」） | 🟡 **已写好、待部署** | 原状况：客流只有两条路 —— MCP 工具 `get_line_demand`（一次一条线）＋ 手动脚本 `collect-line-demand.py`，后者走的正是 `layer_registry` 点名要淘汰的「Python 主动发命令」模式（bridge 单槽邮箱争锁的根源）。**已新增流式图层 `collectors/layer_passenger.lua`**：遍历玩家全部线路，用 `line_demand` 同一套取数逻辑采每线的乘客/货物统计（等候/车上/中位等待/OD 明细），写 `bridge/layer-passenger.json`，登记进 `layer_registry`（`every=12000 delay=340`）。**零新增引擎接口**（复用 `lineSystem.getLines`）。⚠️ 待部署 + 重启游戏验证 —— 重点看**分帧够不够**（273 条线 × 每线遍历全部乘客实体，`BATCH=4` 是保守取值） |

> 另有一条**战略前提**（不是任务，是所有诊断的约束），放在 §一：**城镇发展优先、保证整体盈利；
> 客运线亏损不算病灶**。

### 2.2 后续阶段：游戏内运营（**尚未开始**）

用户已明确：**存档只是测试数据，游戏内运营还没开始。** 下面列的是已知方向，
**等 2.1 的能力齐了再启动；现在不出方案、不动游戏。**

| # | 方向 | 状态 | 前置 |
|---|---|---|---|
| O1 | 产线诊断：哪家缺货、要不要新建线路或加车 | 🔧 一半 | **产出侧已做**（`diagnose-industries.py` 重写，2026-10-02，见 R9）；**进料侧（缺料判定）卡在数据**：官方 `SimBuilding` 不给产量三指标，可用的是 `simEntityAtStockSystem.getStockCount`（**按货种**库存）等四个接口 —— 我们现在只采了总件数、没按货种拆，且进料 link 只有 58/215 家有 ⇒ 需先补采集（改 Lua → 重启游戏） |
| O2 | 财务体检：整体盈利红绿灯 + 每条线亏盈 | ❌ 未开始 | R10 |
| O3 | 道路交通治理：堵点定位 + 公交分流 | ❌ 未开始 | R12 / R13 |
| O4 | 客运服务品质复核（实载/候车/等待中位） | ❌ 未开始 | 候车量（R8 的另一半） |
| O5 | 铁路拥堵治理（哪段该铺轨/加车） | ❌ 未开始 | 诊断流程已具备，但**运营阶段才动** |

### 2.3 已归档

| # | 事项 | 状态 | 备注 |
|---|---|---|---|
| R18 | 京广标杆车 16 节重联不拆 + 单独提速 | 🗄 | 改了 mod 3374213837 的 `TC/MP/04_T.mdl` / `05_T.mdl`（**L3 高危**）；备份与回滚脚本在，**从未实测** |

---

## 三、开发进度

### 3.1 已生效（游戏里跑过，产物在）

| 东西 | 证据 |
|---|---|
| 8 个图层自动采集 | `bridge/layer-*.json`：vehicles 21:28 / freight 21:26 / town 21:26 / lines 21:25 / road 21:25 / stations 21:25 / industry 20:55 / terrain 20:18 |
| 产业链流向数据 | `layer-freight.json`：4,312 条边带 `stopovers` |
| 线路站点序列 | `layer-lines.json`：271 条线全带 `stops[]`（真实下标 + 车站 id） |
| 产业占地与库存指针 | `layer-industry.json`：215 个点带 `extent` |
| 车站结构探针 | `station-struct-probe.json`：333 座（轨 78 / 水 46 / 路 195 / 空 14） |
| 前端图层（强刷即生效） | `freight-flow.js`、`station-struct.js`、`industry-icons.js`、`industry-kinds.js`、`town-layer.js`、`road-congestion.js` |
| 离线产物 | `icons/cargo/*.png`(16)、`icons/industry/*.png`(16)、`industry-recipes.json`、`cargo-types.json`、`layers/station-structures.json`(333)、`layers/road-edge-geometry.json`(9,960 条 / 671 KB) |
| 工具 | `extract-industry-icons.py`、`extract-industry-recipes.py`、`build-cargo-types.py`、`build-station-structures.py`、`build-road-geometry.py`、`diagnose-industries.py` |

### 3.2 部署状态（**2026-10-02 逐文件 md5 核实**）

**结论：§3.2 原先列的"未部署"已经全部落地**，不要再按"待部署"理解。

| 项 | 核实结果 |
|---|---|
| `tpf2_mod/res/**`（全部 Lua，含 40 个采集器） | **54/55 与 staging 一致** ✔ |
| `mcp_server/**`（52 个 Python） | 一致 ✔ |
| 8 个图层产物 | `bridge/layer-*.json` **全部是今天的时间戳**（freight / industry / lines / **road-traffic** / road / stations / terrain / town / vehicles） |
| `station-struct-probe.json` | 已在（Sep 30 跑过），前端结构数据今天重生成过 |
| `economy-probe.json` | 已在（Sep 30 产出，成功即缓存） |
| **唯一没同步的** | `3_dashboard_ui/server/serve-rail-map.py`（缓存头按后缀那个改动）—— 服务跑的是 staging 那份，**要跑 `deploy_mod_layers.bat`** |

> ⚠️ 部署路径要点（2026-10-02 实测钉死）：桌面「TPF2 铁路图」→ `rail-map-service.pyw`
> → `<staging>/mcp_server/start_ui.py` → `UI_SERVER = <staging>/3_dashboard_ui/server/serve-rail-map.py`；
> 而**前端 `ui/rail-map/` 读的是项目目录** ⇒ 改前端不用部署，但必须提 `index.html` 的 `?v=`。

### 3.3 未做 / 待办（**2026-10-02 逐条核实**）

**卡在数据采集（要改 Lua → 完整重启游戏）：**

| 待办 | 卡在哪 |
|---|---|
| **原料数量分货种**（R11 的后半） | 现在只数总件数；官方接口 `simEntityAtStockSystem.getStockCount(stockEntity, stockId)` 可按货种读，要补采集 |
| **进料侧缺料判定**（O1 的后半） | 进料 link 只有 58/215 家有记录；补「按货种库存 + 等待时长 + 来源厂」 |

**没写代码（不依赖采集）：**

| 待办 | 卡在哪 |
|---|---|
| 经济**分析脚本**（R10 后半） | `economy-probe.json` 有了，但没有分析脚本 |
| **线路级盈亏** | 引擎账本（`Account.journal`）里没有线路字段；只能维护费 + 运价 + 运量侧路估算 |
| **公路寻路逻辑**（R12 后半） | 全项目搜不到 `pathfinding` / `findPath` |
| 局部视图复用全网渲染（R14） | 未开工 |
| 小机场 `airfield.con` 结构 | 公式未实测（四类站已接入，只有小机场没验） |

**等用户决定 / 等动作：**

| 事项 | 现状 |
|---|---|
| **`tpf2_control.dll`** | 来源未知 ⇒ `docs/AI_DEPLOY_GUIDE.md` 里写通道那节还不完整 |
| `ust` / `mus` 站型结构 | 各 2 / 1 座，**保留待做**（用户 2026-10-02 定），属独立任务 |

### 3.3.1 本轮（2026-10-04）已闭环的两条

| 原待办 | 结论 |
|---|---|
| **车站候车量**（超容报警的另一半依据） | ✅ **数据侧打通**。不必解 `getPersonNodeId2StationTerminalsMap` 的 key：`layer-passenger.lua` 的 `by_journey[]` 带 `line_stop_0`（上车站序），按它聚合 `waiting`、再用 `layer-lines.json` 的 `stops[].index → group_id` 翻车站 id ⇒ **每站候车 + 每站候运**。实测停站→车站命中 321 / 落空 0 |
| **站台容量**（超容判据的分母） | ✅ **口径定死**：引擎没有容量接口，但 `terminal.personEdges` 每条边有 `getNumFreePlaces(edgeId)`，**站台容量 = Σ 该站台每条候车边的剩余位置**。实测广州北站站台 1 的 Σ = **476**，与游戏 UI「0/476」精确吻合。⚠️ 车站 `pool.moreCapacity` 是**站房共享池**（另计），早先拿它当分母算出的"超容"**作废** |
| **全部改动未提交** | ✅ 已提交并推送：`ac7f6a4`（322 文件 / +329,218 行）→ `fork/feature/multi-layer-map`，工作区干净 |
| **工坊发布包缺前端文件** | ✅ **已解决**：`0_core_shared/build/build-workshop-package.ps1:110` 的白名单已含那 9 个 js ＋ 4 个 json ＋ `templates/vendor/icons/assets` 4 个目录 |

### 3.4 已结案（以前挂着的，现在有答案）

- **333 vs 565**（约 230 座站读不到建筑）→ **不是读不到，是本来就没有**：那 232 座是
  **简易公交站 195**（`cargo=false`）+ **货车卸货站 37**（`cargo=true`），没有站房建筑，
  两者**共用同一个 `.con`**（`station/street/modular_terminal.con`），只能靠站台 `cargo` 属性区分。
- **`station_geometry` 永远空** → 站群 id 写死成 `552273`（存档里不存在），已改成现找一个真实站群。
- **路由/航班的 `sourceEntity` 语义** → 不是产业，是产业的**库存**（09-30 傍晚锁定）。
- **工坊站型的结构反解怎么处理**（用户 2026-10-02 分两次决定）→
  反解目前只覆盖**游戏本体**的 `modular_station`（31 座）。剩下 47 座是工坊站型，**分两类**：

  | 站型 | 座数 | 处理 |
  |---|---|---|
  | `JQKA_station.con`（智能空轨集装箱检查货站） | 27 | 🔚 **不做** —— 「结构太简单没有任何意义」 |
  | `SuspendedMonorail/Sus_Mon_Station.con`（悬挂单轨） | 15 | 🔚 **不做**（同上理由） |
  | `skytrain/skytrainDH.con`（轻轨，同 mod） | 2 | 🔚 **不做**（同上） |
  | `ust/ust.con`（Ultimate Station） | 2 | ⏳ **保留待做** —— 原版模块化站的扩展，结构不简单 |
  | `mus.con`（Modular Underground Station 地下站） | 1 | ⏳ **保留待做** —— 同上 |

  ⚠️ 保留的两类（`ust` / `mus`）各自的 `.con` 布局脚本要单独读，**属独立任务**，不是"补完"。

---

## 四、架构：这套东西是怎么跑起来的（2026-10-02 梳理）

```
① 游戏进程
   ├─ mod（Lua，跑在引擎沙箱里，位置＝staging/tpf2_mcp/）
   │    · 入口：res/config/game_script/tpf2_mcp.lua —— 引擎回调 load/save/update/handleEvent
   │    · 唯一能周期干活的钩子：引擎的 update 回调 ⇒ **游戏暂停就什么都不推进**
   │    · 40 个采集器（collectors/），由 layer_registry.lua 按周期派发（Python 侧退化成纯读）
   │    · 沙箱里没有 io/os 的写文件 API ⇒ 走自建的写盘出口（collectors/bridge_io.lua）
   ├─ 引擎 API（官方参考 14 篇）
   │    · 读字段有**三条取值路**：组件 getter ／ pairs(组件) ／ game.interface.getEntity(id) 聚合表
   │    · 只读不需要注入；写操作（改线路/加车）要 DLL 注入 ⇒ 当前禁用
   └─ 产物：bridge/ 目录（全是纯文本文件）
         layer-*.json（图层）／*-probe.json（探针）／state.json（快照）／heartbeat.json（心跳）

② 文件邮箱 bridge/
   · 正向：mod 写、Python 读
   · 反向：只有一条窄路 —— command.json。**只能由 MCP 工具写**，手写会被 mod 当"已处理"吞掉
   · 有锁文件 ⇒ **并发调 MCP 会抢锁超时，必须串行**（地图服务每 1.5 秒抢一次锁）

③ Python 侧（两套，跑的位置不一样，别混）
   ├─ MCP 服务：<staging>/mcp_server/      ← WorkBuddy 的 ~/.workbuddy/mcp.json 拉起，暴露只读工具
   └─ 地图 HTTP 服务：<staging>/mcp_server/start_ui.py → <staging>/3_dashboard_ui/server/serve-rail-map.py
        · 端口 8790；桌面「TPF2 铁路图」拉起（托盘常驻，右键可重启服务）
        · 把 bridge 产物切块成 ui/rail-map/layers/*.json（manifest + data 两件套）

④ 前端（ui/rail-map/，**读项目目录**，不读 staging）
   · 两条页面线：network-app.js（全网视图）／ app.js（局部视图）
   · 扩展图层各自监听 tpf2map:ready 事件，然后用 window.TPF2Map 接口
   · 改了静态文件**必须提 index.html 的 ?v=**，否则浏览器吃缓存
```

**一句话的数据流**：游戏内 mod 定时把世界扫成 JSON 落进 `bridge/` → Python 服务切块 → 浏览器画图。
反向只有一条窄路：MCP 工具写 `command.json` → mod 在 `update` 里读。

**"改哪儿、怎么才生效"（最容易搞错的一张表）**

| 改的是 | 生效方式 |
|---|---|
| `tpf2_mod/**`（Lua） | 跑 `deploy_mod_layers.bat` ＋ **完全退出游戏再启动**（读档不重载） |
| `mcp_server/**`（Python） | 跑 `deploy_mod_layers.bat` ＋ 重启对应服务 |
| `3_dashboard_ui/server/serve-rail-map.py` | 跑 `deploy_mod_layers.bat`（**服务读的是 staging 那份**）＋ 重启地图服务 |
| `ui/rail-map/**`（前端） | **不用部署**（读项目目录），提 `?v=` 后刷新即生效 |
| **只改索引/文档**（`0_core_shared/index/**`、`docs/*.md`） | 本地重跑生成器即可，**不影响游戏** |
| `1_data_collection/exporters/build-*.py` / `extract-*.py` | 本地直接跑，产物落 `ui/rail-map/` 或 `reports/`（**`tools/` 已空，见 `ARCHITECTURE.md` §二**） |
| 加一个新的采集器/探针 | ① 先查 `docs/DATA_INVENTORY.md` ② 写 ③ 跑三条 `--check` ④ 部署+重启（细则见 `AGENTS.md`） |

**引擎侧：确认知道的 / 还不知道的**

| 已经确认 | 依据 |
|---|---|
| 产业只暴露 `stockList / level / upgradeProgress / closureTimeStamp / manualDevelopment` | 官方 `api.type.SimBuilding` |
| 车辆位置只能从 `BOUNDING_VOLUME` 包围盒中心推（组件视图里没有 position） | 探针实测 + `world-probe.json` |
| 读字段有三条取值路，少走一条就漏数据 | `field_probe.lua` + 长期实测 |
| 官方那三根统计柱（Production / Shipment / Transport）**不给 mod 读** | API 全量搜 + 游戏自带 Lua 里搜不到 `shipment`/`production` |

| 还不知道 | 影响 |
|---|---|
| `tpf2_control.dll` 从哪来、怎么装 | 写通道（L2 操作）用不了 ⇒ `AI_DEPLOY_GUIDE.md` 缺一节 |
| 「传输网边下标 → 实体」那条链 | 已放弃，车辆定位改用坐标匹配 |
| ~~车站候车量怎么读~~ | ✅ **2026-10-04 解决**：不用走引擎，`by_journey.line_stop_0` 聚合 + `stops[].index→group_id` 翻译即可 |
| 账本里"哪条线" | 线路级盈亏只能靠维护费 + 运价侧路估算 |

---

## 五、文档地图（96 份）

| 现行（可当依据） | 说明 |
|---|---|
| **本页** | 需求 + 进度 + 文档地图（入口） |
| `0_core_shared/ARCHITECTURE.md` | 🔴 **架构规约（施工图纸）**：四层定义 + 归属口诀、**契约路径表**、层间契约、1 层「禁止计算」边界、字段纪律、搬迁进度。**写新代码前先在这里找归属** |
| `AGENTS.md` | 🔴 **仓库硬规约**：本机路径、路径归属、提交禁止项、工坊打包规范、**变更前必跑的校验** |
| `docs/DATA_INVENTORY.md` | **数据资产总账 + 交叉索引**（自动生成）：接口利用率／接口→使用者／产物→字段／字段→产物／代码→官方文档，**外加「我想要 → 现成接口」对照表**。查「这个数据有没有、从哪拿」先看它 |
| `docs/CODE_WIKI_INDEX.md` | **代码 ↔ 官方文档索引**（自动生成）：**182 个源码文件 / 1125 个函数**逐条落到官方出处；映射表 `docs/code-wiki-map.json` |
| `docs/REFACTOR_PLAN.md` ／ `docs/ARCHITECTURE_MERGE.md` | 四层怎么搬的、为什么要这么分 |
| `docs/AI_DEPLOY_GUIDE.md` | **部署指南（给 AI 看的）**：三步安装 + 验证清单 + 坑清单 |
| `reports/TPF2_交接_2_昨天存档_20260927.md` | **存档＝当前档**（数字一致）。京广标杆车、JY 客运扎堆等结论**仍适用**；余额/状态以本页为准 |
| `reports/TPF2_交接_3_mod开发.md` | mod 代码·工具·部署链路 |
| `reports/TPF2_交接_4_知识库与引擎API_20260930.md` | 知识库 + 引擎 API 实测 |
| `reports/TPF2_交接_5_产业链与航线_20260930.md` | 产业链字段语义（**其 §五 待办清单已部分过期，以本页 §3.3 为准**） |
| `reports/TPF2_*_20260927.md`（京广/JY/走廊/客流/标车牌，12 篇） | **前期方向探索**（当时走的是运营线）。讲的就是当前档，价值在**口径与实测方法**；**运营尚未开始**，别当待执行清单 |
| `reports/TPF2_产业链物流关系`、`四类站结构解析`、`机场站场结构解析`、`车站容量`、`前端现状与官方文档优化`、`世界探针v3/v4 结果解读` | 专题结论（可当依据） |
| `reports/TPF2_多图层地图_任务规划_20260928.md` | 图层数据源地图（规划） |

| ⚠️ 需注意（不是"没用"，是**别当现状**） | 原因 |
|---|---|
| `reports/TPF2_交接_1_今天存档_20260928.md` | 讲的是 **09-28 那个小档**（16 城 / 140 线 / 664 车 / 362 亿），**当前没在用** |
| `reports/TPF2_交接与状态总览_20260928.md` | 同时讲**两个档**：其中「存档 A」＝ 当前档、「存档 B」＝ 09-28 小档。读时先分清 |
| `agents/` + `docs/`（英文那批） | **上游作者**原文，路径/存档都不是本机的；只作参考 |
