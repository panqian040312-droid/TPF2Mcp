#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产业运转诊断：这家厂在正常出货，还是货堆着没人运？

用户 2026-10-02 的要求（在砍掉"要游戏内那张表"之后）：
    「我需要**是否正常运转的结论**，还有是否抓取到**产业等级和每个等级对应的最大产量**」

--------------------------------------------------------------------------
判据只有一条，但它是**有绝对标尺**的：把"堆着的货"换算成"几个月的产量"。

  年产量上限 P = capacity × Σ产出量 × 当前等级        （件/年）
  堆压月数   = 出货侧 waiting ÷ (P / 12)

  标尺来自游戏本体，可查：
    · `res/construction/construction.zip :: industry/*.con` 的
      `rule = { input = …, output = { COAL = 1 }, capacity = 400 }`
    · 官方 modding 文档 `constructiontypes.md`「#### Rules」原话：
      "The number of times that the rule can be processed **per year** is limited by `capacity`."
      ⇒ 每年最大产量 = capacity × 产出数量
    · 游戏本体 `res/scripts/industryutil.lua` 的 `addIndustryData`：
      `capacity = (… or stockListConfig.rule.capacity or 0) * currentLevel`
      ⇒ 按等级线性放大 ⇒ 第 N 级 = capacity × Σ产出量 × N
    等级数与每级上限由 `1_data_collection/exporters/extract-industry-recipes.py` 抽进
    `ui/rail-map/industry-recipes.json` 的 `levels` / `max_per_level`。

--------------------------------------------------------------------------
🔴 **这一版把上一版被判死的判据换掉了**（2026-10-02 实测证伪）：
  旧版拿 `link.count` 当"累计量"算"供应比 = 入货 ÷ 需要量"，但实测
  **4425/4425 条 link 全部满足 `count = waiting + onboard + other`** ⇒ 它是**当前快照量**，
  两个快照相除没有意义；而且进料侧只有 58/215 家有记录。
  ⇒ 供应比整条判据**删掉**，进料侧改成"有数据才列、没数据明说"。

用法：
    python 2_brain_analysis/diagnose-industries.py                 # 全部产业
    python 2_brain_analysis/diagnose-industries.py --only-plant     # 只看要进料的加工厂（82 家）
    python 2_brain_analysis/diagnose-industries.py --only-raw       # 只看纯采集的原料厂（133 家）
    python 2_brain_analysis/diagnose-industries.py --top 30
    python 2_brain_analysis/diagnose-industries.py --bridge "<staging>\\bridge"
