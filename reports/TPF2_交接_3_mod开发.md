# TPF2 会话交接 · 3/3 · mod 开发

> **本文件只给一个会话用**：管 TPF2Mcp 这个 **mod 的代码本身**（Lua 采集器 / 后端接口 / 前端图层 / 部署链路）。
> 另外两份分别管：`TPF2_交接_1_今天存档_20260928.md`（今天存档的运营优化）、`TPF2_交接_2_昨天存档_20260927.md`（旧档）。
> **本会话只改代码，不改游戏内数据/线路**（那是会话 1 的事）。

---

## 〇、开场指令（复制下面这段给新会话）

```
读 E:\workbody\TPF2Mcp\reports\TPF2_交接_3_mod开发.md，接手 TPF2Mcp 的 mod 开发。
详细工作日志：E:\workbody\.workbuddy\memory\2026-09-28.md 与 2026-09-27.md

背景：TPF2Mcp 是给《Transport Fever 2》做的 MCP mod（Lua 采集器 + Python 桥 + 网页地图）。
我在玩"省委书记"玩法，但已定好**先打地基、先完善 mod**。
路线图三步：①探针搞清引擎能力边界（在做）→ ②按结果补采集器 → ③后端接口 + 前端图层。

**当前进度（2026-09-28 20:23 已更新）**：
- ✅ 世界探针 v3 **已跑通**。`world-probe.json` 277 KB，拿到 72 个可解析组件、38 个组件的精确实体数
  （累计遍历 378,942 个实体）、12 张 API 注册表。
- 📄 **结果解读看这份**：`reports\TPF2_世界探针v3_结果解读_20260928.md`（含能力地图 + 6 个待补缺口）
- 📦 原始数据：`reports\data\world-probe-v3-20260928.json`（md5 `4dac84c1f52604e1f3a76084254710b3`）
- 🔑 三条硬结论：① `api.type.ComponentType` 确实不能用 `pairs()` 枚举（返回 0 项）；
  ② 「组件名 = UPPER_SNAKE(api.type 成员名)」**100% 成立**（205 → 72 个真组件，策展名单贡献 0）；
  ③ `game.interface` 有 60 个官方接口，里面 `findPath` / `getTownReachability` / `getIndustryProduction`
  这类是之前手工反推过的东西，现在有正式入口了。

**第一步（v4 探针）**：补解读报告第四节那 6 个缺口 ——
`api.engine.transport` / `api.engine.terrain` / `api.engine.system.<X>` 的方法表 /
`api.res.*Rep` 的方法表 / `api.util` / **每个组件的真实字段名**（最大的缺口）。
其中 `TRAIN` `RAIL_VEHICLE` `ROAD_VEHICLE` `SHIP` `AIRCRAFT` 五个车种组件 v3 解析成功但没遍历，v4 必须补上。

注意：**staging 的既有文件 Agent 是可以覆盖的** —— 需要用提升权限（绕过沙箱）执行，
用户确认一次即可。第二节那条"部署必须用户动手"已作废，详见第三节。

⚠ **改完 mod Lua 必须让用户完全退出游戏再启动**（读档不重载脚本），而且**游戏不能暂停**
（轮询挂在引擎 `update` 回调上）。
```

---

## 一、路径与部署链路

| 项 | 路径 |
|---|---|
| 项目根 | `E:\workbody\TPF2Mcp` |
| **mod 源码（改这里）** | `E:\workbody\TPF2Mcp\tpf2_mod\res\scripts\tpf2_mcp\` |
| mod 运行副本（游戏实际加载） | `C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\` |
| bridge 数据目录 | `…\staging_area\tpf2mcp_1\bridge\` |
| 游戏本体 | `E:\SteamLibrary\steamapps\common\Transport Fever 2` |
| 后端 | `mcp_server/src/tpf2_mcp/`（`serve-rail-map.py` 在 `tools/`） |
| 前端 | `ui/rail-map/` |
| 地图服务 | `http://127.0.0.1:8765`（用户双击桌面「TPF2 铁路图」= `start_rail_map.bat`） |

### 🔴 部署两件事，缺一不可

