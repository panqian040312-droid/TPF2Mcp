# 四层架构重构计划

> 生成：2026-10-03 ｜ 状态：**待拍板**（本文只做计划，未动任何代码）
> 体检脚本：`_audit/dup_scan.py`（只读）＋ 产物 `_audit/dup_scan.json`

---

## 结论摘要

| 问题 | 数量（归档后仍在使用的代码里） |
|---|---|
| **同族文件互相复制** | 23 对（相似度 ≥ 0.40，最高 0.74） |
| **同一个函数在多个文件里各写一份** | 75 组同名；其中 **2 组函数体逐字相同** |
| **Lua 向量/几何/取值工具重复** | `vec` 11 份、`bounds_for` 4 份、`sample_height` 3 份、`describe` 6 份 |
| **前端同功能重复** | `buildPanel` 5 份、`boot`/`updatePositions`/`applyVisibility` 各 3 份、`app.js`↔`network-app.js` 5 个画图函数各 2 份 |
| **"有现成接口却自己造"的绕路** | 已知 6 类（详见 §1.2），最严重的是**扫描游戏进程内存取数** |
| 已自行归位 | 顶层 **70 个一次性脚本**已在 `_archive/20260927_exploration/scripts/` |

**总判断**：真正需要动手的是 **Python 工具层（tools/）＋ Lua 采集层的工具函数 ＋ 前端图层外壳**这三块；
顶层那堆历史脚本**已经归位，不再重复处理**。

---

## 一、重复与绕路体检

### 1.1 重复：同一个实现被写了好几遍

**A. Python**

| 现象 | 位置 | 证据 |
|---|---|---|
| 9 个 live 验收脚本同一模板 | `tools/test-phase11/12/13-assign/13-buy/20-*/final-*` | 相似度 0.42–0.53；每个都重写一遍 `write()/save()/dump()` 存档助手 + argparse + BridgeClient 三件套 |
| 买卖车操作脚本近乎同源 | `4_execution_control/actions/operate-assign-vehicle.py` ↔ `operate-sell-vehicle.py` | **相似度 0.74**（全项目最高） |
| 造线 / 换车队 / 配置目标三脚本互抄 | `4_execution_control/actions/operate-expand-line.py`、`replace-line-fleet.py`、`test-phase20-configure-goal-live.py` | 两两 0.41–0.44 |
| 分位数算两遍 | `mcp/dwell_optimizer.py`、`mcp/timetable_planner.py` | `_percentile` 同名同职 |
| 参数校验写两遍 | `mcp/operations/handlers/create_line.py`、`set_line_stops.py` | `validate_parameters` / `verify_postcondition` |
| DB 连接助手三份 | `mcp/demand_history.py`、`station_log.py`、`work_log.py` | `_connect` ×3 |

**B. Lua**

| 现象 | 位置 | 证据 |
|---|---|---|
| 向量运算各写一份 | 11 个文件 | `layer_industry / layer_lines / layer_road / layer_road_traffic / layer_stations / layer_terrain / layer_vehicles / operational_telemetry / rail_network / station_geometry / station_struct_probe` |
| 包围盒算 4 遍 | `layer_industry / layer_vehicles / operational_telemetry / rail_network` | `bounds_for` ×4（另有 `bounds_center` ×2） |
| 高程采样 3 遍 | `layer_stations / layer_terrain / rail_network` | `get_height_function` ×3 ＋ `sample_height` ×3 |
| 节点取坐标 2 遍 | `rail_network / station_geometry` | `position_from_node`、`base_node` |
| 字段安全取值 6 遍 | 分散在 11 个文件 | `number_or_nil` ×2、`number` ×2、`entity_id` ×3、`entity_number` ×2、`safe_members` ×2、`describe` ×6 |
| 布局描述器重复 | `layer_industry ↔ layer_vehicles` | 相似度 0.46 |

**C. 前端（`ui/rail-map/`）**

