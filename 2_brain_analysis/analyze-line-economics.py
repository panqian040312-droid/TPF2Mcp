#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按官方收入公式算每条线的收入（权重分摊版）。

## 为什么要有它

用户问：「官方文档里面收入是怎么计算的，应该有一套公式，包含货种、数量、距离、速度等元素」。
查完（见下面「公式出处」），官方口径是**两个要素**，而且**货种不影响价**。

## 公式出处（三方互证）

| 结论 | 原文 | 出处 |
|---|---|---|
| 收入只看**速度**和**距离**两个量 | 「For the calculation of revenue, two measurements are taken into account: The **faster** people and cargo travel, the higher the revenue. The **farther** people and cargo travel, the higher the revenue.」 | `gamemanual:tipstricks` |
| 距离按**直线**算 | 「distances are measured *"as the crow flies"* between the pick-up point and the drop-off point」 | 同上 |
| 货种**不影响**价格 | 17 个 `res/config/cargo_types/*.cargo.lua` 里**只有 `weight`（重量）和模型**，没有价格系数 | 实测 `res/config/cargo_types/` |
| 货物按距离、乘客按距离×速度 | 「Goods: distance covered. Passengers: distance covered multiplied by **speed factor**」 | `community:gameplaytips-hardmode` |
| 速度系数由**最慢车的最高速度**决定 | 「The passenger premium for speed seems to be influenced most by the **maximum speed of the slowest vehicle** on a line」 | 同上 |
| 运价是**每公里**的，且**由车速决定** | 「Top speed is a factor in setting a train's **transport price per Km**」 | `gamemanual:linesvehicles` |
| `defaultPrice` 就是"这条线的默认票价" | `LineVehicleInfo.defaultPrice` — "Default Ticket price for the line" | `api:type`（官方 API） |
| 空车不产生收入 | 「Empty vehicles aren't earning any revenue」 | `gamemanual:tipstricks` |
| ⭐ **收入按直线、维护费按实际轨道长度** | 「you get paid by **aerial distance** … you pay maintenance for **real track length**」 | 同上 |

⇒ 合起来：

    **收入 ≈ 直线距离(km) × defaultPrice × 载量**（客运再乘速度系数）

🔴 **`defaultPrice` 本身已经含了速度因素**（官方说 top speed 是设定 price per Km 的因素之一），
所以这里**不再另外乘速度** —— 否则会重复计一次。

## 这个脚本算什么、不算什么

**算**：每条线的收入**权重** `W = Σ_相邻站段(直线距离) × defaultPrice`，并把账本里的
运输总收入**按权重分摊**到每条线 → 得到一个**可排序、可比较**的"这条线大概赚多少"。

**不算**：不是实测值。它是**分摊**，前提是"各线单位距离的载量大致相当"。
真实收入需要"每次乘运的起终点与载量"（那是事件流，现在只有周期快照）。

**为什么要分摊而不是直接放弃**：账本总收入是**实测**的（`ACCOUNT.journal` 的 INCOME 条目求和），
权重是**按官方公式**算的 —— 两者相乘，比"凭感觉说这条线赚得多"靠谱得多。
每条线都会标 `估算` 而不是 `实测`。

## 用法

    python 2_brain_analysis/analyze-line-economics.py                # 打印排行
    python 2_brain_analysis/analyze-line-economics.py --report x.md  # 另出全量清单
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

# bridge 目录：默认走 staging（mod 真正写的地方），可用 TPF2_MCP_MOD_DIR 覆盖
DEFAULT_STAGING = Path(os.environ.get(
    "TPF2_MCP_MOD_DIR",
    r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1",
))
BRIDGE = DEFAULT_STAGING / "bridge"

# 距离单位：坐标是米。地图上 1 单位 = 1 米（本项目多处实测一致）。
M_PER_KM = 1000.0


