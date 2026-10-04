#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把游戏的货种表整理成前端能直接用的字典：id → 键名 / 中文名 / 图标路径。

数据源是 `bridge/state.json` 里的 `cargo_types`（引擎 `cargoTypeRep.getAll()` 的结果）。
图标用的是 `ui/rail-map/icons/cargo/cargo_<小写键名>.png` —— 那批是从游戏 `ui.zip` 的
`hud/cargo_*@2x.tga` 提出来的原版图标，键名一一对应（id 3 = IRON_ORE = cargo_iron_ore.png）。

中文名是照着游戏中文界面的官方译名对的一遍。要改译名，改下面的 ZH 表再跑一次即可。

用法：
    python 1_data_collection/exporters/build-cargo-types.py
    python 1_data_collection/exporters/build-cargo-types.py --bridge "<staging>\\bridge" --out "<项目>\\ui\\rail-map\\cargo-types.json"
"""

import argparse
import json
import os
import sys

DEFAULT_BRIDGE = (r"C:\Program Files (x86)\Steam\userdata\1070536217"
                  r"\1066780\local\staging_area\tpf2mcp_1\bridge")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "ui", "rail-map", "cargo-types.json")

# 引擎键名 → 中文（非官方键名以游戏中文界面为准；认不出的原样保留英文键名）
ZH = {
    "PASSENGERS": "乘客",
    "LOGS": "原木",
    "COAL": "煤",
    "IRON_ORE": "铁矿石",
    "STONE": "石料",
    "GRAIN": "谷物",
    "CRUDE": "原油",
    "STEEL": "钢",
    "PLANKS": "木板",
    "PLASTIC": "塑料",
    "OIL": "精炼油",
    "CONSTRUCTION_MATERIALS": "建材",
    "MACHINES": "机器",
    "FUEL": "燃料",
    "TOOLS": "工具",
    "FOOD": "食品",
    "GOODS": "货物",
}

# 城镇三区的名字。needs 是个三元素数组，按官方语义依次是住宅 / 商业 / 工业。
ZONE_LABELS = ["住宅", "商业", "工业"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", default=os.environ.get("TPF2_BRIDGE_DIR", DEFAULT_BRIDGE))
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    state_path = os.path.join(args.bridge, "state.json")
    if not os.path.exists(state_path):
        print("找不到：%s" % state_path, file=sys.stderr)
        return 1
    with open(state_path, "r", encoding="utf-8") as fh:
        state = json.load(fh)
    raw = state.get("cargo_types") or []
    if not raw:
        print("state.json 里没有 cargo_types", file=sys.stderr)
        return 1

    icon_dir = os.path.join(PROJECT_ROOT, "ui", "rail-map", "icons", "cargo")
    types = []
    missing_icon = []
    for item in raw:
        key = item.get("cargo_key") or item.get("display_name") or ""
        cid = item.get("cargo_id", item.get("index"))
        icon = "icons/cargo/cargo_%s.png" % key.lower()
        if not os.path.exists(os.path.join(PROJECT_ROOT, "ui", "rail-map", icon)):
            missing_icon.append(key)
        types.append({
            "id": cid,
            "key": key,
            "zh": ZH.get(key, key),
            "icon": icon,
        })
    types.sort(key=lambda t: t["id"] if t["id"] is not None else 0)

    payload = {
        "note": "货种 id → 键名 / 中文名 / 原版图标。id 与城镇 needs 里出现的数字对应。",
        "zones": ZONE_LABELS,
        "types": types,
    }
    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    print("写出：%s" % args.out)
    print("  货种 %d 种" % len(types))
    print("  " + " / ".join("%s=%s" % (t["id"], t["zh"]) for t in types if t["key"] != "PASSENGERS"))
    print("  图标缺的：%s" % (missing_icon if missing_icon else "无 —— 全部齐 ✓"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