1. **把改过的文件覆盖到 staging**（Agent 用提升权限可以直接做，见第三节）
2. **完全退出游戏再启动**（TPF2 **只在启动游戏时读 mod Lua，读档不会重载脚本**）—— 这一步只能用户做

**本次只需覆盖 1 个文件**：`res\scripts\tpf2_mcp\collectors\world_probe.lua`
（`state.lua` 已经写好了 `require` + `M.world_probe()`，`runtime.lua` 已经挂在 `get_game_state` 分支上，都不用动。
2026-09-28 20:06 核对：这两个文件 project 与 staging 的 md5 本来就一致。）

**部署后必须校验**（这是唯一可靠的成功判据）：
```bash
md5sum "E:/workbody/TPF2Mcp/tpf2_mod/res/scripts/tpf2_mcp/collectors/world_probe.lua" \
       "/c/Program Files (x86)/Steam/userdata/1070536217/1066780/local/staging_area/tpf2mcp_1/res/scripts/tpf2_mcp/collectors/world_probe.lua"
```
两个哈希一致才算成功。`robocopy` 会**假报** "Files copied successfully."，不看哈希不算数。

**部署方式（2026-09-28 20:06 实测更新）**：
- ✅ **Agent 直接部署可行**：用 Bash/Python 走提升权限（弹一次用户确认）执行 `shutil.copyfile`，
  实测 `COPY: OK` + 双向 md5 一致。这是**首选方式**，用户不用去找路径、不用拖拽。
- 用户手动方式仍可用：资源管理器拖拽覆盖（保留时间戳）或双击 `deploy_mod.bat`（用 `copy /Y`，会改 mtime）
- ⚠ **不要再往 staging 手动改文件之外的路径**：前端（`ui/`）已经通过 `start_rail_map.bat` 的 `--ui-directory "E:\workbody\TPF2Mcp\ui\rail-map"` 直接从项目目录读取，**改前端立即生效，不用同步**

---

## 二、bridge 命令机制（理解这个才不会白等）

```
人/ Agent  →  bridge\command.json  →  游戏内 mod 轮询到 → 处理
                                       →  bridge\responses\<request_id>.json + .json.ready
```

- mod 每 `config.bridge_poll_interval_updates` 个 tick 读一次 `command.json`；**`request_id` 与上次相同就跳过**
- 🔴 `runtime.lua` 的 `M.start()` 启动时会**读一次已存在的 `command.json` 并把它的 request_id 记为"已处理"**（防止上个会话的残留命令被重放）
  → **所以不能提前把命令写好等游戏读**，必须在游戏进档之后再发
- 🔴 **探针不是自动写的**：`world-probe.json` 只在收到 **`get_game_state`** 命令时由 `runtime.lua:194` 写出。
  心跳（每 ~2 s）**不会**触发探针。这就是"三个文件都部署好了但 world-probe.json 一直不出现"的原因。
- **怎么发命令**：用 MCP 工具 `mcp__tpf2__get_game_state`（带 `force_refresh=true`）—— 本会话实测**该 MCP 服务是连通的**。
- ⚠ MCP 服务 与 UI 服务 会争同一个 bridge 邮箱锁（`command.lock`）→ 同时跑可能 `timeout waiting for the shared bridge mailbox lock`；报锁超时就先关掉地图服务窗口

