# 数据资产总账 与 交叉索引

> **本文件由 `0_core_shared/index/build-data-inventory.py` 自动生成，不要手改。**
> 要改内容 → 改代码/产物或脚本 → 重跑。

**这张表是干什么的**：回答「这个数据我到底有没有、从哪拿、用了没」。
立它的直接原因 —— 同一天里我两次没查账就造新探针：
`getSimPersonsForLine` 项目里早在用（`line_demand.lua:157`），
`world-probe.json` 里早 dump 了 31 个 system 的全部方法。**先查这里，再决定要不要新采。**

## 摘要

| 项 | 数 |
|---|---|
| 引擎 system（实测可用） | **31** 个 |
| 这些 system 的方法合计 | **116** 个 |
| 项目**实际调用**的接口（去重） | **59** 个 |
| 其中 system 方法 | **32** 个 |
| 组件类型（实测可用） | **102** 个 |
| bridge 产物 | **42** 个（17 MB） |
| 产物里出现过的字段路径 | **18400** 条 |

## 零、🎯「我想要这个数据」→「哪个现成接口能给」

**立这张表的直接原因**：反复犯同一个错 —— 想要某个数据时凭记忆觉得「应该没有」，
然后造新探针、加新字段；而接口一直在（`world-probe.json` 里躺着）。
同一天两次：`getSimPersonsForLine` 项目里早在用我却另写探针；
`getVehicle2Cargo2SimEntitesMap` 就是我要问的「车装了什么」，我也没查。

🔴 **规矩：凡是为了拿某个数据而写新采集/新探针之前，先查这张表。**

| 我想要 | 现成接口 | 用了吗 |
|---|---|---|
| 每辆车/每列车当前装了什么货（货种 → 数量）<br><sub>车辆装载</sub> | `simEntityAtVehicleSystem.getVehicle2Cargo2SimEntitesMap` | **❌ 没用过** |
| 车上乘客明细<br><sub>客运量</sub> | `simPersonAtVehicleSystem.getVehiclePartInfoList` | **❌ 没用过** |
| 车站候车人数 / 站台剩余容量<br><sub>车站候车量（R8）</sub> | `simPersonAtTerminalSystem.getNumFreePlaces` | **✔ 已用** |
| 站台货物占用 / 是否有空位 / 支持哪些货种<br><sub>站台压力</sub> | `simCargoAtTerminalSystem.getCount`<br>`getEntity`<br>`getMaxCount`<br>`getPlace`<br>`hasFreePlaces` | 部分 ✔ |
| 有问题的线路 + 问题类型<br><sub>运营诊断</sub> | `lineSystem.getProblemLines` | **✔ 已用** |
| 城镇的货物供给与上限<br><sub>城镇需求（R6）</sub> | `townBuildingSystem.getCargoSupplyAndLimit` | **❌ 没用过** |
| 城镇 ↔ 车站的对应关系<br><sub>城镇/车站分析</sub> | `stationSystem.getStation2TownMap`<br>`getTown2StationsMap` | **❌ 没用过** |
| 某种原料的来源厂<br><sub>产业链上游</sub> | `stockListSystem.getSources` | **❌ 没用过** |
| 库存实体枚举（按库存查实体）<br><sub>库存</sub> | `simEntityAtStockSystem.getStockEntities`<br>`getStockSimEntity` | **❌ 没用过** |
| 乘客总数<br><sub>客运量</sub> | `simPersonSystem.getCount` | **❌ 没用过** |
| 按目的地查在途乘客<br><sub>客运 OD</sub> | `simPersonSystem.getSimPersonsForDestination` | **❌ 没用过** |
| 线路的站点序列（含站台号）<br><sub>线路结构</sub> | `lineSystem.getLineStops`<br>`getTerminal2lineStops` | **❌ 没用过** |
| 停在某车站的所有线路<br><sub>车站分析</sub> | `lineSystem.getLineStopsForStation` | **❌ 没用过** |
| 停在某站台的所有线路<br><sub>站台压力</sub> | `lineSystem.getLineStopsForTerminal` | **❌ 没用过** |
| 我的所有线路<br><sub>线路清单</sub> | `lineSystem.getLinesForPlayer` | **❌ 没用过** |
| 路口 / 平交道口实体<br><sub>公铁立交</sub> | `railRoadCrossingSystem.getRailroadCrossingForEdge`<br>`ForNode` | **❌ 没用过** |
| 街区（parcel）数据<br><sub>城镇地理</sub> | `parcelSystem.getParcelData`<br>`getSegment2ParcelData` | **❌ 没用过** |
| 城镇建筑 / 人口容量分布<br><sub>城镇需求</sub> | `townBuildingSystem.getTown2BuildingMap`<br>`getPersonCapacity2townBuildingMap` | **❌ 没用过** |
| 任意设施 → 它的建筑实体<br><sub>设施↔建筑</sub> | `streetConnectorSystem.getConstructionEntityForStation`<br>`ForEdge`<br>`ForDepot`<br>`ForSimBuilding` | **❌ 没用过** |
| 水体网格实体<br><sub>地形/水运</sub> | `riverSystem.getWaterMeshEntities` | **❌ 没用过** |
| 跑道起降节点<br><sub>机场结构</sub> | `runwaySystem.getLandingNodeIdMap`<br>`getTakeoffNodeIdMap` | **❌ 没用过** |

## 一、🔴 现成但**没用过**的接口（全量）

下面这些是 `world-probe.json` 实测存在、而项目代码里**一次都没调用**的。
要新数据时先扫一遍 —— 很可能已经有现成的。

**`aircraftMoveSystem`** ｜ 3 个方法，用了 0 个，**没用 3 个**：

```
  forEach
  getAirCraftInfo
  isReserved
```

**`animalMoveSystem`** ｜ 1 个方法，用了 0 个，**没用 1 个**：

```
  forEach
```

**`baseParallelStripSystem`** ｜ 1 个方法，用了 0 个，**没用 1 个**：

```
  getStrips
```

**`catchmentAreaSystem`** ｜ 3 个方法，用了 1 个，**没用 2 个**：

```
  getEdge2stationsMap
  getStation2edgesMap
```

**`lineSystem`** ｜ 9 个方法，用了 2 个，**没用 7 个**：

```
  getLineStops
  getLineStopsForStation
  getLineStopsForTerminal
  getLinesForPlayer
  getLinesForWaypoint
  getStationGroup2LineStopsMap
  getTerminal2lineStops
```

**`octreeSystem`** ｜ 1 个方法，用了 0 个，**没用 1 个**：

```
  findIntersectingEntities
```

**`parcelSystem`** ｜ 2 个方法，用了 0 个，**没用 2 个**：

```
  getParcelData
  getSegment2ParcelData
```

**`railRoadCrossingSystem`** ｜ 2 个方法，用了 0 个，**没用 2 个**：

```
  getRailroadCrossingForEdge
  getRailroadCrossingForNode
```

**`riverSystem`** ｜ 1 个方法，用了 0 个，**没用 1 个**：

```
  getWaterMeshEntities
```

**`runwaySystem`** ｜ 2 个方法，用了 0 个，**没用 2 个**：

```
  getLandingNodeIdMap
  getTakeoffNodeIdMap
```

**`shipMoveSystem`** ｜ 2 个方法，用了 0 个，**没用 2 个**：

```
  forEach
  getShipInfo
```

**`signalSystem`** ｜ 1 个方法，用了 0 个，**没用 1 个**：

```
  getSignal
```

**`simCargoAtTerminalSystem`** ｜ 6 个方法，用了 2 个，**没用 4 个**：

```
  getEntity
  getPlace
  hasFreePlaces
  supportsCargoType
```

**`simCargoSystem`** ｜ 5 个方法，用了 4 个，**没用 1 个**：