| 现象 | 位置 | 证据 |
|---|---|---|
| 五个图层的面板外壳各写一遍 | `freight-flow / industry-icons / road-congestion / station-struct / town-layer` | `buildPanel` ×5 |
| 挂载/刷新/显隐三件套各写一遍 | `industry-icons / station-struct / town-layer` | `boot` ×3、`updatePositions` ×3、`applyVisibility` ×3 |
| 两张页面线互抄画图函数 | `app.js` ↔ `network-app.js` | `sideOfPolyline`、`baseX`、`faceForPointer`、`updateViewport`、`setZoom` 各 2 份 |
| 视口/坐标工具重复 | `bridge-crossings / terrain-contour / network-app` | `worldPoint`、`ratio`、`at`、`buildContours` |

### 1.2 绕路：有现成的东西却自己造

| # | 绕路做法 | 绕在哪 | 现成的正路 |
|---|---|---|---|
| 1 | **扫游戏进程内存**取数：`mem_dump / mem_find / mem_scan / mem_scan2 / mem_table / run_memscan` 6 个脚本 | 反汇编/内存扫描，脆弱且和版本绑死 | mod 里直接调引擎 API（已实现） |
| 2 | **解压存档**读数据：`unzstd_save.js` + `_save/` | 自己解 zstd 读二进制 | bridge 直接给 JSON |
| 3 | **车辆成本算了 6 遍**：`classify_vehicle_cost / probe_vehicle_cost / resolve_vehicle_cost / cost_per_train / build_cost_profile / scan_workshop_costs` | 6 份脚本算同一个数，口径还不一致 | 离线产物 `ui/rail-map/line-cost-profile.json` 一份即可 |
| 4 | **车站模块读 3 遍**：`station_modules / save_station_modules / _tmpdb/station_capacity` | 三份解析同一份 `.con` | `1_data_collection/exporters/build-station-structures.py` 已统一 |
| 5 | **离线复算 bridge 已给的字段**：`analyze_*` 25 个 + `check_*` 7 个 | 对同一份 JSON 反复重算 | 归 `2_brain_analysis` 一次算清 |
| 6 | **文档叠版本**：`snapshot-schema-v2/v3/v4/v5` 四份并存 | 读的人不知道以哪份为准 | 只留最新 + 变更记录 |

> 第 1–5 项的脚本**已全部进 `_archive/`**（顶层 70 个），所以"绕路"这一项**已基本止血**，
> 剩下的只是**要不要连归档一起删掉**（见 §7 决策点 D）。

### 1.3 已经归位的部分（不用再动）

- 顶层 71 个 `.py` → 70 个已进 `_archive/20260927_exploration/scripts/`，仅 `make_shortcut.py` 留在顶层。
- `_backup/`、`build_stage/`、`_tmpdb/`、`_save/`、`_state/`、`diagnostics/`、`logs/` 均为运行/构建残留。
- `bridge/`、`tpf2_mcp_state/` 是运行时数据，不进 Git。

---

## 二、目标四层结构

### 2.1 项目根目标布局

