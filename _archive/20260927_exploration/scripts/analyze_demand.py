"""以客货运量为核心重做分析：运量 vs 配车/运力，找供不应求与运力闲置。

数据口径（来源：docs/snapshot-schema-v5.md，已与游戏原生 UI 交叉验证）：
  throughput = game.interface.getEntity(line_id).rate = 原生 UI「吞吐量」= 每站年均运送量
不可得（docs/phase8-acceptance.md 明确 UNAVAILABLE）：分线盈利/成本、车辆实际装载、车站候客
"""
import json
from collections import defaultdict

M = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
B = M + r"\bridge"
OUT = []


def p(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def load(x):
    with open(x, encoding="utf-8") as fh:
        return json.load(fh)


snap = load(B + r"\state.json")
net = load(B + r"\rail-network.json")

rail_ids = {int(l["entity_id"]) for l in net["lines"]}
veh_by_line = defaultdict(list)
for v in snap["vehicles"]:
    veh_by_line[v.get("line_id")].append(v)

# 每条线的运力（车辆容量合计、编组）
info = {}
for lid, vs in veh_by_line.items():
    cap = sum(v.get("capacity_total") or 0 for v in vs)
    parts = sum(len(v.get("consist_parts") or []) for v in vs)
    info[lid] = {"veh": len(vs), "cap": cap, "parts": parts}

rows = []
for l in snap["lines"]:
    lid = int(l["entity_id"])
    if lid not in rail_ids:
        continue
    tp = l.get("throughput")
    stops = l.get("stop_count") or 0
    freq = l.get("frequency_seconds")
    i = info.get(lid, {"veh": 0, "cap": 0, "parts": 0})
    annual = (tp or 0) * stops          # 全线年运量估算（每站量 × 站数）
    rows.append({
        "lid": lid, "name": l.get("name"), "veh": i["veh"], "stops": stops,
        "tp": tp, "annual": annual, "freq": freq, "cap": i["cap"], "parts": i["parts"],
        "per_veh": (annual / i["veh"]) if i["veh"] else None,
        "tp_per_veh": (tp / i["veh"]) if i["veh"] else None,
    })

rows.sort(key=lambda r: -(r["tp"] or 0))
p("=== 铁路线按引擎吞吐量排序（每年每站运送量）===")
p(f"{'线路':<14}{'车':>3}{'站':>3}{'吞吐/站·年':>12}{'全线年运量≈':>13}{'每车年运量':>12}{'容量合计':>10}{'班次s':>8}")
for r in rows:
    p(f"{str(r['name'])[:13]:<14}{r['veh']:>3}{r['stops']:>3}{(r['tp'] or 0):>12.0f}"
      f"{r['annual']:>13.0f}{(r['per_veh'] or 0):>12.0f}{r['cap']:>10}{r['freq'] or 0:>8.0f}")

tot_annual = sum(r["annual"] for r in rows)
tot_veh = sum(r["veh"] for r in rows)
p("")
p(f"铁路合计：年运量估算 {tot_annual:,.0f} ｜ 车辆 {tot_veh} ｜ 平均每车年运量 {tot_annual/max(tot_veh,1):,.0f}")

# 全模式对比
all_rows = []
for l in snap["lines"]:
    lid = int(l["entity_id"])
    i = info.get(lid, {"veh": 0, "cap": 0})
    annual = (l.get("throughput") or 0) * (l.get("stop_count") or 0)
    all_rows.append({"name": l.get("name"), "veh": i["veh"], "annual": annual, "rail": lid in rail_ids})
rail = [r for r in all_rows if r["rail"]]
other = [r for r in all_rows if not r["rail"]]
p("")
p("=== 铁路 vs 其他运输方式 ===")
p(f"铁路 {len(rail)} 条：年运量 {sum(r['annual'] for r in rail):,.0f}，车 {sum(r['veh'] for r in rail)}")
p(f"其他 {len(other)} 条：年运量 {sum(r['annual'] for r in other):,.0f}，车 {sum(r['veh'] for r in other)}")
share = sum(r["annual"] for r in rail) / max(sum(r["annual"] for r in all_rows), 1) * 100
p(f"铁路运量占比 {share:.1f}% ｜ 铁路车辆占比 {sum(r['veh'] for r in rail)/max(sum(r['veh'] for r in all_rows),1)*100:.1f}%")

# 分类：供不应求 vs 运力闲置（用「每车年运量」，避免站多的长线被摊薄）
p("")
p("=== 诊断（按每车年运量 = 吞吐×站数÷车数）===")
vals = sorted(r["per_veh"] for r in rows if r["per_veh"])
med = vals[len(vals) // 2]
q1, q3 = vals[len(vals) // 4], vals[len(vals) * 3 // 4]
p(f"每车年运量：中位数 {med:,.0f} ｜ 下四分位 {q1:,.0f} ｜ 上四分位 {q3:,.0f}")
p("")
p("① 车少但运量高（供不应求候选 → 优先加车）")
for r in sorted(rows, key=lambda r: -(r["per_veh"] or 0)):
    if r["per_veh"] and r["per_veh"] >= q3 and r["veh"] <= 2:
        p(f"   {r['name']}：{r['veh']} 车 / {r['stops']} 站，每车年运量 {r['per_veh']:,.0f}，班次 {r['freq']:.0f}s")
p("")
p("② 车多但运量低（运力闲置 / 亏损风险 → 减车、合并或停运）")
for r in sorted(rows, key=lambda r: (r["per_veh"] or 0)):
    if r["per_veh"] and r["per_veh"] <= q1 and r["veh"] >= 2:
        p(f"   {r['name']}：{r['veh']} 车 / {r['stops']} 站，每车年运量 {r['per_veh']:,.0f}，班次 {r['freq']:.0f}s")
p("")
p("③ 运量几乎为零的线（吞吐 < 100，需排查配置/需求）")
found = False
for r in sorted(rows, key=lambda r: (r["tp"] or 0)):
    if (r["tp"] or 0) < 100:
        found = True
        p(f"   {r['name']}：{r['veh']} 车，{r['stops']} 站，吞吐/站 {r['tp']:.0f}")
if not found:
    p("   无（所有铁路线都有实际运量记录）")

p("")
p("=== 效率横向对比：每种运输方式每辆车创造的年运量 ===")
def per_vehicle(rs):
    v = sum(r["veh"] for r in rs)
    return (sum(r["annual"] for r in rs) / v) if v else 0
p(f"铁路：{per_vehicle(rail):,.0f} /车·年")
others = defaultdict(lambda: {"veh": 0, "annual": 0})
for r in other:
    others["其他" if r["veh"] == 0 else "其他"]["veh"] += r["veh"]
    others["其他"]["annual"] += r["annual"]
p(f"其他方式：{per_vehicle(other):,.0f} /车·年")
ratio = per_vehicle(rail) / max(per_vehicle(other), 1)
p(f"→ 铁路单车的运量效率是其他方式的 {ratio:.1f} 倍（铁路用 {sum(r['veh'] for r in rail)/max(sum(r['veh'] for r in all_rows),1)*100:.1f}% 的车，做了 {share:.1f}% 的运量）")

p("")
p("=== 公司级财务（唯一可得的财务口径）===")
c = snap["company"]
p(f"余额 {c['balance']:,.0f} ｜ 贷款 {c['loan']:,.0f} ｜ 快照时间 {snap['timestamp']}")
p("说明：分线收入/成本/利润在项目文档中标记为 UNAVAILABLE，游戏 API 探针返回 nil。")

with open(r"E:\workbody\TPF2Mcp\demand_analysis.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(OUT))