```
  getSimCargoIdleForTransportNetwork
```

**`simEntityAtStockSystem`** ｜ 4 个方法，用了 2 个，**没用 2 个**：

```
  getStockEntities
  getStockSimEntity
```

**`simEntityAtVehicleSystem`** ｜ 2 个方法，用了 1 个，**没用 1 个**：

```
  getVehicle2Cargo2SimEntitesMap
```

**`simPersonAtTerminalSystem`** ｜ 3 个方法，用了 1 个，**没用 2 个**：

```
  getEdgeInfoMap
  getPos01
```

**`simPersonAtVehicleSystem`** ｜ 1 个方法，用了 0 个，**没用 1 个**：

```
  getVehiclePartInfoList
```

**`simPersonSystem`** ｜ 8 个方法，用了 4 个，**没用 4 个**：

```
  getCount
  getSimPersonsForDestination
  getSimPersonsForTarget
  getSimPersonsMovingForTransportNetwork
```

**`stationGroupSystem`** ｜ 3 个方法，用了 0 个，**没用 3 个**：

```
  getExpiredStationGroups
  getExpiryProgress
  getStationGroup
```

**`stationSystem`** ｜ 10 个方法，用了 4 个，**没用 6 个**：

```
  forEach
  getStation2TownMap
  getStationTerminalForVehicleNode
  getStationTerminalsForPersonEdge
  getTown
  getTown2StationsMap
```

**`stockListSystem`** ｜ 2 个方法，用了 1 个，**没用 1 个**：

```
  getSources
```

**`streetConnectorSystem`** ｜ 9 个方法，用了 1 个，**没用 8 个**：

```
  forEach
  getConstructionEntityForDepot
  getConstructionEntityForEdge
  getConstructionEntityForSimBuilding
  getConstructionEntityForStation
  getConstructionEntityForTownBuilding
  getNode2StreetConnectorMap
  getStreetConnectorEntity
```

**`streetSystem`** ｜ 5 个方法，用了 0 个，**没用 5 个**：

```
  getEdgeForEdgeObject
  getEdgeObject2EdgeMap
  getNode2SegmentMap
  getNode2StreetEdgeMap
  getNode2TrackEdgeMap
```

**`townBuildingSystem`** ｜ 8 个方法，用了 1 个，**没用 7 个**：

```
  getBuilding
  getCargoSupplyAndLimit
  getParcel2BuildingMap
  getPersonCapacity2townBuildingMap
  getTown2BuildingMap
  getTown2personCapacitiesMap
  hasBuilding
```

**`tpNetLinkSystem`** ｜ 2 个方法，用了 0 个，**没用 2 个**：

```
  getEdgeId2linkEntities
  getLinkEntities
```

**`trainMoveSystem`** ｜ 4 个方法，用了 0 个，**没用 4 个**：

```
  forEach
  getBlockedTrains
  getTrainInfo
  getVehicleInfo
```

**`transportHistorySystem`** ｜ 2 个方法，用了 0 个，**没用 2 个**：

```
  getStationTransportHistoryReferences
  getTargetTransportHistoryReferences
```

**`transportVehicleSystem`** ｜ 10 个方法，用了 3 个，**没用 7 个**：

```
  getDepotVehicles
  getGoingToDepotVehicles
  getLine2VehicleMap
  getLineStopVehicles
  getNoPathVehicles
  getVehicleNames
  getVehiclesWithState
```

**`vehicleDepotSystem`** ｜ 2 个方法，用了 0 个，**没用 2 个**：

```
  forEach
  getDepotForInNodeId
```


## 二、接口 → 谁在用（正向索引）