```
TPF2Mcp/
├── 0_core_shared/            ← 契约层：跨层共享物 + 元规则（无业务逻辑）
│   ├── ARCHITECTURE.md       ← 【新】层间边界 + 契约路径表 + 字段复用规则（先查再写）
│   ├── schema/               ← 【新】唯一字段真相
│   │   ├── layer.schema.json           图层产物（9 个 layer-*.json 共用）
│   │   ├── probe.schema.json           探针产物
│   │   ├── actions.schema.json         approved_actions.json
│   │   ├── audit.schema.json           audit_log.json
│   │   └── fields.json                 【新】产物字段索引 —— 写新字段前先查这里（复用优先）
│   ├── protocol/             ← 原 protocol/（6 文件，bridge 协议）
│   ├── index/                ← 原 0_core_shared/index/build-code-wiki-index.py + build-data-inventory.py + index-tpf2-lua-sources.py
│   ├── checks/               ← 原 tools/verify-*.py + validate-snapshot.py
│   ├── build/                ← 原 0_core_shared/build/build-workshop-package.ps1 + build-release-package.py + install-mod.ps1 + build-phase*-evidence.ps1
│   └── lua/                  ← 【Lua 侧】runtime / state / config / json / bridge_io / common / component_access / layer_registry
│
├── 1_data_collection/        ← 只读采集：只读 + 导出，不算数
│   ├── lua/                  ← 【Lua 侧】res/scripts/tpf2_mcp/1_data_collection/ 的源（镜像，见 §三.1）
│   ├── collectors/           ← 9 个图层采集器 + 8 个领域读取器 + 保留的探针
│   └── exporters/            ← 原 tools/export-*.py(4) + build-station-structures.py 等本地生成器
│
├── 2_brain_analysis/         ← 分析：纯计算，产出作战方案
│   ├── diagnose/             ← diagnose-industries.py、find_deadlock_risks.py、analyze-line-economics.py
│   ├── planners/             ← build-line-timetable-plan.py + mcp_server 的 planners
│   └── pkg/                  ← 由 mcp_server/src/tpf2_mcp/{analytics,planning,tasks,graph,...} 搬来
│
├── 3_dashboard_ui/           ← 表现：渲染 + 收指令
│   ├── rail-map/             ← 原 ui/rail-map/（19 源码文件 + 资产）
│   ├── server/               ← 原 3_dashboard_ui/server/serve-rail-map.py + mcp_server/start_ui.py + station_preview.py
│   └── shared/               ← 【新】五个图层共用的面板/挂载外壳（消掉 buildPani ×5 等重复）
│
├── 4_execution_control/      ← 执行：唯一的写通道
│   ├── validator.py          ← 【新】执行前状态检查
│   ├── controller/           ← 原 mcp_server/src/tpf2_mcp/operations/**
│   ├── rollback/             ← 【新】回滚（复用 operations/diff.py）
│   ├── actions/              ← 原 tools/operate-*.py + apply-*.py + replace-line-fleet.py
│   ├── acceptance/           ← 原 tools/test-*-live.py(9) + watch-operations-until.py
│   └── audit_log.json        ← 【新】执行流水（运行时生成，不进 Git）
│
├── tpf2_mod/                 ← 🔒 不可移动（引擎加载契约，见 §三.1）
├── mcp_server/               ← 🔒 不可移动（MCP 注册契约 + 工坊包结构，见 §三.2）
├── ui/rail-map/              ← ⚠️ 保留为发布契约路径（薄壳），真实源码在 3_dashboard_ui/rail-map/
├── docs/ reports/ agents/    ← 文档，原位
└── _archive/ _backup/ _tmpdb/ _audit/  ← 非源码，原位
```

### 2.2 文件级搬迁表

**① Lua（48 个文件，10,564 行）—— 目标：`tpf2_mod/res/scripts/tpf2_mcp/` 内部分层**

| 现在 | 目标 | 归属 |
|---|---|---|
| `runtime.lua`、`state.lua`、`config.lua`、`json.lua` | `0_core_shared/` | 框架 |
| `collectors/bridge_io.lua` | `0_core_shared/` | 唯一写盘出口 |
| `collectors/common.lua`、`component_access.lua` | `0_core_shared/` | 读字段工具（被 34 个文件 require） |
| `collectors/layer_registry.lua` | `0_core_shared/` | 调度器 |
| `collectors/layer_*.lua`（9 个） | `1_data_collection/` | 图层采集 |
| `collectors/{cargo,company,industry,line,station,town,vehicle,simulation}.lua` | `1_data_collection/` | 领域读取 |
| `collectors/{demand_probe,station_struct_probe,economy_probe,line_demand,line_finance_probe,operational_telemetry}.lua` | `1_data_collection/` | 在用探针 |
| `collectors/{api_inventory,world_probe,field_probe,context_probe,dynamic_probe}.lua` | `1_data_collection/` | 能力盘点探针 |
| `collectors/{line_creation_probe,line_raw_probe,operations_probe,vehicle_write_probe,write_api_probe,ui_source_probe,route_probe,rail_network,station_geometry}.lua` | `1_data_collection/_retired/` | 一次性验证探针（**待确认后归档**，见 §7 决策点 E） |
| `operations/{dispatcher,line_stop_builder,timetable_controller}.lua` | `4_execution_control/` | 写操作 |

