#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产业供需诊断：这家厂是缺料、憋货，还是运转正常？要不要加车/新开线？

用户 2026-09-30 的原话：
    「通过统计这些数据告诉我工厂状态，是缺货还是满足，需求量够不够，送达量够不够，
      要不要新建线路或者加车，火车和海运也是一样的」
所以这份脚本输出的不是"数据表"，是**结论 + 该怎么动手**。

判据（两个比值，各自用同一量纲的量）
------------------------------------
① 供应够不够 —— supply_ratio = 实际入货 / 配方反推的原料需求
     · 用**累计量**比：两边都从"第一次运输"起累计，比值可比。
     · 需求的算法：产出量 × (原料用量 / 产出用量)。配方来自 industry-recipes.json，
       例如钢铁厂是「2 铁矿石 + 2 煤 → 1 钢」，产 478 钢就至少要 956 铁矿石 + 956 煤。
     · < 0.5 严重缺料 · < 0.9 偏紧 · ≥ 0.9 够

② 运力够不够 —— wait_ratio = 当前等待 / (当前在途 + 当前等待)
     · 必须用**当前量**（waiting / onboard）比。
       🔴 第一版拿 waiting 去除**累计**的 count —— 量纲不同，119 家厂全被误报"积压"。
     · > 0.5 站台压得厉害（车不够/班次太稀/站台太短） · < 0.3 运力充裕

用法：
    python tools/diagnose-industries.py
    python tools/diagnose-industries.py --bridge "<staging>\\bridge" --top 30