| 接口 | 调用处 |
|---|---|
| `api.engine.component.TRANSPORT_VEHICLE` | `tpf2_mod/res/scripts/tpf2_mcp/state.lua:81` |
| `api.engine.getComponent` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/common.lua:86`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/component_access.lua:36`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_finance_probe.lua:325` …（共 10 处） |
| `api.engine.system.catchmentAreaSystem.getStation2stationsAndDistancesMap` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_stations.lua:265` |
| `api.engine.system.lineSystem.getLines` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_passenger.lua:56`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_finance_probe.lua:334` |
| `api.engine.system.lineSystem.getProblemLines` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:344`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:348` |
| `api.engine.system.simCargoAtTerminalSystem.getCount` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/terminal_waiting_probe.lua:176` |
| `api.engine.system.simCargoAtTerminalSystem.getMaxCount` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/terminal_waiting_probe.lua:180` |
| `api.engine.system.simCargoSystem.getSimCargoAtTerminalForTransportNetwork` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:747` |
| `api.engine.system.simCargoSystem.getSimCargosForLine` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:284`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_demand.lua:158` |
| `api.engine.system.simCargoSystem.getSimCargosForSource` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:796` |
| `api.engine.system.simCargoSystem.getSimCargosForTarget` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:799` |
| `api.engine.system.simEntityAtStockSystem.getStock2SimEntityMap` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:383`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_industry.lua:104` |
| `api.engine.system.simEntityAtStockSystem.getStockCount` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:423` |
| `api.engine.system.simEntityAtVehicleSystem.getFare` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:260` |
| `api.engine.system.simPersonAtTerminalSystem.getNumFreePlaces` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/terminal_waiting_probe.lua:145`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/terminal_waiting_probe.lua:153` |
| `api.engine.system.simPersonSystem.getDestination2SpMap` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:725` |
| `api.engine.system.simPersonSystem.getSimPersonsAtTerminalForTransportNetwork` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:741` |
| `api.engine.system.simPersonSystem.getSimPersonsForLine` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:291`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_demand.lua:157` |
| `api.engine.system.simPersonSystem.getSimPersonsIdleForTransportNetwork` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:744` |
| `api.engine.system.stationSystem.getPersonNodeId2StationTerminalsMap` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:616`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:675` |
| `api.engine.system.stationSystem.getStationTerminalsForPersonNode` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:699` |
| `api.engine.system.stationSystem.getStations` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:713` |
| `api.engine.system.stationSystem.getVehicleNodeId2StationTerminalsMap` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:707` |
| `api.engine.system.stockListSystem.getCargoType2stockList2sourceAndCount` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_finance_probe.lua:416` |
| `api.engine.system.streetConnectorSystem.getStation2ConstructionMap` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_lines.lua:88`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_stations.lua:135`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_stations.lua:538` …（共 4 处） |
| `api.engine.system.townBuildingSystem.getLandUsePersonCapacities` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/town.lua:15` |
| `api.engine.system.transportNetworkSystem.getIntersections` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:758` |
| `api.engine.system.transportNetworkSystem.getTpNetData` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:755` |
| `api.engine.system.transportVehicleSystem.getInfo` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/dynamic_probe.lua:36` |
| `api.engine.system.transportVehicleSystem.getLineVehicles` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:283`、`tpf2_mod/res/scripts/tpf2_mcp/operations/timetable_controller.lua:175` |
| `api.engine.system.transportVehicleSystem.getVehicles` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_finance_probe.lua:404` |
| `api.engine.util.getPlayer` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/company.lua:21`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/company.lua:35`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:143` …（共 11 处） |
| `api.engine.util.getTransportedData` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:259` |
| `api.engine.util.getWorld` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua:144`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_passenger.lua:46`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_road_traffic.lua:441` …（共 9 处） |
| `api.res.cargoTypeRep.getAll` | `tpf2_mod/res/scripts/tpf2_mcp/state.lua:80` |
| `api.res.constructionRep.get` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:396` |
| `api.res.constructionRep.getAll` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:379` |
| `api.res.moduleRep.get` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:366` |
| `api.res.moduleRep.getAll` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:349` |
| `api.res.moduleRep.getFileName` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:376` |
| `api.res.moduleRep.getName` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua:375` |
| `api.type.ComponentType` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/common.lua:75`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/world_probe.lua:172` |
| `api.type.ComponentType.GAME_TIME` | `tpf2_mod/res/scripts/tpf2_mcp/operations/timetable_controller.lua:19` |
| `api.type.ComponentType.LINE` | `tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua:85`、`tpf2_mod/res/scripts/tpf2_mcp/operations/line_stop_builder.lua:92` |
| `api.type.ComponentType.TRANSPORT_VEHICLE` | `tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua:131`、`tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua:169`、`tpf2_mod/res/scripts/tpf2_mcp/operations/timetable_controller.lua:180` |
| `api.type.Line` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:6`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:68`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:91` …（共 4 处） |
| `api.type.Line.Stop` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:91` |
| `api.type.Line.Stop.new` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:91` |
| `api.type.Line.new` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:6`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:31`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:51` …（共 8 处） |
| `api.type.LineStop` | `tpf2_mod/res/scripts/tpf2_mcp/operations/line_stop_builder.lua:24` |
| `api.type.LineStop.new` | `tpf2_mod/res/scripts/tpf2_mcp/operations/line_stop_builder.lua:24` |
| `api.type.StationTerminal` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line.lua:58` |
| `api.type.Vec3f` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:58` |
| `api.type.Vec3f.new` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua:58`、`tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua:73`、`tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua:92` |
| `game.interface.getEntity` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/demand_probe.lua:149`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/dynamic_probe.lua:95`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/dynamic_probe.lua:96` …（共 21 处） |
| `game.interface.getGameTime` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/world_probe.lua:461` |
| `game.interface.getHeight` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_stations.lua:60`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_terrain.lua:68`、`tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_terrain.lua:309` …（共 5 处） |
| `game.interface.getStations` | `tpf2_mod/res/scripts/tpf2_mcp/collectors/operational_telemetry.lua:386` |
| `game.interface.setName` | `tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua:215` |

## 三、产物 → 字段（反向索引）

> 超大产物（>40 MB）只列顶层键，不展开。

| 产物 | 大小 | 顶层键 / 关键字段 |
|---|---|---|
| `rail-network.json` | 4.7 MB | `surroundings_diagnostics`, `overhead_diagnostics`, `edges`, `schema_version`, `nodes`, `lines`, `source_status`, `stations`, `errors`, `depots` ／ **94 条字段路径** |
| `layer-road.json` | 3.7 MB | `schema_version`, `counts`, `edges`, `nodes`, `street_types`, `sampled_at_update`, `status`, `geometry_kind`, `structures`, `source_status` ／ **82 条字段路径** |
| `layer-freight.json` | 1.4 MB | `sample`, `schema_version`, `counts`, `sampled_at_update`, `industry_index`, `status`, `duration_ms`, `geometry_kind`, `source_status`, `coord_source` ／ **53 条字段路径** |
| `state.json` | 1.2 MB | `schema_version`, `simulation`, `vehicles`, `metadata`, `game`, `lines`, `towns`, `sequence`, `company`, `cargo_types` ／ **116 条字段路径** |
| `operational-telemetry-signals.json` | 1.1 MB | `track_edge_objects`, `errors`, `duration_ms`, `counts`, `schema_version`, `probe_kind`, `generated_at`, `write_command_sent`, `signals`, `source_status` ／ **76 条字段路径** |
| `station-struct-probe.json` | 1.1 MB | `schema_version`, `duration_ms`, `errors`, `load_probe_v5`, `load_probe`, `probe_kind`, `question`, `stations_emitted`, `station_group_count`, `source_status` ／ **194 条字段路径** |
| `operational-telemetry-vehicles_live.json` | 669 KB | `errors`, `duration_ms`, `counts`, `schema_version`, `probe_kind`, `vehicles`, `simulation_clock`, `write_command_sent`, `source_status`, `generated_at` ／ **41 条字段路径** |
| `layer-road-traffic.json` | 621 KB | `counts`, `calibration`, `status`, `duration_ms`, `geometry_kind`, `schema_version`, `sampled_at_update`, `vehicles`, `summary`, `sample_interval_seconds` ／ **92 条字段路径** |
| `rail-control-state.json` | 430 KB | `schema_version`, `source_status`, `sampled_at`, `signals`, `blocks`, `counts` ／ **26 条字段路径** |
| `layer-stations.json` | 354 KB | `clusters`, `schema_version`, `counts`, `stations`, `status`, `diagnostics`, `sampled_at_update`, `source_status`, `geometry_kind`, `layer` ／ **70 条字段路径** |
| `layer-vehicles.json` | 211 KB | `by_carrier_raw`, `counts`, `sampled_at_update`, `truncated`, `by_position_source`, `schema_version`, `status`, `geometry_kind`, `layer`, `source_status` ／ **50 条字段路径** |
| `layer-lines.json` | 194 KB | `schema_version`, `counts`, `by_carrier`, `sampled_at_update`, `status`, `diagnostics`, `kind`, `source_status`, `layer`, `by_cargo` ／ **53 条字段路径** |
| `layer-terrain.json` | 192 KB | `grid`, `schema_version`, `counts`, `status`, `diagnostics`, `heights`, `geometry_kind`, `sampled_at_update`, `errors`, `layer` ／ **57 条字段路径** |
| `demand-probe.json` | 147 KB | `last_unhandled`, `schema_version`, `last_write`, `first_tick_done`, `entity_inventory`, `persons_seen`, `cargo_samples`, `cargo_seen`, `errors`, `phase` ／ **12242 条字段路径** |
| `world-probe.json` | 137 KB | `extra_namespaces`, `walk_budget_hit`, `probe_kind`, `component_names_resolved_count`, `system_methods`, `write_command_sent`, `get_entity_selfcheck`, `total_entities_walked`, `note`, `res_count` ／ **1057 条字段路径** |
| `economy-probe.json` | 86 KB | `schema_version`, `components_present`, `duration_ms`, `errors`, `counts`, `unverified`, `probe_kind`, `question`, `stock`, `source_status` ／ **144 条字段路径** |
| `live-rail-state.json` | 74 KB | `schema_version`, `source_status`, `sampled_at`, `simulation`, `vehicles`, `line_diagnostics`, `counts`, `limitations`, `air_vehicles`, `water_vehicles` ／ **98 条字段路径** |
| `context-probe.json` | 62 KB | `game_type`, `get_entity_type`, `lines`, `context`, `get_entity_ok`, `stations`, `vehicles`, `get_player_ok`, `interface_type`, `player_fields` ／ **54 条字段路径** |
| `line-demand-live.json` | 61 KB | `schema_version`, `source_status`, `written_at`, `sweep`, `lines`, `cargo_history` ／ **1955 条字段路径** |
| `layer-industry.json` | 51 KB | `stock_probe`, `counts`, `stock_stats`, `points`, `status`, `sampled_at_update`, `schema_version`, `source_status`, `geometry_kind`, `layer` ／ **62 条字段路径** |
| `route-probe.json` | 49 KB | `duration_ms`, `ship_move_system`, `errors`, `aircraft_move_system`, `system_names`, `source_status`, `write_command_sent`, `ship_components`, `ship_sample_entity_id`, `system_type` ／ **1504 条字段路径** |
| `dynamic-transport-probe.json` | 11 KB | `town_station_relation`, `industry_semantics`, `station_terminal_mapping`, `vehicle_load` ／ **38 条字段路径** |
| `vehicle-write-api-probe.json` | 10 KB | `command_candidates`, `limitations`, `game_interface`, `probe_errors`, `probe_kind`, `api_cmd`, `unassign_candidate`, `depot_samples`, `write_command_sent`, `api_types` ／ **114 条字段路径** |
| `api-type-inventory.json` | 9 KB | `probe_kind`, `api_type` ／ **6 条字段路径** |
| `operations-probe.json` | 7 KB | `company`, `station`, `industry`, `cargo_registry`, `vehicle` ／ **32 条字段路径** |
| `layer-town.json` | 7 KB | `schema_version`, `counts`, `towns`, `sampled_at_update`, `status`, `duration_ms`, `geometry_kind`, `source_status`, `shape_report`, `layer` ／ **75 条字段路径** |
| `semantic-probe.json` | 4 KB | `lines`, `vehicles`, `industries` ／ **18 条字段路径** |
| `api-command-inventory.json` | 4 KB | `probe_kind`, `api_cmd_make` ／ **7 条字段路径** |
| `line-raw-probe.json` | 4 KB | `write_command_sent`, `samples`, `sample_limit`, `errors` ／ **12 条字段路径** |
| `line-creation-probe.json` | 3 KB | `signatures`, `mutable_native_stop_vector`, `constructed_native_stop`, `likely_types`, `probe_kind`, `color`, `write_command_sent`, `native_stop_copy`, `stop_descriptor`, `nested_stop_type` ／ **117 条字段路径** |
| `ui-source-probe.json` | 2 KB | `systems`, `errors`, `vehicle_samples`, `repositories` ／ **56 条字段路径** |
| `heartbeat.json` | 1 KB | `bridge_ready`, `schema_version`, `bridge_dir`, `game_running`, `path_resolution`, `mod_dir`, `probe`, `module_path`, `last_update`, `snapshot_seq` ／ **71 条字段路径** |
| `write-api-probe.json` | 0 KB | `limitations`, `api_cmd_make`, `write_command_sent`, `api_cmd`, `game_interface_set_name`, `api_cmd_send_command`, `probe_kind`, `game_interface` |
| `company-probe.json` | 0 KB | `components`, `player_entity` ／ **5 条字段路径** |
| `station-geometry.json` | 0 KB | `error`, `write_command_sent`, `status` |
| `command.json` | 0 KB | `schema_version`, `request_id`, `command`, `params`, `timestamp` ／ **6 条字段路径** |
| `operational-telemetry-progress.json` | 0 KB | `completed_at`, `status`, `counts`, `section` ／ **5 条字段路径** |
| `probe-write.json` | 0 KB | `` ／ **1 条字段路径** |
| `probe-absolute.json` | 0 KB | `` ／ **1 条字段路径** |
| `newtest.json` | 0 KB | `` ／ **1 条字段路径** |
| `probe2.json` | 0 KB | `` ／ **1 条字段路径** |
| `write-test.json` | 0 KB | `` ／ **1 条字段路径** |

## 四、字段 → 在哪些产物里（跨产物找同一个数据）

只看**出现在 2 个以上产物**里的字段（说明它有多处来源，改的时候别漏）——
单产物独有的字段太多，去第三节按产物查。

| 字段路径 | 出现在 |
|---|---|
| `schema_version` | `command.json`、`demand-probe.json`、`economy-probe.json`、`heartbeat.json`、`layer-freight.json` |
| `source_status` | `demand-probe.json`、`economy-probe.json`、`layer-freight.json`、`layer-industry.json`、`layer-lines.json` |
| `errors` | `demand-probe.json`、`economy-probe.json`、`layer-freight.json`、`layer-industry.json`、`layer-lines.json` |
| `counts` | `economy-probe.json`、`layer-freight.json`、`layer-industry.json`、`layer-lines.json`、`layer-road-traffic.json` |
| `status` | `economy-probe.json`、`layer-freight.json`、`layer-industry.json`、`layer-lines.json`、`layer-road-traffic.json` |
| `probe_kind` | `api-command-inventory.json`、`api-type-inventory.json`、`economy-probe.json`、`line-creation-probe.json`、`operational-telemetry-signals.json` |
| `write_command_sent` | `line-creation-probe.json`、`line-raw-probe.json`、`operational-telemetry-signals.json`、`operational-telemetry-vehicles_live.json`、`rail-network.json` |
| `sampled_at_update` | `layer-freight.json`、`layer-industry.json`、`layer-lines.json`、`layer-road-traffic.json`、`layer-road.json` |
| `geometry_kind` | `layer-freight.json`、`layer-industry.json`、`layer-lines.json`、`layer-road-traffic.json`、`layer-road.json` |
| `layer` | `layer-freight.json`、`layer-industry.json`、`layer-lines.json`、`layer-road-traffic.json`、`layer-road.json` |
| `kind` | `layer-freight.json`、`layer-industry.json`、`layer-lines.json`、`layer-road-traffic.json`、`layer-road.json` |
| `duration_ms` | `economy-probe.json`、`layer-freight.json`、`layer-road-traffic.json`、`layer-town.json`、`operational-telemetry-signals.json` |
| `counts.total` | `layer-industry.json`、`layer-lines.json`、`layer-road-traffic.json`、`layer-road.json`、`layer-stations.json` |
| `lines` | `context-probe.json`、`economy-probe.json`、`layer-lines.json`、`line-demand-live.json`、`rail-network.json` |
| `vehicles` | `context-probe.json`、`layer-road-traffic.json`、`live-rail-state.json`、`operational-telemetry-vehicles_live.json`、`semantic-probe.json` |
| `__read_error__` | `newtest.json`、`probe-absolute.json`、`probe-write.json`、`probe2.json`、`write-test.json` |
| `stations` | `context-probe.json`、`layer-stations.json`、`rail-network.json`、`state.json` |
| `counts.scanned` | `layer-industry.json`、`layer-road.json`、`layer-town.json`、`layer-vehicles.json` |
| `diagnostics` | `layer-lines.json`、`layer-road-traffic.json`、`layer-stations.json`、`layer-terrain.json` |
| `api_cmd_make` | `api-command-inventory.json`、`vehicle-write-api-probe.json`、`write-api-probe.json` |
| `game_time` | `economy-probe.json`、`layer-road-traffic.json`、`world-probe.json` |
| `counts.skipped` | `layer-industry.json`、`layer-road.json`、`layer-vehicles.json` |
| `field_probe` | `layer-industry.json`、`layer-road.json`、`layer-vehicles.json` |
| `counts.vehicles` | `layer-lines.json`、`operational-telemetry-progress.json`、`operational-telemetry-vehicles_live.json` |
| `lines.[].name` | `layer-lines.json`、`rail-network.json`、`state.json` |
| `lines.[].entity_id` | `layer-lines.json`、`rail-network.json`、`state.json` |
| `lines.[].stops` | `layer-lines.json`、`rail-network.json`、`state.json` |
| `sampled_at` | `layer-road-traffic.json`、`live-rail-state.json`、`rail-control-state.json` |
| `stations.[].name` | `layer-stations.json`、`rail-network.json`、`state.json` |
| `stations.[].entity_id` | `layer-stations.json`、`rail-network.json`、`state.json` |
| `note` | `layer-town.json`、`route-probe.json`、`world-probe.json` |
| `vehicles.[].entity_id` | `live-rail-state.json`、`operational-telemetry-vehicles_live.json`、`state.json` |
| `vehicles.[].name` | `live-rail-state.json`、`operational-telemetry-vehicles_live.json`、`state.json` |
| `vehicles.[].line_id` | `live-rail-state.json`、`operational-telemetry-vehicles_live.json`、`state.json` |
| `vehicles.[].raw_state` | `live-rail-state.json`、`operational-telemetry-vehicles_live.json`、`state.json` |
| `limitations` | `live-rail-state.json`、`vehicle-write-api-probe.json`、`write-api-probe.json` |
| `section` | `operational-telemetry-progress.json`、`operational-telemetry-signals.json`、`operational-telemetry-vehicles_live.json` |
| `generated_at` | `operational-telemetry-signals.json`、`operational-telemetry-vehicles_live.json`、`route-probe.json` |
| `timestamp` | `command.json`、`state.json` |
| `lines.samples` | `context-probe.json`、`semantic-probe.json` |
| `lines.samples.[].entity_id` | `context-probe.json`、`semantic-probe.json` |
| `vehicles.samples` | `context-probe.json`、`semantic-probe.json` |
| `vehicles.samples.[].entity_id` | `context-probe.json`、`semantic-probe.json` |
| `counts.lines_seen` | `economy-probe.json`、`layer-lines.json` |
| `question` | `economy-probe.json`、`station-struct-probe.json` |
| `systems` | `economy-probe.json`、`ui-source-probe.json` |
| `systems.transportVehicleSystem` | `economy-probe.json`、`ui-source-probe.json` |
| `systems.simCargoSystem` | `economy-probe.json`、`ui-source-probe.json` |
| `systems.lineSystem` | `economy-probe.json`、`ui-source-probe.json` |
| `counts.links` | `layer-freight.json`、`layer-stations.json` |
| `links` | `layer-freight.json`、`layer-stations.json` |
| `counts.no_bounds` | `layer-industry.json`、`layer-vehicles.json` |
| `counts.points` | `layer-industry.json`、`layer-vehicles.json` |
| `points` | `layer-industry.json`、`layer-vehicles.json` |
| `points.[].entity_id` | `layer-industry.json`、`layer-vehicles.json` |
| `points.[].position` | `layer-industry.json`、`layer-vehicles.json` |
| `points.[].position.x` | `layer-industry.json`、`layer-vehicles.json` |
| `points.[].position.y` | `layer-industry.json`、`layer-vehicles.json` |
| `points.[].position.z` | `layer-industry.json`、`layer-vehicles.json` |
| `counts.lines` | `layer-lines.json`、`rail-network.json` |
| `by_carrier` | `layer-lines.json`、`layer-vehicles.json` |
| `by_carrier.AIR` | `layer-lines.json`、`layer-vehicles.json` |
| `by_carrier.WATER` | `layer-lines.json`、`layer-vehicles.json` |
| `by_carrier.ROAD` | `layer-lines.json`、`layer-vehicles.json` |
| `lines.[].stop_count` | `layer-lines.json`、`state.json` |
| `counts.edges` | `layer-road.json`、`rail-network.json` |
| `counts.nodes` | `layer-road.json`、`rail-network.json` |
| `edges` | `layer-road.json`、`rail-network.json` |
| `edges.[].node1` | `layer-road.json`、`rail-network.json` |
| `edges.[].node0` | `layer-road.json`、`rail-network.json` |
| `edges.[].structure` | `layer-road.json`、`rail-network.json` |
| `edges.[].tangent1` | `layer-road.json`、`rail-network.json` |
| `edges.[].tangent1.x` | `layer-road.json`、`rail-network.json` |
| `edges.[].tangent1.y` | `layer-road.json`、`rail-network.json` |
| `edges.[].tangent1.z` | `layer-road.json`、`rail-network.json` |
| `edges.[].structure_index` | `layer-road.json`、`rail-network.json` |
| `edges.[].entity_id` | `layer-road.json`、`rail-network.json` |
| `edges.[].tangent0` | `layer-road.json`、`rail-network.json` |
| `edges.[].tangent0.x` | `layer-road.json`、`rail-network.json` |
| `edges.[].tangent0.y` | `layer-road.json`、`rail-network.json` |

（共 125 条跨产物字段，上面按出现次数排前 80）

## 五、代码 ↔ 官方文档（并入 `CODE_WIKI_INDEX.md` 的口径）

| 文件 | 干什么 | 官方出处 |
|---|---|---|
| `0_core_shared/build-fields-index.py` | **产物字段索引生成器**：扫 `bridge/*.json` 抽出全部字段路径 → 落成 `0_core_shared | `SELF` |
| `0_core_shared/build/build-phase10-evidence.ps1` | Phase 10 证据集构建脚本 | `SELF` |
| `0_core_shared/build/build-phase9-evidence.ps1` | Phase 9 证据集构建脚本 | `SELF` |
| `0_core_shared/build/build-release-package.py` | 打可复现的发布包（单一 `tpf2-mcp/` 根） | `MD:publishing` |
| `0_core_shared/build/build-workshop-package.ps1` | 打自包含的创意工坊 mod 包（含**逐文件白名单**） | `MD:publishing`、`MD:modcomponents`、`MD:modvalidator` |
| `0_core_shared/build/collect-diagnostics.ps1` | 收集诊断材料 | `SELF` |
| `0_core_shared/build/install-mod.ps1` | 把 mod 装进 staging（游戏真正加载的位置） | `MD:publishing`、`GM:modinstallation` |
| `0_core_shared/checks/validate-snapshot.py` | 校验世界快照是否符合 schema | `SELF` |
| `0_core_shared/checks/verify-network-semantics.py` | 核对网络字段语义 | `API:type` |
| `0_core_shared/checks/verify-release-package.py` | 解包、校验布局、跑离线测试 | `MD:modvalidator` |
| `0_core_shared/checks/verify-ui-ground-truth.py` | 用游戏界面截图口径核对前端取数 | `SELF` |
| `0_core_shared/index/build-code-wiki-index.py` | **本索引的生成器 + 覆盖率校验器**：扫源码/函数 → 按映射表生成 docs/CODE_WIKI_INDEX.md | `SELF` |
| `0_core_shared/index/build-data-inventory.py` | 生成「数据资产总账 + 交叉索引」→ `docs/DATA_INVENTORY.md`：引擎接口利用率、接口→使用者、产 | `SELF` |
| `0_core_shared/index/index-tpf2-lua-sources.py` | 给游戏本体 `res/scripts` 下的 Lua 源码建索引（查官方实现用） | `SRC` |
| `1_data_collection/exporters/build-cargo-types.py` | 从游戏文件抽货种定义 → `cargo-types.json` | `MD:cargotypes` |
| `1_data_collection/exporters/build-road-geometry.py` | 抽公路边几何 → `road-edge-geometry.json`（路况图层用） | `API:type` |
| `1_data_collection/exporters/build-station-structures.py` | 四类站结构反解：slotId → 网格坐标 → 世界坐标，输出 layers/station-structures.js | `MD:modularconstructions`、`SRC`、`PN` |
| `1_data_collection/exporters/export-layer-map.py` | 把 mod 自驱推送的图层数据切块成 manifest + tiles | `SELF` |
| `1_data_collection/exporters/export-physical-station-map.py` | 归一化引擎观测到的铁路几何，给独立 SVG viewer 用 | `SELF` |
| `1_data_collection/exporters/export-rail-network-map.py` | 一次性引擎铁路导出 → 浏览器调度图的数据 | `SELF` |
| `1_data_collection/exporters/export-static-station-map.py` | 导出只读的车站/线路邻域给独立 SVG UI | `SELF` |
| `1_data_collection/exporters/extract-industry-icons.py` | 从游戏资源里抽产业/货种**原版图标**（手写 TGA 解码）→ `icons/*.png` | `MD:resourcetypes_mdl` |
| `1_data_collection/exporters/extract-industry-recipes.py` | 从游戏 `.con` 抽产业配方『原料 → 产品』＋ **每年最大产量** → `ui/rail-map/industr | `GM:industriescargos` |
| `1_data_collection/probes/collect-line-demand.py` | 把乘客/货运需求采进本地 SQLite 历史 | `SELF` |
| `2_brain_analysis/analyze-line-economics.py` | 按官方收入公式算每条线的收入（权重分摊版）：直线距离 × 每公里价 × 载量 → 权重 → 把账本实测的运输总收入分摊到 | `GM:tipstricks`、`GM:linesvehicles`、`API:type`、`SRC`、`SAVE` |
| `2_brain_analysis/analyze-operational-telemetry.py` | 把实时遥测发现结果汇总成一张「就绪矩阵」 | `SELF` |
| `2_brain_analysis/build-line-timetable-plan.py` | 从当前导出证据构一份**默认禁用**的时刻表方案 | `GM:linesvehicles` |
| `2_brain_analysis/diagnose-industries.py` | 产业运转诊断（2026-10-02 重写）：判「这家厂是在正常出货，还是货堆着没人运」，输出 停摆 / 无流量 / 没人 | `GM:industriescargos`、`GM:towns` |
| `2_brain_analysis/find_deadlock_risks.py` | 从拓扑找铁路**死锁风险**：单线走廊、站台净空、袋形股道 | `GM:railwaysignals`、`DG:06` |
| `2_brain_analysis/record-and-optimize-dwell.py` | 录实时铁路帧 → 出保守的停站策略方案 | `GM:stationsdepots` |
| `3_dashboard_ui/server/serve-rail-map.py` | 本地只读 HTTP/SSE 服务，供铁路调度图页面取数 | `SELF` |
| `4_execution_control/acceptance/test-dispatch-hold-live.py` | 单个车辆「扣住再放行」的实机最小复现 | `API:cmd` |
| `4_execution_control/acceptance/test-dispatch-task-live.py` | 通过 Task 层验证扣住/放行 | `API:cmd` |
| `4_execution_control/acceptance/test-final-planner-live.py` | 采集只读证据供「自动选线路」规划用 | `SELF` |
| `4_execution_control/acceptance/test-final-task-gate-live.py` | 验证「改线/排班/买车/卖车」只能走 Task 闸门 | `API:cmd` |
| `4_execution_control/acceptance/test-live-bridge.ps1` | bridge 连通性实机测试 | `SELF` |
| `4_execution_control/acceptance/test-live-mcp.ps1` | MCP 工具集实机测试 | `SELF` |
| `4_execution_control/acceptance/test-phase11-live.py` | Phase 11 改名/回滚验收（**仅专用存档**） | `API:cmd` |
| `4_execution_control/acceptance/test-phase12-live.py` | Phase 12 任务编排验收（仅专用存档） | `SELF` |
| `4_execution_control/acceptance/test-phase13-assign-live.py` | 一次性 ASSIGN_VEHICLE 探针（**从不重试**） | `API:cmd` |
| `4_execution_control/acceptance/test-phase13-buy-live.py` | 一次性 BUY_VEHICLE 探针（从**不重试**命令） | `API:cmd` |
| `4_execution_control/acceptance/test-phase20-configure-goal-live.py` | 在授权测试存档上验收「建线并配置」目标 | `API:cmd` |
| `4_execution_control/acceptance/test-phase20-scheduling-live.py` | 建一条一次性线路，验证一次停站策略更新 | `API:cmd` |
| `4_execution_control/acceptance/test-phase20-sell-live.py` | 一次性 SELL_VEHICLE 验收（仅专用存档） | `API:cmd` |
| `4_execution_control/acceptance/watch-operations-until.py` | 持续观察并在一个截止时间前保守地操作一个存档 | `API:cmd` |
| `4_execution_control/actions/apply-dwell-optimization.py` | 站停优化方案：先 dry-run，再执行可执行条目 | `GM:stationsdepots`、`MD:vehicletypes` |
| `4_execution_control/actions/apply-line-timetable.py` | 预览/应用/清除一条线路的常驻时刻表 | `GM:linesvehicles` |
| `4_execution_control/actions/operate-assign-vehicle.py` | 把一个闲置车辆分配到线路（走 Task 闸门） | `API:cmd` |
| `4_execution_control/actions/operate-expand-line.py` | 给线路加一辆已验证的模板车（走 Task 闸门） | `API:cmd` |
| `4_execution_control/actions/operate-sell-vehicle.py` | 卖掉一个明确指定的车辆（走 Task 闸门） | `API:cmd` |
| `4_execution_control/actions/replace-line-fleet.py` | 整线换车队：**先加后卖**（先验证替换车到位，再卖原车） | `API:cmd` |
| `4_execution_control/actions/run-operational-telemetry.py` | 跑全部有界实时遥测分区并合并输出 | `SELF` |
| `mcp_server/src/tpf2_mcp/__init__.py` | 包标记 | `SELF` |
| `mcp_server/src/tpf2_mcp/analytics/__init__.py` | 分析包标记 | `SELF` |
| `mcp_server/src/tpf2_mcp/analytics/evidence.py` | 分析结论的「证据对象」：每个字段标出**来源与可信级别** | `SELF` |
| `mcp_server/src/tpf2_mcp/analytics/network_index.py` | 快照绑定的网络智能索引：线路/车站指标、分位数、离群、枢纽排名、可达性 | `SELF` |
| `mcp_server/src/tpf2_mcp/bridge.py` | bridge 的 Python 侧：写命令文件 → 等 mod 回应 → 读响应（单槽邮箱） | `MD:gamescripts`、`SELF` |
| `mcp_server/src/tpf2_mcp/cargo.py` | 货种注册表（从世界快照取，动态） | `MD:cargotypes`、`API:res` |
| `mcp_server/src/tpf2_mcp/cli.py` | 命令行入口 | `SELF` |
| `mcp_server/src/tpf2_mcp/config.py` | 定位游戏目录 / mod · staging / bridge / state 目录 | `GM:gamefilelocations`、`MD:publishing` |
| `mcp_server/src/tpf2_mcp/demand_history.py` | 按线路的引擎需求采样历史（有界持久化） | `SELF` |
| `mcp_server/src/tpf2_mcp/dispatch.py` | 调度（把发车控制接到 bridge） | `API:cmd` |
| `mcp_server/src/tpf2_mcp/dwell_optimizer.py` | 站停时长优化建议 | `MD:vehicletypes`、`GM:stationsdepots` |
| `mcp_server/src/tpf2_mcp/fleet_policy.py` | 保守的车队规模建议（基于已验证的需求采样） | `GM:linesvehicles` |
| `mcp_server/src/tpf2_mcp/graph.py` | 车站/线路**连通性**图（不是物理走行图） | `SELF` |
| `mcp_server/src/tpf2_mcp/journal.py` | 只追加的本地日志（**故意放在 bridge 目录之外**） | `SELF` |
| `mcp_server/src/tpf2_mcp/lines/__init__.py` | 线路包标记 | `SELF` |
| `mcp_server/src/tpf2_mcp/lines/models.py` | 线路/站点的数据模型 | `API:type` |
| `mcp_server/src/tpf2_mcp/lines/stop_resolver.py` | 把站点解析成引擎实体 | `API:type` |
| `mcp_server/src/tpf2_mcp/operations/__init__.py` | 受控操作层包标记（在引擎 API 未经验证前**故意不含写传输**） | `API:cmd` |
| `mcp_server/src/tpf2_mcp/operations/capabilities.py` | 写能力注册表（保守：一种操作单独验证过才登记） | `API:cmd`、`DG:09` |
| `mcp_server/src/tpf2_mcp/operations/controller.py` | 「先出提案再执行」的控制器：逐条验证过的操作才能落地 | `API:cmd`、`DG:09` |
| `mcp_server/src/tpf2_mcp/operations/diff.py` | 操作前后的状态差异 | `SELF` |
| `mcp_server/src/tpf2_mcp/operations/handlers/__init__.py` | 操作处理器注册表包标记 | `SELF` |
| `mcp_server/src/tpf2_mcp/operations/handlers/assign_vehicle.py` | 把车辆分配到线路 | `API:cmd` |
| `mcp_server/src/tpf2_mcp/operations/handlers/base.py` | 处理器基类 | `SELF` |
| `mcp_server/src/tpf2_mcp/operations/handlers/buy_vehicle.py` | 买车（对应官方 `buyVehicle`） | `API:cmd` |
| `mcp_server/src/tpf2_mcp/operations/handlers/create_line.py` | 建线（对应官方 `make.line` 一系） | `API:cmd`、`DG:09` |
| `mcp_server/src/tpf2_mcp/operations/handlers/registry.py` | 处理器注册 | `SELF` |
| `mcp_server/src/tpf2_mcp/operations/handlers/sell_vehicle.py` | 卖车（对应官方 `sellVehicle`） | `API:cmd` |
| `mcp_server/src/tpf2_mcp/operations/handlers/set_line_stop_policy.py` | 改线路停站策略 | `API:cmd` |
| `mcp_server/src/tpf2_mcp/operations/handlers/set_line_stops.py` | 改线路站点（对应官方 `setLine` / `updateLine`） | `API:cmd` |
| `mcp_server/src/tpf2_mcp/operations/handlers/vehicle_departure.py` | 强制发车 | `API:cmd` |
| `mcp_server/src/tpf2_mcp/operations/models.py` | 操作提案/结果的数据模型 | `SELF` |
| `mcp_server/src/tpf2_mcp/overtake_planner.py` | 待避/越行规划 | `GM:railwaysignals` |
| `mcp_server/src/tpf2_mcp/planning/__init__.py` | 规划包标记 | `SELF` |
| `mcp_server/src/tpf2_mcp/planning/decision_support.py` | 确定性的拓扑 what-if 规划（**从不写 bridge**） | `SELF` |
| `mcp_server/src/tpf2_mcp/protocol.py` | bridge 请求/响应/心跳的封包与解包 | `SELF` |
| `mcp_server/src/tpf2_mcp/rail_crossings.py` | 从引擎给的 XYZ 几何里检出**立体交叉**（公铁立交） | `SELF` |
| `mcp_server/src/tpf2_mcp/rail_live.py` | 铁路实时帧（供浏览器高频图层用） | `API:type` |
| `mcp_server/src/tpf2_mcp/save_scope.py` | 「一个存档谱系一个本地库」的作用域键 | `GM:gamefilelocations` |
| `mcp_server/src/tpf2_mcp/server.py` | MCP stdio 服务（JSON-RPC，一行一消息），把工具暴露给桌面端 | `SELF` |
| `mcp_server/src/tpf2_mcp/snapshot.py` | 世界快照（schema v2）的索引与只读网络分析 | `API:type`、`SELF` |
| `mcp_server/src/tpf2_mcp/station_log.py` | 车站停站/通过事件日志（从实时轨道帧推出） | `SELF` |
| `mcp_server/src/tpf2_mcp/station_preview.py` | 每座车站生成一份复用的物理预览（`platform_centerline` / `scope` 站场坐标系） | `API:type`、`SRC` |
| `mcp_server/src/tpf2_mcp/tasks/__init__.py` | 任务编排包标记（有界、提案优先） | `SELF` |
| `mcp_server/src/tpf2_mcp/tasks/goals.py` | 目标定义 | `SELF` |
| `mcp_server/src/tpf2_mcp/tasks/orchestrator.py` | 任务编排器（分步推进 + 人工审批闸门） | `SELF` |
| `mcp_server/src/tpf2_mcp/tasks/policy.py` | 任务策略常量 | `SELF` |
| `mcp_server/src/tpf2_mcp/timetable_planner.py` | 线模板循环时刻表规划（基于已验证的快照/实时字段） | `GM:linesvehicles` |
| `mcp_server/src/tpf2_mcp/vehicle_length.py` | 按车辆实际使用的模型资源解析编组长度 | `MD:vehicletypes`、`API:res` |
| `mcp_server/src/tpf2_mcp/work_log.py` | 给铁路图界面看的「调整日志」（持久化） | `SELF` |
| `mcp_server/start_server.py` | 不装包直接起 MCP 服务的启动器 | `SELF` |
| `mcp_server/start_ui.py` | 起铁路图 HTTP 服务的启动器 | `SELF` |
| `protocol/error.schema.json` | bridge 错误 schema | `SELF` |
| `protocol/heartbeat.schema.json` | 心跳 schema（`last_update` 推进 = 游戏真在跑） | `SELF` |
| `protocol/operational-telemetry.schema.json` | 运营遥测 schema | `SELF` |
| `protocol/request.schema.json` | bridge 请求 schema | `SELF` |
| `protocol/response.schema.json` | bridge 响应 schema | `SELF` |
| `protocol/snapshot.schema.json` | 世界快照 schema v2 | `SELF` |
| `tpf2_mod/mod.lua` | mod 元数据 + `runFn` 入口（资源加载前那一档） | `MD:scriptingbasics` |
| `tpf2_mod/res/config/game_script/tpf2_mcp.lua` | GameScript 入口：`load`/`save`/`update`/`handleEvent` 四个引擎回调 +  | `MD:gamescripts` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/api_inventory.lua` | 运行时把 `api.type` / `api.cmd` 的成员清单导出（Phase 18 用） | `API:cmd`、`API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/bridge_io.lua` | mod 沙箱内唯一可靠的写盘出口（`write_text` / `write_json` / 图层文件命名） | `MD:scriptingbasics`、`SELF` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/cargo.lua` | 货种字典：`api.res.cargoTypeRep` → id/名称/图标 | `API:res`、`MD:cargotypes` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/common.lua` | 读引擎字段的通用工具：`pick`（getter→pairs 两条路）、`flatten`、`components_of | `API:type`、`DG:08` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/company.lua` | 公司组件采集（快照用） | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/component_access.lua` | 组件类型解析（`api.type.ComponentType[name]`）+ 缓存 | `API:engine` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/context_probe.lua` | 调用上下文 / 返回形状探针（判断「可调用对象还是描述表」） | `API:engine`、`PN` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/demand_probe.lua` | 乘客/货物流量的事件式采集（挂引擎事件，累计计数） | `MD:gamescripts` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/dynamic_probe.lua` | 动态运输来源诊断探针（限 3 辆车，只输出原语值） | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/economy_probe.lua` | 经济探针：公司账本（按 type/carrier/maintenance 聚合）+ 每条线的维护费/运价/车辆数/货运数 | `API:type`、`GM:companyandfinances` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/field_probe.lua` | 组件字段可用性诊断：钉死「组件视图 vs `game.interface` 聚合表」字段名完全不同这件事 | `API:type`、`PN` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/industry.lua` | 产业组件采集（快照用） | `API:type`、`GM:industriescargos` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_freight.lua` | 产业链物流关系：遍历 `SIM_CARGO` 按 (source, target, cargoType) 聚合成边，带关 | `API:type`、`PN` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_industry.lua` | 产业图层：`SIM_BUILDING` 等级/库存指针 + 厂区占地包围盒 + 实时库存 | `API:type`、`GM:industriescargos` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_lines.lua` | 全方式线路图层：线路真实颜色 + `stops[]`（真实下标 + 车站 id） | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_passenger.lua` | **客流图层（流式）**：把客流从「外部主动拉」改成「mod 自驱推」。遍历玩家全部线路，用 `line_demand` | `API:engine`、`SELF` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_registry.lua` | 图层自驱派发：每 tick 按周期触发各层采集并写文件（Python 侧退化成纯读） | `MD:gamescripts` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_road.lua` | 公路网图层：`BASE_EDGE_STREET` 边 + 端点坐标 | `API:type`、`MD:tracksstreets` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_road_traffic.lua` | 道路交通图层：NPC 车流 → 路段聚合（车数/均速/分位）→ 绿黄橙红分档，不逐辆渲染 | `DG:08`、`GM:statisticsdatalayers` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_stations.lua` | 车站互通站群：`catchmentAreaSystem.getStation2stationsAndDistancesM | `API:engine`、`GM:stationsdepots` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_terrain.lua` | 地形图层：`game.interface.getHeight({x,y})` 采样 → 等高线 / 水深 | `API:engine`、`DG:04` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_town.lua` | 城镇图层：`TOWN.name` / `TOWN.position` / `Town.cargoNeeds`（城镇要什么 | `API:type`、`GM:towns` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/layer_vehicles.lua` | 车辆图层：`TRANSPORT_VEHICLE` 组件，位置走 `BOUNDING_VOLUME` 包围盒中心 | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/line.lua` | 线路组件采集（快照用）：站点服务、备用站台、UI 指标 | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_creation_probe.lua` | 「建线」API 形状探针：只构造对象，**从不调用 createLine/updateLine/sendCommand* | `API:type`、`API:cmd`、`DG:09` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_demand.lua` | 线路需求：候车/在途占比、等待时长分位 | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_finance_probe.lua` | 只读探针：线路/车辆层面的「收入」—— 游戏 UI 那条曲线引擎给不给 mod 读，以及能不能用车辆装载量自己算 | `GM:statisticsdatalayers`、`API:type`、`API:engine` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/line_raw_probe.lua` | 线路描述符字段/类型探针（不序列化引擎 userdata） | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/operational_telemetry.lua` | 运营遥测：信号、在途车辆、站台需求、仿真时钟，分区采集 | `API:type`、`DG:08` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/operations_probe.lua` | 运营相关组件探针（车辆/车站/产业/公司/货种的写侧字段形状） | `API:type`、`API:cmd` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/rail_network.lua` | 物理铁路图一次性导出：轨道边/节点、站台、线路站点序列，另带站台周边地形剖面与「正上方有没有贴地公路」 | `API:type`、`MD:tracksstreets` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/route_probe.lua` | 水运/航空航路接口探针 v2：六个 system 的成员逐个试调（不要求 `type=="function"`） | `API:engine`、`DG:09` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/simulation.lua` | 仿真时钟采集（游戏内时间基准） | `API:engine` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/station.lua` | 车站组件采集（快照用） | `API:type` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_geometry.lua` | 某个站群周边的物理铁路子图（独立于世界快照 schema） | `API:engine` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/station_struct_probe.lua` | 车站结构探针 v3：四类站的**模块网格**（`pairs(params.modules)`）全量导出 | `MD:modularconstructions`、`PN` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/terminal_waiting_probe.lua` | **站台候车人数 / 剩余位数探针**（只读、极度克制）。回答 R8 缺的那半：`simPersonAtTerminal | `API:engine`、`SELF` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/town.lua` | 城镇组件采集（快照用） | `API:type`、`GM:towns` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/ui_source_probe.lua` | UI 数据源探针（找游戏界面用的取数接口） | `API:gui`、`DG:10` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/vehicle.lua` | 车辆物理参数：编组、车长、最高速度、按货种容量 | `API:type`、`MD:vehicletypes` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/vehicle_write_probe.lua` | 车辆写 API 形状探针：列可调用成员、可构造对象，但不发命令 | `API:cmd`、`DG:09` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/world_probe.lua` | 世界探针 v4：全组件字段枚举 + `game.interface.getEntity(id)` 聚合表全字段 | `API:engine`、`API:type`、`PN` |
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/write_api_probe.lua` | 写 API 形状探针（只观察，不调用） | `API:cmd`、`DG:09` |
| `tpf2_mod/res/scripts/tpf2_mcp/config.lua` | 模块路径归一（`require` 前缀拼装） | `MD:scriptingbasics` |
| `tpf2_mod/res/scripts/tpf2_mcp/json.lua` | 自带 JSON 编解码（沙箱里没有 `json` 库） | `SELF` |
| `tpf2_mod/res/scripts/tpf2_mcp/operations/dispatcher.lua` | 发车控制（故意 fail-closed：bridge 挂了绝不让列车无限等待） | `API:cmd`、`MD:gamescripts` |
| `tpf2_mod/res/scripts/tpf2_mcp/operations/line_stop_builder.lua` | 构造 `Line.Stop` / 线路站点序列（复用观察到的原生描述符，userdata 不过桥） | `API:type`、`DG:09` |
| `tpf2_mod/res/scripts/tpf2_mcp/operations/timetable_controller.lua` | 时刻表控制器（发车时刻、挂钟↔游戏时间换算） | `API:cmd`、`GM:linesvehicles` |
| `tpf2_mod/res/scripts/tpf2_mcp/runtime.lua` | bridge 运行时：轮询命令文件、执行探针、写响应、写 `heartbeat.json` | `MD:gamescripts` |
| `tpf2_mod/res/scripts/tpf2_mcp/state.lua` | 探针注册表：一张「探针名 → 入口函数」的表，供 bridge 命令派发 | `SELF` |
| `tpf2_mod/strings.lua` | 本地化字符串表（`data()` 返回） | `MD:localizations` |
| `ui/rail-map/app.js` | 独立版站图应用外壳 | `SELF` |
| `ui/rail-map/bridge-crossings.js` | 公铁立交图层渲染 | `SELF` |
| `ui/rail-map/dispatch-pages.js` | 调度页面（含挂钟↔游戏时间换算） | `SELF` |
| `ui/rail-map/freight-flow.js` | 产业链流向渲染：选中产业 → 画上下游去向线（终点是**车站**）+ 明细浮层；支持**在地图上点产业图标选中** | `GM:industriescargos` |
| `ui/rail-map/industry-icons.js` | 产业图标层：用游戏原版图标画「原料 → 产品」；**点击图标即选中该产业**（与产业链层用事件广播解耦） | `GM:industriescargos` |
| `ui/rail-map/industry-kinds.js` | 产业类型表（从产业名字反推类别），供图标层与流向层共用 | `GM:industriescargos` |
| `ui/rail-map/network-app.js` | 铁路图主渲染（**上游作者的核心文件**，2286 行）：地图、图层、站台线、站点标记、侧栏 | `SELF` |
| `ui/rail-map/network-page.js` | 网络图页面装配 | `SELF` |
| `ui/rail-map/rail-graph.js` | 铁路图数据装配 | `SELF` |
| `ui/rail-map/rail-network-data.js` | **生成物**：由 `tools/export-rail-network-map.py` 写出的数据壳 | `SELF` |
| `ui/rail-map/rail-network-manifest.js` | **生成物**：铁路图数据清单 | `SELF` |
| `ui/rail-map/road-congestion.js` | 路况色带图层：按聚合速度给路段涂绿/黄/橙/红，放大才显示 | `GM:statisticsdatalayers`、`MD:baseconfig` |
| `ui/rail-map/station-struct.js` | 车站结构渲染：站台客/货分色、站房按真实尺寸画、**出入口按进/出/双向分色并画道路式箭头**；火车站只补站房（站台/轨 | `MD:modularconstructions`、`PN` |
| `ui/rail-map/template-runtime.js` | HTML 模板运行时 | `SELF` |
| `ui/rail-map/terrain-contour.js` | 等高线生成（Marching squares），纯计算不碰 DOM | `GM:statisticsdatalayers` |
| `ui/rail-map/timetable-page.js` | 时刻表页面入口 | `SELF` |
| `ui/rail-map/timetable.js` | 时刻表页面逻辑 | `GM:linesvehicles` |
| `ui/rail-map/town-layer.js` | 城镇图层：27 个城镇的名字 + 「它要什么货」 | `GM:towns` |
| `ui/rail-map/ui-persist.js` | 面板勾选项的本地记忆（localStorage）：把每个勾选框的状态记下来，下次打开还是上次那样；reset() 清空并 | `SELF` |
