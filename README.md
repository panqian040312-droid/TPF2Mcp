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

> 本分支新增的图层（产业范围框、产业配方图标、产业链流向、城镇需求、路况色带）**截图待补** ——
> 前端还在迭代，等稳定了一并补上。

---

## 新功能（本分支）

### 一、多图层地图（`ui/rail-map/`）

8 个图层由 Mod 自驱采集、地图服务自动切块，浏览器按需加载：

| 图层 | 内容 |
|---|---|
| 路网 | 公路 + 轨道几何（本档 9,960 条边），含桥/隧道区分 |
| 线路 | 271 条线的走向 + **游戏里那条线的真实颜色** + 停靠站位 |
| 车辆 | 1,370 辆车的实时位置（按铁路/公路/水运/航空上色） |
| 车站 | 565 座站的坐标、容量、客运/货运属性 |
| 产业 | 215 个产业的位置 + **按厂区实际占地的范围框** |
| 城镇 | 27 个城镇：城名 + **它需要什么货**（商业区/工业区各自的需求） |
| 地形 | 地形等高线（按官方四级重做） |
| 产业链 | 物流关系（见下） |

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

### 七、诊断工具（`tools/`）

| 工具 | 作用 |
|---|---|
| `extract-industry-icons.py` | 从游戏 `ui.zip` 提取货物图标（TGA 手写解码） |
| `extract-industry-recipes.py` | 从 `.con` 解出配方与用量（自带硬校验） |
| `build-cargo-types.py` | 货种 id → 中文名 + 图标字典 |
| `build-station-structures.py` | 站场结构数据（占地框 + 站台 + 模块格子） |
| `build-road-geometry.py` | 道路几何（给路况色带用） |
| `diagnose-industries.py` | 产业供需诊断首版（供应比 / 等待占比） |

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

要求：Windows + Steam 版 TPF2 + **Python 3.11+**（无第三方依赖）。

> 🔴 三条最容易翻车的：**复制文件前必须退出游戏**；**改完 Lua 必须重启游戏**（读档不算）；
> **服务放在 Mod 根外面时必须设 `TPF2_MCP_MOD_DIR`**。

---

## 项目组成

- `tpf2_mod/` — Transport Fever 2 Lua Mod 源码（采集器 / 探针 / 图层）
- `mcp_server/` — Python MCP 服务 + 地图 UI 服务端
- `ui/rail-map/` — 地图前端（每个图层一个独立脚本）
- `tools/` — 数据生成工具；`analyze_*.py` 等根目录脚本是开发期一次性分析脚本，**部署不需要**

---

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/AI_DEPLOY_GUIDE.md`](docs/AI_DEPLOY_GUIDE.md) | **部署指南（给 AI 看的）** |
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | 现状入口：需求清单 + 开发进度 + 文档地图 |
| [`docs/technical-reference.md`](docs/technical-reference.md) | 架构、开发、安装与发布（上游） |
| [`docs/agent-mcp-tools.md`](docs/agent-mcp-tools.md) | 功能与受控操作入口（上游） |
| `docs/` 其余 | 上游各阶段开发文档与验收记录 |