**② Python / 工具（tools/ 43 个 + mcp_server 52 个）**

| 现在 | 目标层 | 说明 |
|---|---|---|
| `1_data_collection/exporters/export-layer-map.py`、`export-rail-network-map.py`、`export-physical-station-map.py`、`export-static-station-map.py` | 1 | 桥数据 → 前端数据 |
| `1_data_collection/exporters/build-station-structures.py`、`build-road-geometry.py`、`build-cargo-types.py`、`extract-industry-icons.py`、`extract-industry-recipes.py`、`collect-line-demand.py` | 1 | 离线生成器 |
| `2_brain_analysis/diagnose-industries.py`、`find_deadlock_risks.py`、`analyze-line-economics.py`、`analyze-operational-telemetry.py` | 2 | 诊断 |
| `2_brain_analysis/build-line-timetable-plan.py`、`record-and-optimize-dwell.py` | 2 | 方案 |
| `4_execution_control/actions/operate-assign-vehicle.py`、`operate-sell-vehicle.py`、`operate-expand-line.py`、`replace-line-fleet.py`、`apply-dwell-optimization.py`、`apply-line-timetable.py`、`run-operational-telemetry.py` | 4 | 写操作 |
| `tools/test-*-live.py`（9 个）、`watch-operations-until.py` | 4 | 验收 |
| `3_dashboard_ui/server/serve-rail-map.py` | 3 | 前端服务 |
| `0_core_shared/index/build-code-wiki-index.py`、`build-data-inventory.py`、`index-tpf2-lua-sources.py` | 0 | 元工具 |
| `tools/verify-*.py`、`validate-snapshot.py` | 0 | 校验 |
| `0_core_shared/build/build-workshop-package.ps1`、`build-release-package.py`、`install-mod.ps1`、`build-phase*-evidence.ps1`、`collect-diagnostics.ps1` | 0 | 构建 |
| `mcp_server/src/tpf2_mcp/{analytics,planning,tasks}/**`、`graph.py`、`dwell_optimizer.py`、`timetable_planner.py`、`overtake_planner.py`、`fleet_policy.py`、`vehicle_length.py`、`demand_history.py`、`rail_live.py`、`rail_crossings.py` | 2 | 算法 |
| `mcp_server/src/tpf2_mcp/operations/**`、`journal.py`、`work_log.py`、`station_log.py`、`dispatch.py` | 4 | 写通道 |
| `mcp_server/src/tpf2_mcp/{bridge,snapshot,save_scope}.py` | 1 | 读桥 |
| `mcp_server/src/tpf2_mcp/{server,cli,config,protocol}.py` | 0 | 入口/契约 |
| `mcp_server/src/tpf2_mcp/station_preview.py` | 3 | 渲染 |

**③ 前端（`ui/rail-map/`，19 个源码文件 + 资产）**

| 现在 | 目标 | 说明 |
|---|---|---|
| 全部 | `3_dashboard_ui/rail-map/` | 整体搬迁，`ui/rail-map/` 留薄壳或改服务指向 |
| **【新】公共外壳** | `3_dashboard_ui/shared/layer-shell.js` | 消掉 `buildPanel×5`、`boot×3`、`updatePositions×3`、`applyVisibility×3` |
| **【新】公共几何** | `3_dashboard_ui/shared/geo.js` | 消掉 `app.js↔network-app.js` 的 5 个重复函数 |

---

## 三、三条硬约束（这几处**不能**照四层搬）

> 这不是反对四层，是这四个位置被**外部**钉死了。搬了就断链。

### 1. Lua 只能住在 `tpf2_mod/res/`
引擎按固定约定加载：入口 `res/config/game_script/tpf2_mcp.lua` → `require "tpf2_mcp/runtime"`
→ `res/scripts/tpf2_mcp/*.lua`。**`res/config/game_script/` 这个路径是引擎写死的，改不了。**
✅ 可行做法：在 `res/scripts/tpf2_mcp/` **内部**建 `0_core_shared/ 1_data_collection/ 4_execution_control/` 子目录，
入口文件里把 `require` 路径改新即可。四层照样成立，只是根在 `tpf2_mod/res/scripts/tpf2_mcp/`。

