#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成「数据资产总账 + 交叉索引」→ docs/DATA_INVENTORY.md

## 为什么要有它（用户的批评，2026-10-03）

> 「没有充分利用现有的接口和数据，总是造新的探针、新的字段出来」

这个批评是对的，而且证据就在眼前 —— 同一天里我犯了两次：

- `simPersonSystem.getSimPersonsForLine`（拿乘客的那条接口）**项目里 `line_demand.lua:157`
  早就在用**，我却写了个新探针去问"乘客能不能读"；
- `bridge/world-probe.json` 里**已经 dump 了 31 个 system 的全部方法名和 74 个组件清单**，
  我却先是靠猜字段名、又靠写探针去验证。

⇒ 根子是：**没有一张"我手上到底有什么"的总账**。每次要一个数据，凭记忆想"应该没有吧"，
    然后造新东西。这张总账就是为了终结这件事 —— 先查它，再决定要不要新采。

## 它交叉索引哪几个维度

    ┌─────────────┐      ┌──────────────┐      ┌──────────────┐
    │ 引擎接口     │ ←──→ │ 代码（谁在用）│ ←──→ │ 官方文档      │
    │（31 system） │      │ collectors/  │      │ api/ gamemanual/│
    └─────────────┘      └──────────────┘      └──────────────┘
                                  ↑
                                  │
                          ┌──────────────┐
                          │ 产物字段      │
                          │ bridge/*.json│
                          └──────────────┘

四个方向都能查：
- **接口 → 谁在用、采到哪个产物**（"这个接口我用了没？"）
- **产物 → 字段 → 来自哪个接口**（"这个字段怎么来的？"）
- **要 X 数据 → 去哪拿**（速查表，手工维护，最实用）
- **没用过的接口清单**（"还有哪些现成的没利用" ← 这条最治本）

## 数据来源

| 来源 | 提供什么 |
|---|---|
| `bridge/world-probe.json` | **全部可用接口**（`system_methods` 31 个 system、`component_walk` 74 组件、`registries` 各命名空间） |
| `tpf2_mod/**/*.lua` | 项目**实际调用了**哪些接口 |
| `bridge/*.json` | 产物里**实际有**哪些字段 |
| `docs/code-wiki-map.json` | 代码 ↔ 官方文档的对应（已有的那份索引） |

## 用法

    python 0_core_shared/index/build-data-inventory.py                 # 生成 docs/DATA_INVENTORY.md
    python 0_core_shared/index/build-data-inventory.py --check         # 只校验数据源在不在
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# 项目根：向上找 .git。不要写 parent.parent —— 本脚本在 0_core_shared/index/ 下，
# 数层数会在搬目录时静默算错（2026-10-03 踩过）。
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / ".git").exists())
MOD_LUA = PROJECT / "tpf2_mod" / "res" / "scripts" / "tpf2_mcp"
OUT = PROJECT / "docs" / "DATA_INVENTORY.md"
WIKI_MAP = PROJECT / "docs" / "code-wiki-map.json"
# 接口基线：**代码里允许出现的引擎接口白名单**。
# 🔴 立它是因为用户 2026-10-03 的硬要求：「务必在添加新功能、写新代码前查询这个交叉索引的目录，
#    禁止随意生成新探针、新字段」。写在文档里靠自觉是不够的 —— 这里做成**会报错的断言**：
#    代码里一旦出现基线外的接口调用，`--check` 直接失败退出，逼着先查总账、再显式登记。
BASELINE = PROJECT / "docs" / "interface-baseline.json"

STAGING = Path(os.environ.get(
    "TPF2_MCP_MOD_DIR",
    r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1",
))
BRIDGE = STAGING / "bridge"

# ── 手工维护：现成接口 ↔ 已知需求 ──────────────────────────────────────────
# 这张表是全篇最有用的一节：**「我想要 X」→「哪个现成接口能给」**。
# 立它就是因为反复犯同一个错 —— 想要某数据时凭记忆觉得"应该没有"，然后造新探针，
# 而接口其实一直在（`world-probe.json` 里躺着）。
# 维护规则：**凡是"为了拿某个数据"而写新采集/新探针之前，先查这里。**
# `used` 由脚本按代码实际调用情况**自动判定**，不用手工填。
WISH_LIST = [
    ("每辆车/每列车当前装了什么货（货种 → 数量）",
     "simEntityAtVehicleSystem.getVehicle2Cargo2SimEntitesMap", "车辆装载"),
    ("车上乘客明细", "simPersonAtVehicleSystem.getVehiclePartInfoList", "客运量"),
    ("车站候车人数 / 站台剩余容量 / 候车位所在的传输网边",
     "simPersonAtTerminalSystem.getNumFreePlaces / getEdgeInfoMap / getPos01",
     "车站候车量（R8/R26）"),
    ("候车区的边 / 节点 → 站台（把 getEdgeInfoMap 的 EdgeId 解回车站）",
     "stationSystem.getStationTerminalsForPersonEdge / getStationTerminalsForPersonNode",
     "站台容量（R26）"),
    ("站台货物占用 / 是否有空位 / 支持哪些货种",
     "simCargoAtTerminalSystem.getCount / getEntity / getMaxCount / getPlace / hasFreePlaces", "站台压力"),
    ("有问题的线路 + 问题类型", "lineSystem.getProblemLines", "运营诊断"),
    ("城镇的货物供给与上限", "townBuildingSystem.getCargoSupplyAndLimit", "城镇需求（R6）"),
    ("城镇 ↔ 车站的对应关系", "stationSystem.getStation2TownMap / getTown2StationsMap", "城镇/车站分析"),
    ("某种原料的来源厂", "stockListSystem.getSources", "产业链上游"),
    ("库存实体枚举（按库存查实体）", "simEntityAtStockSystem.getStockEntities / getStockSimEntity", "库存"),
    ("乘客总数", "simPersonSystem.getCount", "客运量"),
    ("按目的地查在途乘客", "simPersonSystem.getSimPersonsForDestination", "客运 OD"),
    ("线路的站点序列（含站台号）", "lineSystem.getLineStops / getTerminal2lineStops", "线路结构"),
    ("停在某车站的所有线路", "lineSystem.getLineStopsForStation", "车站分析"),
    ("停在某站台的所有线路", "lineSystem.getLineStopsForTerminal", "站台压力"),
    ("我的所有线路", "lineSystem.getLinesForPlayer", "线路清单"),
    ("路口 / 平交道口实体", "railRoadCrossingSystem.getRailroadCrossingForEdge / ForNode", "公铁立交"),
    ("街区（parcel）数据", "parcelSystem.getParcelData / getSegment2ParcelData", "城镇地理"),
    ("城镇建筑 / 人口容量分布",
     "townBuildingSystem.getTown2BuildingMap / getPersonCapacity2townBuildingMap", "城镇需求"),
    ("任意设施 → 它的建筑实体",
     "streetConnectorSystem.getConstructionEntityForStation / ForEdge / ForDepot / ForSimBuilding",
     "设施↔建筑"),
    ("水体网格实体", "riverSystem.getWaterMeshEntities", "地形/水运"),
    ("跑道起降节点", "runwaySystem.getLandingNodeIdMap / getTakeoffNodeIdMap", "机场结构"),
]

MAX_FULL_PARSE_MB = 40
MAX_KEY_DEPTH = 4
MAX_ARRAY_SAMPLE = 1          # 数组只取第一项代表


# ── 一、代码里调用了哪些接口 ────────────────────────────────────────────────
def scan_calls() -> dict:
    """扫 Lua 源码，抽出所有引擎接口调用 → {接口: [(文件, 行号), ...]}"""
    patterns = [
        r"api\.engine\.system\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)",   # system.xxx.yyy
        r"api\.engine\.util\.([a-zA-Z0-9_]+)",                      # util.xxx
        r"api\.engine\.component\.([A-Z_]+)",                        # component.XXX
        r"game\.interface\.([a-zA-Z0-9_]+)",                         # game.interface.xxx
        r"api\.res\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)",               # res.xxx.yyy
        r"api\.type\.([a-zA-Z0-9_.]+)",                              # type.Xxx
        r"api\.engine\.(getComponent|getEntity)",                    # 少数的顶层函数
    ]
    calls: dict[str, list] = {}
    for path in sorted(MOD_LUA.rglob("*.lua")):
        rel = path.relative_to(PROJECT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("--"):        # 整行注释不算
                continue
            for pattern in patterns:
                for match in re.finditer(pattern, line):
                    key = match.group(0)
                    calls.setdefault(key, []).append("%s:%d" % (rel, line_no))
    return calls


# ── 二、world-probe 里的全部可用接口 ────────────────────────────────────────
def load_available() -> dict:
    """返回 {system: [方法...]}、[组件...]、{命名空间: {键: 类型}}"""
    probe_path = BRIDGE / "world-probe.json"
    if not probe_path.is_file():
        return {}
    with probe_path.open(encoding="utf-8") as handle:
        probe = json.load(handle)

    systems = {}
    for name, block in (probe.get("system_methods") or {}).items():
        methods = [entry.get("name") for entry in (block.get("names") or [])
                   if isinstance(entry, dict)]
        systems[name] = methods

    components = sorted((probe.get("component_walk") or {}).keys())

    namespaces = {}
    for source in ("registries", "extra_namespaces"):
        for name, block in (probe.get(source) or {}).items():
            keys = [entry.get("name") for entry in (block.get("names") or [])
                    if isinstance(entry, dict)]
            namespaces.setdefault(name, []).extend(keys)

    return {"systems": systems, "components": components, "namespaces": namespaces,
            "probed_at": probe.get("game_time"), "total_entities": probe.get("total_entities_walked")}


# ── 三、bridge 产物里的字段 ────────────────────────────────────────────────
def collect_keys(value, depth: int = 0) -> dict:
    """递归收集键（只到 MAX_KEY_DEPTH 层；数组只看第一项）。"""
    out: dict[str, object] = {}
    if depth >= MAX_KEY_DEPTH:
        return out
    if isinstance(value, dict):
        for key, item in value.items():
            out[key] = type(item).__name__
            for sub_key, sub_type in collect_keys(item, depth + 1).items():
                out.setdefault("%s.%s" % (key, sub_key), sub_type)
    elif isinstance(value, list) and value:
        for sub_key, sub_type in collect_keys(value[0], depth + 1).items():
            out.setdefault("[]." + sub_key, sub_type)
    return out


def scan_outputs() -> list[dict]:
    """扫 bridge 的产物 → [{文件名, 大小, 顶层键, 字段}]"""
    rows = []
    if not BRIDGE.is_dir():
        return rows
    for path in sorted(BRIDGE.glob("*.json")):
        size = path.stat().st_size
        entry = {"name": path.name, "size": size, "top": [], "fields": {}, "skipped": False}
        if size > MAX_FULL_PARSE_MB * 1024 * 1024:
            # 超大产物只读顶层键（用正则扫第一层的 "key":，不稳但够用）
            entry["skipped"] = True
            try:
                head = path.read_text(encoding="utf-8", errors="ignore")[:200000]
                entry["top"] = sorted(set(re.findall(r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', head)))[:25]
            except OSError:
                pass
            rows.append(entry)
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            entry["fields"] = {"__read_error__": str(error)[:60]}
            rows.append(entry)
            continue
        if isinstance(data, dict):
            entry["top"] = list(data.keys())
            entry["fields"] = collect_keys(data)
        elif isinstance(data, list):
            entry["top"] = ["(顶层是数组, %d 项)" % len(data)]
            entry["fields"] = collect_keys(data)
        rows.append(entry)
    return rows


# ── 四、主流程 ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="生成数据资产总账与交叉索引")
    ap.add_argument("--check", action="store_true",
                    help="🔴 硬校验：代码里出现了基线外的新接口调用就报错退出（防止随意新增探针/字段）")
    ap.add_argument("--update-baseline", action="store_true",
                    help="把当前扫到的接口写入基线（**改了它会出现在 git diff 里，请连同理由一起提交**）")
    args = ap.parse_args()

    calls = scan_calls()

    # ── 基线校验 / 更新 ──────────────────────────────────────────────────
    if args.check or args.update_baseline:
        current = sorted(calls)
        baseline = {"note": "代码里允许出现的引擎接口白名单。由 0_core_shared/index/build-data-inventory.py --update-baseline 生成。"
                            "新增接口必须先查 docs/DATA_INVENTORY.md 第零节，确认现成接口里没有可用的，"
                            "再连同理由一起更新本文件。",
                    "approved": []}
        baseline_exists = BASELINE.is_file()
        if BASELINE.is_file():
            with BASELINE.open(encoding="utf-8") as handle:
                baseline.update(json.load(handle))
        approved = set(baseline.get("approved") or [])

        if args.update_baseline:
            baseline["approved"] = current
            BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
            added = sorted(set(current) - approved)
            print("✅ 基线已更新：%d 条（本次新增 %d 条）" % (len(current), len(added)))
            for key in added:
                print("   + %s" % key)
            return 0

        if not baseline_exists:
            baseline["approved"] = current
            BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
            print("✅ 基线文件不存在 → 已用当前 %d 个接口初始化。" % len(current))
            print("   请提交 docs/interface-baseline.json；之后任何**新增**接口调用都会让 --check 失败。")
            return 0

        new_calls = sorted(set(current) - approved)
        gone = sorted(approved - set(current))
        print("接口基线校验：代码里 %d 个接口，基线批准 %d 个" % (len(current), len(approved)))
        if gone:
            print("   基线里多出 %d 条（代码里已不再调用，可清理）：%s"
                  % (len(gone), "、".join(gone[:6])))
        if new_calls:
            print()
            print("❌ 校验未通过：出现 %d 个**基线外的新接口调用**。" % len(new_calls))
            for key in new_calls:
                shown = "、".join(calls[key][:3])
                print("   - %s" % key)
                print("     用在：%s" % shown)
            print()
            print("按规矩，新增接口前必须先做两件事：")
            print("  ① 查 docs/DATA_INVENTORY.md 第零节「我想要 → 现成接口」——")
            print("     实测有 31 个 system / 116 个方法，项目历史上一度只用了 28 个，")
            print("     很可能你要的数据**已经有现成接口**（例：每辆车装了什么货 =")
            print("     simEntityAtVehicleSystem.getVehicle2Cargo2SimEntitesMap）；")
            print("  ② 确认现成接口确实不够用，再把接口补进脚本的 WISH_LIST（写清「我想要什么」），")
            print("     然后跑 `--update-baseline` 更新白名单 —— 这一步会出现在 git diff 里，")
            print("     等于把「新加了什么接口、为什么加」留痕。")
            print()
            print("⚠️ 直接 --update-baseline 而不登记 WISH_LIST 等于绕过规矩。")
            return 1
        print("✅ 通过：没有基线外的新接口。")
        return 0

    available = load_available()
    outputs = scan_outputs()

    # 接口 → 使用者（只取 system.xxx.yyy 形式，好跟 system_methods 对齐）
    used_system_calls = {}
    for key, places in calls.items():
        match = re.match(r"api\.engine\.system\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)", key)
        if match:
            used_system_calls.setdefault(match.group(1), set()).add(match.group(2))
        elif re.match(r"api\.engine\.util\.", key):
            used_system_calls.setdefault("(api.engine.util)", set()).add(key.rsplit(".", 1)[-1])

    # 产物字段 → 哪些产物有它（反向索引）
    field_sources: dict[str, list] = {}
    for entry in outputs:
        for field in entry["fields"]:
            field_sources.setdefault(field, []).append(entry["name"])

    # 代码 ↔ 官方文档（复用已有索引）
    wiki = {}
    if WIKI_MAP.is_file():
        with WIKI_MAP.open(encoding="utf-8") as handle:
            wiki = (json.load(handle).get("files") or {})

    L: list[str] = []
    add = L.append
    add("# 数据资产总账 与 交叉索引")
    add("")
    add("> **本文件由 `0_core_shared/index/build-data-inventory.py` 自动生成，不要手改。**")
    add("> 要改内容 → 改代码/产物或脚本 → 重跑。")
    add("")
    add("**这张表是干什么的**：回答「这个数据我到底有没有、从哪拿、用了没」。")
    add("立它的直接原因 —— 同一天里我两次没查账就造新探针：")
    add("`getSimPersonsForLine` 项目里早在用（`line_demand.lua:157`），")
    add("`world-probe.json` 里早 dump 了 31 个 system 的全部方法。**先查这里，再决定要不要新采。**")
    add("")

    # ── 摘要 ──
    total_methods = sum(len(v) for v in (available.get("systems") or {}).values())
    used_methods = sum(len(v) for v in used_system_calls.values())
    add("## 摘要")
    add("")
    add("| 项 | 数 |")
    add("|---|---|")
    add("| 引擎 system（实测可用） | **%d** 个 |" % len(available.get("systems") or {}))
    add("| 这些 system 的方法合计 | **%d** 个 |" % total_methods)
    add("| 项目**实际调用**的接口（去重） | **%d** 个 |" % len(calls))
    add("| 其中 system 方法 | **%d** 个 |" % used_methods)
    add("| 组件类型（实测可用） | **%d** 个 |" % len(available.get("components") or []))
    add("| bridge 产物 | **%d** 个（%.0f MB） |"
        % (len(outputs), sum(e["size"] for e in outputs) / 1024 / 1024))
    add("| 产物里出现过的字段路径 | **%d** 条 |" % len(field_sources))
    add("")

    # ── 零、需求 → 现成接口（全篇最该先看的一节）──
    add("## 零、🎯「我想要这个数据」→「哪个现成接口能给」")
    add("")
    add("**立这张表的直接原因**：反复犯同一个错 —— 想要某个数据时凭记忆觉得「应该没有」，")
    add("然后造新探针、加新字段；而接口一直在（`world-probe.json` 里躺着）。")
    add("同一天两次：`getSimPersonsForLine` 项目里早在用我却另写探针；")
    add("`getVehicle2Cargo2SimEntitesMap` 就是我要问的「车装了什么」，我也没查。")
    add("")
    add("🔴 **规矩：凡是为了拿某个数据而写新采集/新探针之前，先查这张表。**")
    add("")
    add("| 我想要 | 现成接口 | 用了吗 |")
    add("|---|---|---|")
    for want, api_names, tag in WISH_LIST:
        marks = []
        for one in [x.strip() for x in api_names.split("/")]:
            if "." in one:
                system, method = one.split(".", 1)
                full = "api.engine.system.%s.%s" % (system, method.strip())
            else:
                full = ""
            marks.append("✔" if full and full in calls else "❌")
        used_flag = "**✔ 已用**" if all(m == "✔" for m in marks) else \
                    ("部分 ✔" if any(m == "✔" for m in marks) else "**❌ 没用过**")
        add("| %s<br><sub>%s</sub> | `%s` | %s |"
            % (want, tag, api_names.replace(" / ", "`<br>`"), used_flag))
    add("")

    # ── 一、没用过的接口（最治本的一节）──
    add("## 一、🔴 现成但**没用过**的接口（全量）")
    add("")
    add("下面这些是 `world-probe.json` 实测存在、而项目代码里**一次都没调用**的。")
    add("要新数据时先扫一遍 —— 很可能已经有现成的。")
    add("")
    for name, methods in sorted((available.get("systems") or {}).items()):
        unused = [m for m in methods if m not in (used_system_calls.get(name) or set())]
        if not unused:
            continue
        used = len(methods) - len(unused)
        add("**`%s`** ｜ %d 个方法，用了 %d 个，**没用 %d 个**：" % (name, len(methods), used, len(unused)))
        add("")
        add("```")
        for method in unused:
            add("  %s" % method)
        add("```")
        add("")
    add("")

    # ── 二、接口 → 使用者 ──
    add("## 二、接口 → 谁在用（正向索引）")
    add("")
    add("| 接口 | 调用处 |")
    add("|---|---|")
    for key in sorted(calls):
        places = calls[key]
        shown = "、".join("`%s`" % p for p in places[:3])
        if len(places) > 3:
            shown += " …（共 %d 处）" % len(places)
        add("| `%s` | %s |" % (key, shown))
    add("")

    # ── 三、产物 → 字段 ──
    add("## 三、产物 → 字段（反向索引）")
    add("")
    add("> 超大产物（>%d MB）只列顶层键，不展开。" % MAX_FULL_PARSE_MB)
    add("")
    add("| 产物 | 大小 | 顶层键 / 关键字段 |")
    add("|---|---|---|")
    for entry in sorted(outputs, key=lambda e: -e["size"]):
        size = "%.1f MB" % (entry["size"] / 1024 / 1024) if entry["size"] > 1024 * 1024 \
            else "%.0f KB" % (entry["size"] / 1024)
        if entry["skipped"]:
            detail = "（未展开）顶层像：`%s`" % "`, `".join(entry["top"][:12])
        else:
            top = entry["top"][:10]
            detail = "`%s`" % "`, `".join(str(t) for t in top)
            if len(entry["fields"]) > len(top):
                detail += " ／ **%d 条字段路径**" % len(entry["fields"])
        add("| `%s` | %s | %s |" % (entry["name"], size, detail))
    add("")

    # ── 四、字段 → 在哪些产物里 ──
    add("## 四、字段 → 在哪些产物里（跨产物找同一个数据）")
    add("")
    add("只看**出现在 2 个以上产物**里的字段（说明它有多处来源，改的时候别漏）——")
    add("单产物独有的字段太多，去第三节按产物查。")
    add("")
    add("| 字段路径 | 出现在 |")
    add("|---|---|")
    shared = [(f, ps) for f, ps in field_sources.items() if len(ps) > 1]
    for field, places in sorted(shared, key=lambda kv: -len(kv[1]))[:80]:
        add("| `%s` | %s |" % (field, "、".join("`%s`" % p for p in places[:5])))
    add("")
    add("（共 %d 条跨产物字段，上面按出现次数排前 80）" % len(shared))
    add("")

    # ── 五、代码 ↔ 官方文档（并入已有索引）──
    add("## 五、代码 ↔ 官方文档（并入 `CODE_WIKI_INDEX.md` 的口径）")
    add("")
    if wiki:
        add("| 文件 | 干什么 | 官方出处 |")
        add("|---|---|---|")
        for rel in sorted(wiki):
            entry = wiki[rel]
            sources = "、".join("`%s`" % s for s in (entry.get("sources") or [])) or "`—`"
            add("| `%s` | %s | %s |" % (rel, (entry.get("what") or "—")[:60], sources))
    else:
        add("（没有 `docs/code-wiki-map.json`）")
    add("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")

    print("✅ 已生成 %s" % OUT)
    print("   摘要：%d 个 system / 共 %d 个方法；项目调用了 %d 个接口（其中 system 方法 %d 个）；"
          % (len(available.get("systems") or {}), total_methods, len(calls), used_methods))
    print("         %d 个产物 / %.0f MB；产物字段路径 %d 条（跨产物的 %d 条）"
          % (len(outputs), sum(e["size"] for e in outputs) / 1024 / 1024,
             len(field_sources), len(shared)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