"""

import argparse
import collections
import json
import os
import sys

DEFAULT_BRIDGE = (r"C:\Program Files (x86)\Steam\userdata\1070536217"
                  r"\1066780\local\staging_area\tpf2mcp_1\bridge")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPES = os.path.join(PROJECT_ROOT, "ui", "rail-map", "industry-recipes.json")

# 名字关键词 → 配方键。顺序即优先级，长词在前（与 ui/rail-map/industry-kinds.js 保持一致）。
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

# 堆压月数（堆着的货 = 几个月的产量）的分档。
# 🔴 **这三个阈值是本项目自己定的**，不是游戏给的 —— 游戏只给"库存无限、看谁先见底"的口径。
MONTHS_TIGHT = 1.0      # ≥ 1 个月的产量堆着 = 有积压
MONTHS_HEAVY = 3.0      # ≥ 3 个月 = 明显积压（要加车或改线）

VERDICT_ORDER = ("停摆", "无流量", "没人运", "运力不足", "偏紧", "正常", "无法判定")


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
    ap.add_argument("--only-plant", action="store_true", help="只看要进料的加工厂")
    ap.add_argument("--only-raw", action="store_true", help="只看纯采集的原料厂")
    ap.add_argument("--report", default=None,
                    help="把**全部**产业（不受 --top 限制）导成 Markdown 清单；给了就写这个文件")
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
                                         "out": 0, "out_wait": 0, "out_on": 0, "out_other": 0})
            for field, suffix in (("count", ""), ("waiting", "_wait"),
                                  ("onboard", "_on"), ("other", "_other")):
                slot[key + suffix] += link.get(field, 0) or 0

    by_id = {p["entity_id"]: p for p in industries}

    rows = []
    for eid, slot in agg.items():
        point = by_id.get(eid) or {}
        name = names.get(eid) or ("产业 %s" % eid)
        kind = kind_of(name)
        recipe = recipes.get(kind) or {}
        is_plant = bool(recipe.get("inputs"))          # 要进料的加工厂

        level = point.get("level")
        ladder = recipe.get("max_per_level") or []
        # 存档的 `level` 是 0 起（与 industryutil.lua 里 `currentLevel = productionLevel + 1` 同源），
        # 所以索引就是 level 本身。
        # ⚠️ 这一层是**推断**（官方文档只说 `level` = "the current level"）；好在它只影响
        #    "几个月"的换算比例，不影响"积压 / 正常"的分档方向。
        cap_per_year = None
        if ladder and isinstance(level, int) and 0 <= level < len(ladder):
            cap_per_year = ladder[level]

        wait = slot["out_wait"]
        on = slot["out_on"]
        months = (wait / (cap_per_year / 12.0)) if cap_per_year else None

        # ── 结论 ──────────────────────────────────────────────────────────────
        if slot["out"] == 0 and on == 0 and wait == 0:
            verdict = "停摆"
            why = "系统里一件产出的货都没有 —— 要么没投产，要么产出走的是我们没采到的通道"
        elif wait == 0 and on == 0:
            verdict = "停摆"
            why = "既没有货在等，也没有货在车上"
        elif months is None:
            verdict = "无法判定"
            why = "这类产业没解析到年产量上限"
        elif on == 0 and months >= MONTHS_TIGHT:
            verdict = "没人运"
            why = "堆了 %.1f 个月的产量，车上一件都没有 —— 没有线路或车辆在拉这家的货" % months
        elif months >= MONTHS_HEAVY:
            verdict = "运力不足"
            why = "堆了 %.1f 个月的产量（车在拉，但拉不完）" % months
        elif months >= MONTHS_TIGHT:
            verdict = "偏紧"
            why = "堆了 %.1f 个月的产量，留意" % months
        else:
            verdict = "正常"
            why = "产出在流动，缓冲正常"

        # 进料侧：全档只有 58/215 家有记录 ⇒ 有才列，没有就明说数据缺口（不硬判缺料）
        in_note = None
        if is_plant:
            if slot["in"] > 0:
                in_now = slot["in_wait"] + slot["in_on"] + slot["in_other"]
                if in_now:
                    in_note = "进料 %d 件，其中 %.0f%% 卸不下来等着" % (
                        slot["in"], slot["in_wait"] / in_now * 100)
                else:
                    in_note = "进料 %d 件" % slot["in"]
            else:
                in_note = "进料侧无记录（数据缺口，不据此判断）"

        severity = {"停摆": 4, "没人运": 4, "运力不足": 3, "偏紧": 1}.get(verdict, 0)
        rows.append({
            "name": name, "kind": kind, "is_plant": is_plant,
            "level": level, "cap_per_year": cap_per_year,
            "wait": wait, "on": on, "out": slot["out"], "months": months,
            "verdict": verdict, "why": why, "in_note": in_note, "severity": severity,
        })

    # ── 🔴 一条流量记录都没有的产业，不能就这么漏掉 ─────────────────────────────
    # 215 家里有 75 家从来没在 `layer-freight.json` 里当过源头或目标。它们不是"不存在"，
    # 而是"没有任何线路在跟它发生关系"—— 这正是要报出来的事。
    # 分开两档：厂里**存着货**（有人产、没人运）vs **一件存货都没有**（多半没投产）。
    missing = [p for p in industries if p["entity_id"] not in agg]
    for point in missing:
        eid = point["entity_id"]
        name = names.get(eid) or ("产业 %s" % eid)
        kind = kind_of(name)
        recipe = recipes.get(kind) or {}
        level = point.get("level")
        ladder = recipe.get("max_per_level") or []
        cap = ladder[level] if (ladder and isinstance(level, int) and 0 <= level < len(ladder)) else None
        stock = point.get("stock_count")
        has_stock = isinstance(stock, int) and stock > 0
        if has_stock:
            verdict = "没人运"
            why = "厂里存着 %d 件货，而整份流量表里一条记录都没有 —— 没有任何线路在运这家的货" % stock
        else:
            # ⚠️ 这里**不能**叫"停摆" —— 那是"有流量记录但产出为 0"的意思。这一档是
            #    一条记录都没有，多半没投产 / 刚建好还没接线路，措辞要留余地。
            verdict = "无流量"
            why = "整份流量表里一条记录都没有，厂里也没有存货 —— 多半没投产，或刚建好还没接线路"
        # 没流量时，"堆了几个月"只能拿厂内存货当分子（口径与上面那半张表不同，注明）
        months = (stock / (cap / 12.0)) if (has_stock and cap) else None
        rows.append({
            "name": name, "kind": kind, "is_plant": bool(recipe.get("inputs")),
            "level": level, "cap_per_year": cap,
            "wait": stock if has_stock else 0, "on": 0, "out": 0,
            "months": months, "verdict": verdict, "why": why, "in_note": None,
            "severity": 4,
        })

    # 🔴 两个筛选必须放在**补齐之后** —— 放在前面的话，"无流量"那批绕过了筛选，
    #    `--only-plant` 里会冒出一堆煤矿铁矿（2026-10-02 自己测出来的）。
    if args.only_plant:
        rows = [r for r in rows if r["is_plant"]]
    if args.only_raw:
        rows = [r for r in rows if not r["is_plant"]]

    rows.sort(key=lambda r: (-r["severity"], -(r["months"] or 0)))

    scope = "全部产业"
    if args.only_plant:
        scope = "只看要进料的加工厂"
    elif args.only_raw:
        scope = "只看纯采集的原料厂"
    detail = ("" if (args.only_plant or args.only_raw)
              else "（= 有流量记录的 %d 家 + 一条记录都没有的 %d 家）" % (len(agg), len(missing)))
    print("产业运转诊断 · %s：%d 家%s" % (scope, len(rows), detail))
    print("判据：出货侧堆积量 ÷ 年产量上限 = 堆了几个月的产量\n")
    print("%-20s %-7s %-4s %9s %7s %7s %8s  结论"
          % ("产业", "类型", "级", "年产上限", "等待", "在途", "堆压月"))
    print("-" * 112)
    for row in rows[:args.top]:
        print("%-20s %-7s %-4s %9s %7d %7d %8s  %s：%s" % (
            row["name"][:20], KIND_LABEL[row["kind"]],
            ("%d" % (row["level"] + 1)) if isinstance(row["level"], int) else "?",
            row["cap_per_year"] if row["cap_per_year"] else "-",
            row["wait"], row["on"],
            ("%.1f" % row["months"]) if row["months"] is not None else "-",
            row["verdict"], row["why"]))

    print("\n汇总")
    buckets = collections.Counter(r["verdict"] for r in rows)
    for name in VERDICT_ORDER:
        if not buckets.get(name):
            continue
        hit = [r["name"] for r in rows if r["verdict"] == name]
        print("  %-6s %3d 家   %s" % (name, len(hit), "、".join(hit[:6]) + ("…" if len(hit) > 6 else "")))

    # 自检：各档之和必须等于总家数 —— 新加一档忘了登记时立刻能看出来
    total = sum(buckets.values())
    if total != len(rows):
        print("  ⚠️ 分档之和 %d ≠ 总家数 %d —— 有档位没登记进 VERDICT_ORDER" % (total, len(rows)))

    # 进料侧单独说清楚 —— 别让它混进上面那份"运转结论"里
    plants = [r for r in rows if r["is_plant"]]
    with_in = [r for r in plants if r["in_note"] and "无记录" not in r["in_note"]]
    if plants:
        print("\n进料侧（加工厂 %d 家）" % len(plants))
        print("  有进料记录的 %d 家：%s" % (
            len(with_in),
            "；".join("%s %s" % (r["name"], r["in_note"]) for r in with_in[:4]) or "无"))
        print("  其余 %d 家无记录 ⇒ **数据缺口**（全档仅 58/215 家有），本表不据此判断缺料"
              % (len(plants) - len(with_in)))

    # ── 导出 Markdown 清单（全部，不受 --top 限制）─────────────────────────────
    if args.report:
        L = []
        L.append("# 产业运转诊断（全部 %d 家）" % len(rows))
        L.append("")
        L.append("判据：**堆压月数 = 出货侧等待量 ÷ 年产量上限**，"
                 "年产量上限 = `capacity × Σ产出量 × 当前等级`（出处见脚本 docstring）。")
        L.append("")
        L.append("| 结论 | 家数 |")
        L.append("|---|---|")
        for name in VERDICT_ORDER:
            if buckets.get(name):
                L.append("| %s | %d |" % (name, buckets[name]))
        L.append("")
        L.append("| 产业 | 类型 | 等级 | 年产量上限 | 等待 | 在途 | 堆压月数 | 结论 | 说明 |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for row in rows:
            L.append("| %s | %s | %s | %s | %d | %d | %s | %s | %s |" % (
                row["name"], KIND_LABEL[row["kind"]],
                (row["level"] + 1) if isinstance(row["level"], int) else "?",
                row["cap_per_year"] or "—", row["wait"], row["on"],
                ("%.1f" % row["months"]) if row["months"] is not None else "—",
                row["verdict"], row["why"]))
        L.append("")
        L.append("进料侧（加工厂 %d 家）：有记录 %d 家，其余 %d 家为**数据缺口**"
                 "（全档仅 58/215 家有），本表不据此判缺料。"
                 % (len(plants), len(with_in), len(plants) - len(with_in)))
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write("\n".join(L) + "\n")
        print("\n清单已写入：%s（%d 行）" % (args.report, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