### 2. `mcp_server/` 与 `ui/rail-map/` 是**发布契约**，不是内部目录
| 谁依赖它 | 依赖什么 |
|---|---|
| `~/.workbuddy/mcp.json` | `staging/mcp_server/start_server.py`（MCP 注册点） |
| `rail-map-service.pyw` | `SERVICE_ENTRY = <staging>/mcp_server/start_ui.py`；`UI_DIRECTORY = <项目>/ui/rail-map` |
| `start_ui.py:13` | `UI_SERVER = MOD_DIRECTORY/"tools"/"serve-rail-map.py"` |
| `build-workshop-package.ps1` | 白名单里写死 `mcp_server/`、精选 `tools/`、`ui/rail-map/` 平铺在工坊包根 |
| `deploy_mod_layers.bat` | 写死 `%PROJ%\tpf2_mod\res`、`%PROJ%\mcp_server`、`3_dashboard_ui/server/serve-rail-map.py`、`1_data_collection/exporters/export-layer-map.py` |

✅ 可行做法（**推荐**）：**源码分层、发布打平**。
四层是**开发仓库**的组织；`build-workshop-package.ps1` 负责把四层里的文件**重新组装**成工坊包需要的平铺形状。
代价是构建脚本要重写一版（唯一一处大改）。

### 3. `docs/code-wiki-map.json` 与 `AGENTS.md` 的扫描范围要同步
- `code-wiki-map.json` 有 **179 个文件路径键**（`mcp_server`52 / `tpf2_mod`51 / `tools`51 / `ui`19 / `protocol`6），搬迁后全部要改。
- 生成器 `build-code-wiki-index.py` 的 `SCOPE` 字典按顶层目录列举，要改成新四层。
- `AGENTS.md` 现在明写「保持 `tpf2_mod/` `mcp_server/` `ui/` `tools/` 职责分离」—— **与四层直接冲突**，必须改（见 §7 决策点 A）。
- `0_core_shared/index/build-data-inventory.py` 里扫接口调用也是按目录扫的，同理。

---

## 四、直接废弃清单

| 类别 | 内容 | 处置 |
|---|---|---|
| 一次性历史脚本 | `_archive/20260927_exploration/scripts/` 70 个 | **保留归档**（可查口径），或按决策点 D 删除 |
| 内存扫描路线 | `mem_*.py` 6 个 | 归档（已归）。**永不复活** |
| 存档解压路线 | `unzstd_save.js`、`_save/`、`_archive_save_20260927/` | 归档 |
| 重复的成本脚本 | `classify_vehicle_cost / probe_vehicle_cost / resolve_vehicle_cost / cost_per_train / build_cost_profile / scan_workshop_costs` | 归档；结论并进 `line-cost-profile.json` |
| 重复的车站模块脚本 | `station_modules / save_station_modules / _tmpdb/station_capacity` | 归档；职能归 `build-station-structures.py` |
| 顶层散落产物 | `sim_plan_V0/1/2.json`、`sim_snapshot_V0/1/2.json`、`vehicle_cost*.json`、`trunk_analysis*.txt`、`passenger_analysis.json`、`_dwell_probe.csv`、`_frame_*.json`、`_lv.json`、`_st.json`、`*_stdout.log` | 移到 `_archive/20260927_exploration/`（AGENTS.md 禁止这类文件进 Git） |
| 临时实验 | `_tmpdb/`（含 `app.js.bak`、`app.js.bak2`） | 挑出仍在用的搬走，其余清 |
| 文档叠版本 | `docs/snapshot-schema-v2/v3/v4/v5.md` | 合并成一份 `snapshot-schema.md` + 历史附表 |
| 重复入口 | `deploy_bugfix.bat`、`deploy_mod.bat`（与 `deploy_mod_layers.bat` 并存） | 确认无用后删 |
| 重复分位数/校验 | `_percentile`×2、`validate_parameters`×2、`_connect`×3 | **合并进共享模块**，不删功能 |