`get_game_state` 一次会写出这一批文件（全在 `bridge\`）：
`state.json` / `company-probe.json` / `semantic-probe.json` / `operations-probe.json` / `ui-source-probe.json` /
`context-probe.json` / `dynamic-transport-probe.json` / `write-api-probe.json` / `vehicle-write-api-probe.json` /
`line-raw-probe.json` / `line-creation-probe.json` / `api-type-inventory.json` / `api-command-inventory.json` /
**`world-probe.json`** / `station-geometry.json`

---

## 三、🔴 沙箱限制（Agent 侧实测，决定工作方式）

对 `bridge\` / `staging_area\` 这类**工作区外**目录：

| 操作 | 沙箱内 | 提升权限（`dangerouslyDisableSandbox` + 用户确认一次） |
|---|---|---|
| **新建**文件 | ✅ 可以 | ✅ 可以 |
| **覆盖既有**文件 | ❌ `PermissionError [Errno 13]` | ✅ **可以**（2026-09-28 20:06 实测 `shutil.copyfile` 成功、md5 一致） |
| 删除文件 | ❌ safe-delete 钩子拦（trash 失败） | ✅ **可以**（`Path.unlink()` 实测成功） |
| `os.replace` 移出该目录 | ❌ `WinError 5 拒绝访问` | 未测（用 unlink 就够了） |

（沙箱内对照实验排除 ACL 因素：同目录下新建成功、覆盖失败，ACL 显示 `RailG FullControl`。
→ 所以限制来自**沙箱本身**，不是权限，提升权限即可绕过。）

**既往结论作废**：交接文档早期写的"覆盖既有文件 `dangerouslyDisableSandbox` 也无效"是**错的**，
当时没实测过提升权限路径。**部署 staging 既有文件不必再让用户动手**。

**仍然成立的两条工作方式**：
1. **改代码**只改 `E:\workbody\TPF2Mcp\` 下的源码，改完由 Agent 部署（提升权限）+ md5 校验
2. **发命令**只能走 MCP 工具（`mcp__tpf2__*`），不能自己写 `command.json`（会被"防重放"逻辑吞掉）

> 遗留已清：2026-09-28 20:06 用提升权限把之前删不掉的 `zz-sandbox-overwrite-test.txt`、
> `command.json.bak` 从 `bridge\` 删除完毕，目录已无残留。

---

## 四、引擎 API 结构（本轮最重要的发现）

### 4.1 `api.type` 有 205 个可枚举成员（PascalCase）
`api-type-inventory.json` 里已经完整落了盘。里面**同时混了三类东西**：
- **组件/数据类型**：`Terrain`、`TerrainTile`、`TerrainTileHeightmap`、`WaterMesh`、`Map`、`GroundTexture`、
  `SimBuilding`、`TownBuilding`、`TownBuildingParams`、`BuildingType`、`Construction`、`ModuleDesc`、`LotList`、`Parcel`、
  `BaseEdgeStreet`、`StreetType`、`StreetProposal`、`LaneConfig`、`RailroadCrossing`、
  `TransportNetwork`、`TransportNode`、`TransportEdge`、`TpNetData`、`TpNetLink`、
  `RunwayList`、`PortId`、`Ship`、`Aircraft`、`Bridge`、`BridgeType`、`TunnelType`、
  `Signal`、`SignalList`、`Town`、`TownConnection`、`CargoType`、`TransportHistory`、`TransportationStats` …
- **写命令构造器**：`CreateLine`、`DeleteLine`、`SellVehicle`、`BuyVehicle`、`SetGameSpeed`、`SetName`、`SetDate`、`CreateTowns`、`DevelopTown` …
- **数学/值类型**：`Vec2f`、`Vec3f`、`Box3`、`Mat4f`、`Color`、`Value`、`ValuesMap` …

### 4.2 🔴 组件名 = `UPPER_SNAKE(api.type 成员名)`
```
TransportVehicle → TRANSPORT_VEHICLE      SimBuilding → SIM_BUILDING
BaseEdgeTrack    → BASE_EDGE_TRACK        StationGroup → STATION_GROUP
GameTime         → GAME_TIME              TickEpoch   → TICK_EPOCH
ModelInstanceList→ MODEL_INSTANCE_LIST    BoundingVolume → BOUNDING_VOLUME
TpNetData        → TP_NET_DATA            WaterMesh   → WATER_MESH
```
**mod 里现在在用的每一个组件名都符合这条映射**（`LINE`/`SIGNAL`/`NAME`/`PLAYER`/`ACCOUNT`/`CONSTRUCTION`/`VEHICLE_DEPOT`/`MOVE_PATH`/`SIGNAL_LIST`…）→ 这条规则可信，也是 v3 探针的取名单依据。
**但**：光有名字不够 —— **「能解析出组件类型」≠「能读到数据」**（见 4.4）。

### 4.3 ❌ `api.type.ComponentType` **不能**用 `pairs()` 枚举
v2 探针实测：`pairs(api.type.ComponentType)` 迭代 0 次（`enumeration_ok = true` 但 `component_type_count = 0`）。
只能按名字取：`api.type.ComponentType["LINE"]`（← `common.component_type(name)` 就是这么干的）。
大概率是带 `__index` 的枚举 userdata。v3 探针里专门记了它的 `value_type` / `pairs` 成员数 / `pairs` 键，用来确认这一点。

### 4.4 组件是 userdata → `pairs()` 拿不到字段，只能**按名字逐个试读**
```lua
common.field(value, key)          -- pcall 包一层再取值
common.array_count(value)         -- pcall 取 #
common.probe_fields(value, keys)  -- 按给定 key 名单试读（mod 里到处在用这个套路）
common.sequence_values(value)     -- 引擎数组可能是 0 基
```
→ 所以探针要探「某组件有哪些字段」，就得**给一份候选键名单挨个试**（v3 的 `PROBE_KEYS` 约 90 个键）。

### 4.5 `api.cmd.make` 有 33 个成员 = 游戏可被脚本改动的表面
`buildProposal`、`connectTownsAndIndustries`、`createLine`、`deleteLine`、`createTowns`、`developTown`、
`buyVehicle`、`sellVehicle`、`setGameSpeed`、`setDate`、`setName`、`bookJournalEntry` …
⚠ 能构造命令 ≠ 能安全执行；mod 侧真正可用的写操作由 `local_config.lua` 白名单 + `operations/dispatcher.lua` 决定
（**当前白名单只有 `SET_LINE_STOP_POLICY`**，文件在 staging 的 `res/scripts/tpf2_mcp/local_config.lua`，改完必须完全重启游戏）。

---

## 五、世界探针 v3（本次的核心交付）

| | v2（已跑到空结果） | **v3（已写好 + 已部署到 staging，等重启游戏加载）** |
|---|---|---|
| 路径 | `tpf2_mod/res/scripts/tpf2_mcp/collectors/world_probe.lua` | 同 |
| 大小 | 4046 B | **13274 B** |
| md5 | `d714adb29906acf9b331a023a8bac6f0` | **`5678dcf61f48dd81c9357488e71c4bf9`** |
| 取候选组件名 | `pairs(api.type.ComponentType)` → **空** | ① `api.type` 205 个成员名转 UPPER_SNAKE ② 加策展名单 |
| 备份 | `_backup\world_probe_v2_20260928_195900.lua`（可回滚） | — |

**v3 会输出什么**（`bridge\world-probe.json`）：
1. `component_type_probe`：`api.type.ComponentType` 的类型、能否 `pairs`、`pairs` 到的键
2. `component_names_resolved` / `component_names_missing`：205+ 个候选名里**哪些真能解析成组件类型** ← **这就是"能力地图"的第一层**
3. `component_walk`：对**规模可控**的组件做实体遍历 → `count` + 前 3 个实体的**字段快照**
   （`pairs_keys` + 按 90 个候选键试读出的 `fields`）← **这是"能读到什么精度"的答案**
4. `registries`：`api` / `api.type` / `api.engine` / `api.engine.system` / `api.engine.util` /
   `api.engine.component` / `api.res` / `api.cmd` / `api.cmd.make` / `game` / `game.interface` / `game.config`
   **各自的成员名单** ← 用来找"还没用上的数据源"（比如有没有 `industryRep` 这种仓储）

**🔴 安全边界（mod 作者当年一次性遍历把游戏搞崩过）**：
v3 **不做** `TERRAIN_TILE` / `MODEL_INSTANCE_LIST` / `SIM_PERSON` / `SIM_CARGO` / `ANIMAL` / `PARTICLE_SYSTEM` 这类
可能上百万实体的遍历 —— 这些只记录「类型能否解析」。
允许遍历的名单写在 `WALK_LIST`（约 70 个结构类组件），单个组件只取前 3 个实体的字段。
**若要扩到那些大组件，必须单独一轮、单个试、并且先跟用户打招呼。**

**语法自检**：改完先跑 Lua 5.2 语法检查（见第六节），再交给用户部署。

---

## 六、开发工具

| 工具 | 说明 |
|---|---|
| `_tmpdb\luacheck\lua-syntax-check.js` | **新增**：用 `luaparse` 做 Lua 5.2 语法检查（不执行代码）。用法见下 |
| `_tmpdb\luacheck\luaparse.js` | 依赖，已下载到项目内（不装任何全局包） |
| `deploy_mod.bat` | 把 3 个文件复制到 staging 并回显大小/时间戳（用 `copy /Y`，会改 mtime；**只在用户想自己部署时用**，Agent 走提升权限更省事） |
| `start_rail_map.bat` | 用户双击启动地图服务；已带 `--ui-directory` 指项目目录 |
| `tools/serve-rail-map.py` | UI 后端（路由：`/api/live`、`/api/demand-live`、`/api/operations-context`、`/api/status`…） |
| `mcp_server/src/tpf2_mcp/bridge.py` | Python 侧 bridge 客户端（`_atomic_json_write(command.json)` + 轮询响应） |

```bash
# Lua 语法检查（改完 mod 的 .lua 先跑这个）
"C:/Users/RailG/.workbuddy/binaries/node/versions/22.22.2-3/node.exe" \
  "E:/workbody/TPF2Mcp/_tmpdb/luacheck/lua-syntax-check.js" \
  "E:/workbody/TPF2Mcp/tpf2_mod/res/scripts/tpf2_mcp/collectors/world_probe.lua"
