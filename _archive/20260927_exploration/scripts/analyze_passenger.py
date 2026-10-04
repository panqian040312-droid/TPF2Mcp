"""客流分析：把客运线路单独拎出来，算运量、载客率、发车间隔够不够。

口径说明（全部来自引擎字段，只读）：
- throughput = line.rate = 游戏原生 UI「吞吐量」，游戏文档定义：每站年均运送的客/货量
  → 全线年运量 = rate × 停站数（每站都发生一次运送）
- frequency_seconds = 1/line.frequency，即同线相邻两车的发车间隔（游戏秒）
- millis_per_day = 8000 → 1 游戏日 = 8 游戏秒 → 1 年（365 日）= 2,920 游戏秒
- 车辆载客量 = vehicle.capacity_by_cargo 中 cargo_id=0 (PASSENGERS) 的部分
- 车列年发车次数（全车队）= 2920 / 发车间隔   （因为 headway = cycle / 车数）
- 年载客能力 = 车列年发车次数 × 单车载客量
- 载客率 = 年运量 / 年载客能力
"""
import json
from collections import defaultdict
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
snap = json.load(open(MOD / "bridge/state.json", encoding="utf-8"))
net = json.load(open(MOD / "bridge/rail-network.json", encoding="utf-8"))
plan = json.load(open(MOD / "diagnostics/rail-operations/line-timetable-plan.json", encoding="utf-8"))

CARGO = {c["cargo_id"]: c["cargo_key"] for c in snap["cargo_types"]}
RAIL = {int(l["entity_id"]) for l in net["lines"]}
LINES = {int(l["entity_id"]): l for l in snap["lines"] if int(l["entity_id"]) in RAIL}
PLAN = {int(p["line_id"]): p for p in plan["lines"]}

SEC_PER_DAY = (snap["simulation"]["millis_per_day"] or 8000) / 1000.0   # 8 s/日
YEAR_S = 365 * SEC_PER_DAY
print(f"时间口径：1 游戏日 = {SEC_PER_DAY} 游戏秒；1 年 = {YEAR_S:.0f} 游戏秒")

veh = defaultdict(list)
for v in snap["vehicles"]:
    if v.get("line_id") in LINES:
        veh[v["line_id"]].append(v)

rows = []
for lid, line in LINES.items():
    vs = veh.get(lid, [])
    n = len(vs)
    if not n:
        continue
    mix = defaultdict(float)
    for v in vs:
        for c in (v.get("capacity_by_cargo") or []):
            mix[c.get("cargo_id")] += c.get("capacity") or 0
    seats_total = mix.get(0, 0)
    seats_per_train = seats_total / n
    freight_total = sum(cap for cid, cap in mix.items() if cid != 0)
    headway = line.get("frequency_seconds") or 0
    rate = line.get("throughput") or 0
    stops = line.get("stop_count") or 0
    p = PLAN.get(lid, {})
    annual_vol_per_station = rate * stops          # 全线年运量（每站口径）
    trips_year = YEAR_S / headway if headway else 0  # 全车队年发车次数
    year_capacity = trips_year * seats_per_train if seats_per_train else 0
    lf = annual_vol_per_station / year_capacity if year_capacity else None
    rows.append(dict(
        id=lid, name=line["name"], vehicles=n, stops=stops, rate=rate,
        annual_vol=annual_vol_per_station, rate_x1=rate,
        headway=headway, cycle=headway * n,
        seats_per_train=seats_per_train, seats_total=seats_total,
        freight_total=freight_total,
        trips_year=trips_year, year_capacity=year_capacity, lf=lf,
        service=p.get("service_class"), speed=p.get("speed_class_kmh"),
    ))

pax = [r for r in rows if r["seats_total"] > 0]
frt = [r for r in rows if r["seats_total"] == 0]
mix_lines = [r for r in rows if 0 < r["seats_total"] and r["freight_total"] > 0]

print(f"\n铁路线路 {len(rows)} 条：纯客运 {len(pax) - len(mix_lines)}、客货混装 {len(mix_lines)}、纯货运 {len(frt)}")
print("\n=== 载客率分布自检（判断年份口径是否合理）===")
lfs = sorted((r["lf"] for r in pax if r["lf"]), reverse=True)
if lfs:
    print("  前 10 高载客率:", " ".join(f"{x*100:.0f}%" for x in lfs[:10]))
    print("  中位数:", f"{lfs[len(lfs)//2]*100:.0f}%", "| 最大:", f"{lfs[0]*100:.0f}%")
    print(f"  若假定最忙线路载客率=100%，则 1 年应为 {YEAR_S / lfs[0]:.0f} 游戏秒（当前用 {YEAR_S:.0f}）")

print("\n=== 客运线路（按年运量降序）===")
hdr = f"{'线路':<14}{'车':>3}{'节/列':>6}{'站':>4}{'吞吐/站年':>10}{'全线年运量':>11}{'座位/列':>8}{'间隔s':>7}{'班次min':>8}{'年发车':>7}{'年载客力':>10}{'载客率':>7}"
print(hdr)
print("-" * len(hdr))


def consist(r):
    vs = veh[r["id"]]
    cars = [len(v.get("consist_parts") or []) for v in vs]
    return max(cars) if cars else 0


for r in sorted(pax, key=lambda x: -x["annual_vol"]):
    print(f"{r['name'][:13]:<14}{r['vehicles']:>3}{consist(r):>6}{r['stops']:>4}{r['rate']:>10}"
          f"{r['annual_vol']:>11,.0f}{r['seats_per_train']:>8.0f}{r['headway']:>7.0f}{r['headway']/60:>8.1f}"
          f"{r['trips_year']:>7.1f}{r['year_capacity']:>10,.0f}{(r['lf']*100 if r['lf'] else 0):>6.0f}%")

print("\n=== 纯货运线路（对照，按年运量降序前 12）===")
hdr2 = f"{'线路':<14}{'车':>3}{'站':>4}{'吞吐/站年':>10}{'全线年运量':>11}{'载重/列':>9}{'座位/列':>8}"
print(hdr2)
for r in sorted(frt, key=lambda x: -x["annual_vol"])[:12]:
    print(f"{r['name'][:13]:<14}{r['vehicles']:>3}{r['stops']:>4}{r['rate']:>10}{r['annual_vol']:>11,.0f}"
          f"{r['freight_total']/r['vehicles']:>9.0f}{r['seats_per_train']:>8.0f}")

print("\n=== 客运汇总 ===")
tot_v = sum(r["vehicles"] for r in pax)
tot_vol = sum(r["annual_vol"] for r in pax)
tot_cap = sum(r["year_capacity"] for r in pax)
print(f"  客运线路 {len(pax)} 条 / 车辆 {tot_v} 辆 / 年运量 {tot_vol:,.0f} 人次 / 年载客能力 {tot_cap:,.0f} 座位")
print(f"  整体载客率 {tot_vol/tot_cap*100 if tot_cap else 0:.1f}%")
tf = sum(r["vehicles"] for r in frt)
tfv = sum(r["annual_vol"] for r in frt)
print(f"  货运线路 {len(frt)} 条 / 车辆 {tf} 辆 / 年运量 {tfv:,.0f} 吨")
print(f"  客运每车年运量 {tot_vol/tot_v:,.0f} 人次 vs 货运每车年运量 {tfv/tf:,.0f} 吨")

json.dump({"year_seconds": YEAR_S, "lines": rows}, open(r"E:\workbody\TPF2Mcp\passenger_analysis.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n已写出 passenger_analysis.json")