---

## 五、搬迁要同步改的引用点（**一处漏了 = 断链**）

| # | 文件 | 要改什么 |
|---|---|---|
| 1 | `deploy_mod_layers.bat` | 4 个路径：`tpf2_mod\res`、`mcp_server`、`3_dashboard_ui/server/serve-rail-map.py`、`1_data_collection/exporters/export-layer-map.py` |
| 2 | `rail-map-service.pyw` | `SERVICE_ENTRY`、`UI_DIRECTORY` |
| 3 | `mcp_server/start_ui.py` | `UI_SERVER`（第 13 行） |
| 4 | `mcp_server/start_server.py` | `sys.path` 指向新包位置 |
| 5 | `~/.workbuddy/mcp.json` | MCP 注册路径（若 `mcp_server/` 移动） |
| 6 | `0_core_shared/build/build-workshop-package.ps1` | 白名单 + 从四层打平组装（**最大一处**） |
| 7 | `docs/code-wiki-map.json` | 179 个路径键 |
| 8 | `tools/build-{code-wiki-index,data-inventory}.py` | `SCOPE` 扫描根 |
| 9 | `AGENTS.md` | 目录职责那一节 |
| 10 | `tpf2_mod/res/config/game_script/tpf2_mcp.lua` | `require` 路径 |
| 11 | `ui/rail-map/index.html` | 若前端搬走，`?v=` 与 script src |
| 12 | `collect_demand.bat`、`start_rail_map.bat` | 检查是否含旧路径 |

---

## 六、分四期执行

| 期 | 内容 | 风险 | 需要什么 |
|---|---|---|---|
| **P1** | **只做废弃**：归档顶层散落产物、`_tmpdb` 清理、文档叠版本合并、重复 bat 清理。**不碰任何代码路径** | 🟢 零 | 无 |
| **P2** | **建骨架 + 0 层落地**：建四个目录、写 `0_core_shared/ARCHITECTURE.md`（含契约路径表）、写 `schema/` 四个 schema、元工具/校验/构建脚本移入 0 层，同步改引用点 7/8/9 | 🟡 中 | 拍板 A |
| **P3** | **Python 分层**：tools/ 与 mcp_server/ 按 §2.2 归位；`server.py` 改 import；重写 `build-workshop-package.ps1`（打平组装）；改引用点 1–6 | 🔴 高（发布链路） | 拍板 B、C |
| **P4** | **Lua 分层 + 前端去重**：`res/scripts/tpf2_mcp/` 内建三层子目录、改 48 处 require、归档一次性探针；前端抽 `layer-shell.js` + `geo.js`，消掉 5+3+3+3 处重复 | 🟠 中高（要重启游戏验证） | 拍板 E、F ＋ 一次游戏重启 |
| **P5** | **执行层硬化**：`validator.py`、`approved_actions.json` 闸门、回滚、`audit_log.json` | 🟠 中 | 拍板 G（涉及写通道，当前 `allow_write_operations=false`） |

> ⚠️ **P3 与 P4 都不能和"当前在跑的链路"同时进行**：地图服务在跑、游戏可能要启动。
> 每期开始前先确认服务停掉，做完再起。

---

## 七、需要你拍板的 7 个点