```
（已验证：这个检查器对现有 3 个正常文件返回 OK，可作基准。）

**mod Lua 版本 = Lua 5.2**（`heartbeat.json` 的 `probe.lua_version` 实测）。注意 `table.unpack` 而不是 `unpack`。

---

## 七、已查证的能力边界（**别再重复论证**）

| 问题 | 结论 | 证据 |
|---|---|---|
| 地图能否自动跟随游戏视角 | ❌ **不可实现** | 205 项 `api.type` 里无 camera/view/screen/zoom；`game.interface.*` 24 个方法里无相机相关；游戏 Lua 里 `camera` 只出现在引导系统的事件名（`camera.userPan` 等，不带角度值） |
| 车辆 mod 的 `cameraConfig.positions` | 是**车厢内司机视点**（静态数据），与自由视角无关 | `3374213837\...\CR400AF_0207\HC\CR\*.mdl` |
| 作业线路（停哪些站） | ✅ 已有，**不用开发** | `/api/operations-context` 返回 140 条 |
| 路网几何 | ⚠ 只采了**铁路**（从 `BASE_EDGE`/`BASE_NODE` 里筛轨道） | `rail_network.lua` |
| 其他交通/地形/水体 类型是否存在 | ✅ 类型都在（见 4.1） | 205 项清单 |
| 能否读到它们的**数据** | ❓ **未知，v3 探针就是回答这个** | — |
| 反向证据 | 游戏自己的 Lua 里 `Terrain` 只用于施工地形对齐和菜单图标；`Water` **0 命中** → 游戏自己也不怎么用这些数据 | `constructionutil.lua:215/232`、`contexthelper.lua:71/161` |
| 高程 | ✅ **已经能拿到**：铁路节点坐标的 `z` 就是海拔（5043 点，−11.6 ~ 130.9 m） | `rail-network.json` |
| 游戏"设计层"配置 | ✅ 可读：`res/scripts` 71 个 lua、`res/config` 1164 个 lua、`terrain_heightmaps` 11 个 PNG、`base_config.lua` 504 行、`cargo_types` 17 个 | 直接读文件 |
| C++ 引擎源码 | ❌ 不开源（模拟算法/物理/寻路/AI 拿不到） | — |

`base_config.lua` 里就是那些游戏参数（**可被 mod 覆盖**）：产业密度、`cargoNeedsPerTown = 2`、需求灵敏度、`closureCountdownTimeSpan = 730.5*2000`（← 就是运力公式里 730.5 的出处）。

---

## 八、环境坑清单（mod 开发专用）

1. **TPF2 只在启动游戏时读 mod Lua** → 改代码必须**完全退出游戏再启动**（读档不行）
2. **游戏暂停 / 停在主菜单时 mod 主循环不跑** → 心跳会停，别把"没数据"当成"代码坏了"
3. **沙箱内不能覆盖工作区外既有文件**，但**提升权限可以**（第三节）→ 部署由 Agent 做，用户只需重启游戏
4. **`robocopy` 假报成功** → 一律回读哈希/时间戳校验
5. **Lua 沙盒对 `.tmp` 后缀读不到**（连已存在的 `.tmp` 都打不开），`.json` 放行 → mod 里所有探测/临时文件**必须用 `.json` 后缀**
6. **`M.start()` 会吞掉启动前已存在的命令**（防重放）→ 命令必须在游戏进档后发
7. **MCP 服务 与 UI 服务争 bridge 邮箱锁** → 报 `timeout waiting for the shared bridge mailbox lock` 就先关掉地图服务
8. **一次回调遍历太多实体会让游戏原生崩溃**（mod 作者踩过）→ 大组件必须分批/分节
9. **`get_lines`（MCP 工具）有 schema bug**（返回数组却声明成 record）→ 绕开它，走 HTTP `/api/operations-context`
10. **`line.frequency_seconds` 不可信** → 用实测单圈时间
11. **时钟比例动态变化**（挂钟/游戏 0.43–2.64）→ 一律现读 `simulation.deltas`
12. **等待时长有哨兵值**：`request_time = 0` 的实体等待 = 整个游戏时长（`p90 == max == 同值` 即伪影）
13. **mod 侧采样固定每 2.01–2.02 墙上秒一帧** → 自己的采样脚本间隔要 ≥2 s
14. **bat 里路径含 `(x86)` 的右括号会提前闭合 `if (...)` 块** → 用 `goto` 标签；`find /I "文本"` 在 `chcp 936` 下引号乱码 → 用 `findstr`
15. **PowerShell 工具在本机经常无输出**（同一命令改用 Python 就正常）→ 优先用 Python 做文件/时间戳检查
16. **`station-events.sqlite3` 被 WAL 锁** → 读取前先 copy 到 E: 再开
17. **`local_config.lua` 只在** staging 副本里存在（项目目录没有），是**按操作名索引的表**不是数组；改完要完全重启游戏

---

## 九、路线图与待办

| 步骤 | 内容 | 状态 |
|---|---|---|
| ① | ~~部署 world_probe v3 → 重启游戏 → 触发 `get_game_state` → 解读 `world-probe.json`~~ | ✅ **已完成（20:23）** |
| ①b | **v4 探针**：补解读报告第四节 6 个缺口（`api.engine.transport` / `terrain` / `system.<X>` 方法表 / `api.res.*Rep` / `api.util` / 各组件真实字段名），并遍历 `TRAIN`/`RAIL_VEHICLE`/`ROAD_VEHICLE`/`SHIP`/`AIRCRAFT` | 🔴 **下一步** |
| ② | 按探针结果补采集器：其他路网（道路/水运/航空）、产业配方、城镇需求、建筑 | 待① |
| ③ | 后端接口 + 前端图层（把新数据画到地图上） | 待② |
| — | `cargoNeedsPerTown = 2` 的具体是哪 2 种（城镇需求） | 待① |
| — | 铺轨/建造类操作 mod **做不到**（`api.cmd.make` 里有 `buildProposal` 但 dispatcher 未实现、也无建造类白名单）→ 若以后要"让 AI 自己铺轨"，得单独设计 | 备忘 |
| — | `api.engine.component` 是否存在且可枚举 | v3 会答 |

---

## 十、三份交接文档的分工（避免串台）

| 文件 | 管什么 | 不管什么 |
|---|---|---|
| `TPF2_交接_1_今天存档_20260928.md` | 今天存档的游戏内运营（咽喉方案 C、全网普查） | 不改 mod 代码 |
| `TPF2_交接_2_昨天存档_20260927.md` | 旧档的结论迁移 / 备查 | 不改 mod 代码 |
| **`TPF2_交接_3_mod开发.md`（本文件）** | **mod 代码、探针、采集器、接口、前端、部署** | 不动游戏内存档数据 |