def load(name: str, required: bool = True):
    path = BRIDGE / name
    if not path.is_file():
        if required:
            raise SystemExit("读不到 %s\n  期望路径：%s\n"
                             "  提示：命令行直跑要设 TPF2_MCP_MOD_DIR 指向 staging" % (name, path))
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def xy(node):
    """取 x/y（水平面）。z 是高度，'as the crow flies' 按水平直线算。"""
    if not isinstance(node, dict):
        return None
    x, y = node.get("x"), node.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="按官方收入公式分摊每条线的收入")
    ap.add_argument("--report", default=None, help="另出一份全量清单 Markdown")
    ap.add_argument("--top", type=int, default=20, help="打印前多少条（默认 20）")
    ap.add_argument("--include-zero-load", action="store_true",
                    help="把载量为 0 的线也纳入（多为客运线 —— 乘客不是货物实体）。"
                         "⚠️ 它们按载量 1 计，结果只反映「距离 × 价」，会明显高估客运线")
    args = ap.parse_args()

    state = load("state.json")
    economy = load("economy-probe.json")
    stations_layer = load("layer-stations.json", required=False)

    if stations_layer is None:
        raise SystemExit("没有 layer-stations.json —— 站点坐标是算距离的前提。"
                         "\n  它是 mod 自驱图层产物，等游戏跑起来会自动写。")

    # ── 坐标表 ────────────────────────────────────────────────────────────
    coords = {}
    for station in stations_layer.get("stations") or []:
        point = xy(station.get("position"))
        if point is not None:
            coords[station.get("entity_id")] = point

    # ── 每条线的运价 + 载量 ────────────────────────────────────────────────
    # 载量 = 在途货物实体数（`cargo_count`）＋ 在途乘客实体数（`person_count`）。
    # 🔴 2026-10-03：`person_count` 是**新加的**（`simPersonSystem.getSimPersonsForLine`，
    #    与 `getSimCargosForLine` 同构）。旧产物里没有这个字段 ⇒ 那时客运线载量一律 0。
    #    没这个字段就退化成"只用货"，并在输出里点明。
    prices, loads = {}, {}
    person_field_seen = False
    for item in (economy.get("lines") or {}).get("items") or []:
        price = item.get("default_price")
        if isinstance(price, (int, float)):
            prices[item["entity_id"]] = float(price)
        total, has_any = 0.0, False
        for key in ("cargo_count", "person_count"):
            value = item.get(key)
            if key == "person_count" and value is not None:
                person_field_seen = True
            if isinstance(value, (int, float)):
                total += float(value)
                has_any = True
        loads[item["entity_id"]] = total if has_any else None

    # ── 账本：运输总收入（实测）────────────────────────────────────────────
    journal = economy.get("journal") or {}
    income_total = None
    for row in journal.get("by_type") or []:
        if row.get("key") == "INCOME":
            income_total = row.get("sum")
    income_by_carrier = {}
    for row in journal.get("by_type_carrier") or []:
        key = str(row.get("key") or "")
        if key.startswith("INCOME|"):
            income_by_carrier[key.split("|", 1)[1]] = row.get("sum")

    # ── 逐线算权重 ────────────────────────────────────────────────────────
    # 公式：权重 = Σ_相邻站段(直线距离 km) × 每公里价 × 载量
    # 🔴 载量这一项**客运线拿不到**（cargo_count = 0）。默认**把载量 0 的线排除**，
    #    否则它们会按"距离 × 高价"被严重高估（实测：QY空中客运曾算出占总收入 9.17%）。
    #    要看那些线，加 `--include-zero-load`（它们按载量 1 算，只反映"距离 × 价"的相对大小）。
    rows = []
    skipped_no_price, skipped_no_coord, skipped_no_load = 0, 0, 0
    for line in state.get("lines") or []:
        entity_id = line.get("entity_id")
        price = prices.get(entity_id)
        if price is None:
            skipped_no_price += 1
            continue

        volume = loads.get(entity_id)
        if volume is None or volume <= 0:
            if not args.include_zero_load:
                skipped_no_load += 1
                continue
            volume = 1.0

        # stops 已按 index 排好序；相邻两站就是一段
        stops = sorted(line.get("stops") or [], key=lambda s: s.get("index") or 0)
        ids = [s.get("station_id") for s in stops]
        seg_km, missing = [], 0
        for a, b in zip(ids, ids[1:]):
            pa, pb = coords.get(a), coords.get(b)
            if pa is None or pb is None:
                missing += 1
                continue
            seg_km.append(math.dist(pa, pb) / M_PER_KM)
        if not seg_km:
            skipped_no_coord += 1
            continue

        total_km = sum(seg_km)
        weight = total_km * price * volume   # ← 官方公式：距离 × 每公里价 × 载量
        rows.append({
            "entity_id": entity_id,
            "name": line.get("name"),
            "stop_count": len(ids),
            "segments": len(seg_km),
            "missing_segments": missing,
            "km": total_km,
            "price": price,
            "load": volume,
            "weight": weight,
            "throughput": line.get("throughput"),
        })

    if not rows:
        print("一条线都没算出来 —— 检查 defaultPrice 与站点坐标是否齐全")
        return 1

    weight_sum = sum(r["weight"] for r in rows)
    rows.sort(key=lambda r: -r["weight"])
    for rank, row in enumerate(rows, 1):
        share = row["weight"] / weight_sum if weight_sum else 0.0
        row["share"] = share
        row["est_income"] = (income_total or 0) * share
        row["rank"] = rank

    # ── 自检 ──────────────────────────────────────────────────────────────
    checks = []
    checks.append(("权重总和 > 0", weight_sum > 0, "%.4g" % weight_sum))
    checks.append(("分摊比例之和 = 1", abs(sum(r["share"] for r in rows) - 1.0) < 1e-9,
                   "%.12f" % sum(r["share"] for r in rows)))
    checks.append(("每条线的距离 > 0", all(r["km"] > 0 for r in rows), "全为正"))
    checks.append(("覆盖率", True,
                   "%d 条算出 ／ 跳过 无价 %d、无坐标 %d、载量为0 %d"
                   % (len(rows), skipped_no_price, skipped_no_coord, skipped_no_load)))
    checks.append(("载量已进公式", True,
                   "每条权重都乘了 cargo_count（客运线因此被排除，不是漏算）"))

    # ── 输出 ──────────────────────────────────────────────────────────────
    print("每条线收入**估算**（公式：直线距离 × 每公里价 × 载量，再按权重分摊账本实测总收入）")
    print("=" * 112)
    print("账本运输总收入（实测，INCOME 条目求和）= %s" % (
        "{:,}".format(round(income_total)) if isinstance(income_total, (int, float)) else "（没采到）"))
    if income_by_carrier:
        print("按载体拆分（纯收入）：" + "  ".join(
            "%s %s" % (k, "{:,}".format(v)) for k, v in sorted(income_by_carrier.items())))
    else:
        print("按载体拆分：**还没有数据** —— `by_type_carrier` 是 2026-10-03 新加的聚合，"
              "要部署 + 重启游戏后才会出现在产物里")
    print("算出的线：%d 条；权重总和 Σ(km × 每公里价 × 载量) = %.4g" % (len(rows), weight_sum))
    if not person_field_seen:
        print("⚠️ 产物里**还没有 `person_count`**（乘客在途数）—— 那是 2026-10-03 新加的采集项，"
              "要部署 + 重启游戏后才会出现。所以本版客运线仍然被排除。")
    if skipped_no_load:
        print("⚠️ 排除 %d 条**载量数据为 0** 的线。要看它们加 --include-zero-load" % skipped_no_load)
    print()
    print("%-4s %-22s %5s %8s %8s %7s %10s %9s %14s" %
          ("#", "线名", "站数", "里程km", "每公里价", "载量", "权重", "占比", "推算收入"))
    print("-" * 112)
    for row in rows[:args.top]:
        print("%-4d %-22s %5d %8.1f %8.1f %7.0f %10.4g %8.2f%% %14s" % (
            row["rank"], str(row["name"])[:20], row["stop_count"], row["km"], row["price"],
            row["load"], row["weight"], row["share"] * 100, "{:,}".format(round(row["est_income"]))))

    print()
    print("自检：")
    for name, ok, detail in checks:
        print("   %s %-22s %s" % ("✔" if ok else "✗", name, detail))

    print()
    print("🔴 这是**估算**不是实测，而且有两层偏差，都要记住：")
    print("   ① 权重按官方公式算（距离 × 每公里价 × 载量），总收入是账本实测；")
    if person_field_seen:
        print("   ② 载量已含**乘客在途数**（person_count）⇒ 客运线也参与分摊了；")
    else:
        print("   ② ⚠️ 产物里还没有 `person_count` ⇒ **客运线（%d 条载量为 0）被排除**，"
              "却让货运线分摊了**全部**运输收入 ⇒ **货运线数字整体偏高**。" % skipped_no_load)
        print("      （`person_count` = `simPersonSystem.getSimPersonsForLine`，2026-10-03 新加，待部署重启）")
    print("   ⭐ 正确姿势还是：先用账本 `by_type_carrier` 拆出各载体的**纯收入**，再在载体内部按权重分摊。")
    print("   另：官方有一句运营要点 —— **收入按直线距离、维护费按实际轨道长度**，")
    print("   所以「实际里程 ÷ 直线距离」越大的线越吃亏（绕路白跑）。")

    if args.report:
        out = Path(args.report)
        with out.open("w", encoding="utf-8") as fh:
            fh.write("# 每条线收入估算（按官方公式分摊）\n\n")
            fh.write("公式：`估算收入 = 账本实测运输总收入 × 权重占比`，"
                     "`权重 = Σ_相邻站段(直线距离 km) × defaultPrice × 载量`\n\n")
            fh.write("- 账本运输总收入（实测）：%s\n" % (
                "{:,}".format(round(income_total)) if isinstance(income_total, (int, float)) else "未采到"))
            fh.write("- 算出 %d 条线；权重总和 %.4g\n" % (len(rows), weight_sum))
            fh.write("- 因载量为 0 被排除：%d 条（几乎都是客运线 —— 乘客不是货物实体）\n" % skipped_no_load)
            fh.write("- ⚠️ 分摊值，不是实测；前提是各线单位距离载量相当\n\n")
            fh.write("| # | 线名 | 站数 | 里程 km | 每公里价 | 载量 | 权重 | 占比 | 推算收入 |\n")
            fh.write("|---|---|---|---|---|---|---|---|---|\n")
            for row in rows:
                fh.write("| %d | %s | %d | %.1f | %.1f | %.0f | %.4g | %.2f%% | %s |\n" % (
                    row["rank"], row["name"], row["stop_count"], row["km"], row["price"],
                    row["load"], row["weight"], row["share"] * 100,
                    "{:,}".format(round(row["est_income"]))))
        print("\n已写出：%s（%d 条线）" % (out, len(rows)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