| # | 问题 | 我的建议 |
|---|---|---|
| **A** | `AGENTS.md` 现在写着"保持 `tpf2_mod/ mcp_server/ ui/ tools/` 职责分离"，和四层冲突。改不改 AGENTS.md？ | **改**。它是上游作者的规约，本机仓库以你的四层为准；把"职责分离"那节改写成"四层 + 发布契约路径表" |
| **B** | 四层目录放在**项目根**，还是只做**逻辑分层**（物理路径不动）？ | **放项目根**（你原话），但 `tpf2_mod/`、`mcp_server/`、`ui/rail-map/` 三个**发布/加载契约路径保留**（§三） |
| **C** | `mcp_server/` 内部要不要真搬？搬了工坊包必须靠构建脚本重组装 | **搬**，但**分两步**：先搬 `analytics/planning/tasks/operations`（内部包，外部无引用），`server.py/start_*.py` 留在原位当壳 |
| **D** | `_archive/` 里 70 个历史脚本：留还是删？ | **留**。它们记录了 09-27 那批分析的口径（客货判据、时间基准、站台容量算法），删了以后没法复核 |
| **E** | 9 个一次性验证探针（`line_creation_probe / line_raw_probe / operations_probe / vehicle_write_probe / write_api_probe / ui_source_probe / route_probe / rail_network / station_geometry`）归档还是留？ | **逐个核对调用方后归档**。判据：`state.lua` 里还有没有它的命令分支、MCP 侧还有没有工具调它。**不一次性关掉**，先列清单给你过目 |
| **F** | 前端 `app.js`（局部视图）与 `network-app.js`（全网视图）是否合并成一个？ | **先不合并**，只抽公共件（`geo.js` + `layer-shell.js`）。两条页面线的差异还没收敛，硬并会出新 bug |
| **G** | 要不要现在就上 `validator.py` + `approved_actions.json` 闸门 + 回滚？ | **放到 P5**。当前 `allow_write_operations=false`、DLL 写通道未启用，闸门没有执行对象；先把前四层理顺 |

### 另外两个必须提前说清的约束

1. **`2_brain_analysis` 要求用 NetworkX / PuLP —— 目前项目没有任何第三方依赖。**
   `AGENTS.md` 明确禁止 `pip install --user` / 全局安装，工坊包也要求保持纯净。
   要引入就得：项目内建 `.venv`（开发用）＋ 决策 **这两个库要不要随发布包分发**（会显著增大包体，且绝大多数玩家用不到分析层）。
   **建议**：分析层依赖只在开发 `.venv` 里，发布包不分发 —— 因为 MCP 工具跑在用户机器上时确实需要它们，
   这点要你决定（见决策点，我会在 P2 开工前再确认一次）。
2. **「字段必须与 schema.json 严格一致」的正解是「复用优先」，不是「冻结」**（用户 2026-10-03 澄清）。

   原话：「我指的是不能随意发明新的字段，**不是完全静止**，是要**写之前看看有没有能复用的资源**」。

   ✅ 这条**不是新要求，也早就是项目硬规约** —— `AGENTS.md` 的「数据资产总账」一节原文就写着：
   「凡是为了拿某个数据而**新写 collector / probe / 字段**，必须先查 `docs/DATA_INVENTORY.md` 第零节」，
   并且**已经落成断言**（`build-data-inventory.py --check` 拦基线外的新接口调用，`--update-baseline` 留痕进 git diff）。

   ⇒ **四层架构要做的不是改这条，是继承它、把它的覆盖面补全。** 缺口只有一处：

   | 层 | 现在管不管 | 说明 |
   |---|---|---|
   | 引擎接口（Lua 调了哪些 system 方法） | ✅ 已管 | `docs/interface-baseline.json`，56 个，`--check` 强制 |
   | **产物字段（JSON 里出现哪些路径）** | ❌ 没管 | 有 **18,400 条字段路径**，但**没有"先查再写"的入口**，也没断言 |

   **补法（进 P2）**：在 `0_core_shared/` 建**产物字段索引**（从 `bridge/*.json` 自动抽取全部字段路径），
   新增采集器写字段前先查它；新字段必须登记，否则 `--check` 失败。
   规则一句话：**「新字段要么复用已有路径，要么登记说明为什么复用不了」** —— 探针产物同样适用，不设"自由档"。

---

## 附：体检数据出处

- 相似度/重名/同体：`_audit/dup_scan.py` → `_audit/dup_scan.json`（162 个文件全扫，可复跑）
- 接口利用率与"我想要→现成接口"表：`docs/DATA_INVENTORY.md`
- 代码↔官方文档索引：`docs/CODE_WIKI_INDEX.md`（179 文件 / 1098 函数）
- 目录契约：`AGENTS.md`、`deploy_mod_layers.bat`、`rail-map-service.pyw`、`mcp_server/start_ui.py`