"""

import argparse
import json
import os
import sys

DEFAULT_BRIDGE = (r"C:\Program Files (x86)\Steam\userdata\1070536217"
                  r"\1066780\local\staging_area\tpf2mcp_1\bridge")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPES = os.path.join(PROJECT_ROOT, "ui", "rail-map", "industry-recipes.json")

# 名字关键词 → 配方键。顺序即优先级，长词在前（与 ui/rail-map/industry-kinds.js 一致）。
WORDS = [
    ("food_processing_plant", ["食物加工", "食品加工", "食物厂", "食品厂"]),
    ("construction_material", ["建材"]),
    ("iron_ore_mine", ["铁矿"]),
    ("coal_mine", ["煤矿"]),
    ("oil_well", ["油井"]),
    ("oil_refinery", ["炼油"]),
    ("fuel_refinery", ["燃料"]),
    ("chemical_plant", ["化工"]),
    ("machines_factory", ["机械"]),
    ("steel_mill", ["钢铁", "炼钢", "钢"]),
    ("tools_factory", ["工具"]),
    ("quarry", ["采石"]),
    ("farm", ["农田", "农场"]),
    ("forest", ["森林", "林场"]),
    ("saw_mill", ["锯木", "木材"]),
    ("goods_factory", ["加工厂", "工厂", "厂"]),
]
KIND_LABEL = {
    "food_processing_plant": "食品厂", "construction_material": "建材厂", "iron_ore_mine": "铁矿",
    "coal_mine": "煤矿", "oil_well": "油井", "oil_refinery": "炼油厂", "fuel_refinery": "燃料厂",
    "chemical_plant": "化工厂", "machines_factory": "机械厂", "steel_mill": "钢铁厂",
    "tools_factory": "工具厂", "quarry": "采石场", "farm": "农田", "forest": "森林",
    "saw_mill": "锯木厂", "goods_factory": "加工厂",
}

MIN_COUNT = 20          # 累计件数太小的边不参与判断（噪声）
SHORT_RATIO = 0.5       # 供应比低于这个 = 严重缺料
TIGHT_RATIO = 0.9       # 低于这个 = 偏紧
WAIT_HEAVY = 0.5        # 等待占比高于这个 = 运力不足
WAIT_OK = 0.3           # 低于这个 = 运力充裕


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def kind_of(name):
    text = str(name or "")
    for key, words in WORDS:
        if any(word in text for word in words):
            return key
    return "goods_factory"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", default=os.environ.get("TPF2_BRIDGE_DIR", DEFAULT_BRIDGE))
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    freight = load(os.path.join(args.bridge, "layer-freight.json"))
    industries = load(os.path.join(args.bridge, "layer-industry.json"))["points"]
    recipes = load(RECIPES)["industries"]
    state = load(os.path.join(args.bridge, "state.json"))
    names = {x["entity_id"]: x.get("name") for x in state.get("industries") or []}

    # ── 按产业聚合流向 ────────────────────────────────────────────────────────
    agg = {}
    for link in freight.get("links") or []:
        for side, key in ((link.get("source_industry"), "out"), (link.get("target_industry"), "in")):
            if side in (None, -1):
                continue
            slot = agg.setdefault(side, {"in": 0, "in_wait": 0, "in_on": 0, "in_other": 0,
                                         "out": 0, "out_wait": 0, "out_on": 0, "out_other": 0,
                                         "out_cargo": {}, "in_cargo": {}})
            for field, suffix in (("count", ""), ("waiting", "_wait"),
                                  ("onboard", "_on"), ("other", "_other")):
                slot[key + suffix] += link.get(field, 0) or 0
            if link.get("cargo_type") is not None:
                cargo = slot[key + "_cargo"]
                cargo[link["cargo_type"]] = cargo.get(link["cargo_type"], 0) + (link.get("count", 0) or 0)

    by_id = {p["entity_id"]: p for p in industries}

    rows = []
    for eid, slot in agg.items():
        point = by_id.get(eid) or {}
        name = names.get(eid) or ("产业 %s" % eid)
        kind = kind_of(name)
        recipe = recipes.get(kind) or {}

        # ① 供应比：产多少货，按配方反推该收到多少原料
        need = None
        if recipe.get("inputs") and recipe.get("outputs"):
            out_units = sum(recipe.get("output_amounts") or [1]) or 1
            in_units = sum(recipe.get("input_amounts") or [])
            need = slot["out"] * in_units / out_units
        supply = (slot["in"] / need) if need else None

        # ② 等待占比：当前货里有多少还堆在站台 / 源头
        out_now = slot["out_on"] + slot["out_wait"] + slot["out_other"]
        in_now = slot["in_on"] + slot["in_wait"] + slot["in_other"]
        out_wait_ratio = (slot["out_wait"] / out_now) if out_now else None
        in_wait_ratio = (slot["in_wait"] / in_now) if in_now else None

        verdicts = []
        if need and slot["out"] >= MIN_COUNT:
            if slot["in"] == 0:
                verdicts.append(("断料", "这家厂一点原料都没收到 —— 先查供货厂的线通不通"))
            elif supply is not None and supply < SHORT_RATIO:
                verdicts.append(("严重缺料", "只到了需求量的 %.0f%% —— 源头产量不够，或那条线运力不足"
                                 % (supply * 100)))
            elif supply is not None and supply < TIGHT_RATIO:
                verdicts.append(("原料偏紧", "到了 %.0f%%，还差一点" % (supply * 100)))
        if out_wait_ratio is not None and slot["out"] >= MIN_COUNT:
            if out_wait_ratio > WAIT_HEAVY:
                verdicts.append(("外运积压", "产出的货 %.0f%% 堆着没运走 —— 加车或加班次"
                                 % (out_wait_ratio * 100)))
            elif out_wait_ratio < WAIT_OK:
                pass
        if in_wait_ratio is not None and slot["in"] >= MIN_COUNT:
            if in_wait_ratio > WAIT_HEAVY:
                verdicts.append(("进料积压", "运到的原料 %.0f%% 卸不下来等着 —— 站台/车辆周转不过来"
                                 % (in_wait_ratio * 100)))

        if not verdicts:
            if slot["out"] >= MIN_COUNT or slot["in"] >= MIN_COUNT:
                verdicts.append(("运转正常", "供应和运力都跟得上"))
            else:
                continue

        severity = sum(3 if v[0] in ("断料", "严重缺料", "外运积压") else 1 for v in verdicts)
        rows.append({
            "name": name, "kind": kind, "level": point.get("level"),
            "progress": point.get("upgrade_progress"),
            "in": slot["in"], "need": need, "supply": supply,
            "out": slot["out"], "out_wait_ratio": out_wait_ratio,
            "severity": severity, "verdicts": verdicts, "slot": slot,
        })

    rows.sort(key=lambda r: (-r["severity"], -r["out"]))

    print("产业供需诊断（%d 家有流量的产业）\n" % len(rows))
    print("%-20s %-7s %-3s %7s %8s %6s %7s %7s  结论" %
          ("产业", "类型", "Lv", "入货", "原料需", "供应比", "出货", "等待占比"))
    print("-" * 118)
    for row in rows[:args.top]:
        print("%-20s %-7s %-3s %7d %8s %6s %7d %7s  %s" % (
            row["name"][:20], KIND_LABEL[row["kind"]], row["level"],
            row["in"], ("%.0f" % row["need"]) if row["need"] else "-",
            ("%.0f%%" % (row["supply"] * 100)) if row["supply"] is not None else "-",
            row["out"],
            ("%.0f%%" % (row["out_wait_ratio"] * 100)) if row["out_wait_ratio"] is not None else "-",
            " · ".join("%s：%s" % (v[0], v[1]) for v in row["verdicts"])))

    # ── 汇总：按病症归类，直接说该动什么 ──────────────────────────────────────
    buckets = {}
    for row in rows:
        for name, advice in row["verdicts"]:
            buckets.setdefault(name, []).append(row["name"])
    print("\n汇总")
    for name in ("断料", "严重缺料", "原料偏紧", "外运积压", "进料积压", "运转正常"):
        hit = buckets.get(name)
        if not hit:
            continue
        print("  %-6s %3d 家   %s" % (name, len(hit), "、".join(hit[:6]) + ("…" if len(hit) > 6 else "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
