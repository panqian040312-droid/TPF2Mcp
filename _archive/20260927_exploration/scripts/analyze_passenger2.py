"""客运运力供给 + 实测服务行为分析（只读，不改游戏）。

关键口径更正（2026-09-27 实测）：
  line.throughput = round(730.5 × 单车容量 ÷ 发车间隔)
  → 它是**运力**（满载口径的理论年输送能力），不是实测运量/客流。
  验证：271 条线路中 269 条精确相等，残差仅为整数取整误差。

本脚本产出：
  1) 客运线路运力基线与排名
  2) 京广走廊三线的运力供给与加车/拆编组效果
  3) 实测服务行为：STOP（停靠）vs PASS（通过不服务）
"""
import json
import sqlite3
from collections import defaultdict, Counter
from pathlib import Path

K = 730.5  # 引擎内部年长常数（= 2 × 365.25），rate = round(K × 容量 / 间隔)
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
snap = json.load(open(MOD / "bridge/state.json", encoding="utf-8"))
net = json.load(open(MOD / "bridge/rail-network.json", encoding="utf-8"))
plan = json.load(open(MOD / "diagnostics/rail-operations/line-timetable-plan.json", encoding="utf-8"))

RAIL = {int(l["entity_id"]) for l in net["lines"]}
LINES = {int(l["entity_id"]): l for l in snap["lines"] if int(l["entity_id"]) in RAIL}
PLAN = {int(p["line_id"]): p for p in plan["lines"]}

veh = defaultdict(list)
for v in snap["vehicles"]:
    if v.get("line_id") in LINES:
        veh[v["line_id"]].append(v)


def line_row(lid):
    line = LINES[lid]
    vs = veh[lid]
    n = len(vs)
    seats = sum((c.get("capacity") or 0) for v in vs for c in (v.get("capacity_by_cargo") or []) if c.get("cargo_id") == 0)
    tons = sum((c.get("capacity") or 0) for v in vs for c in (v.get("capacity_by_cargo") or []) if c.get("cargo_id") != 0)
    cars = max((len(v.get("consist_parts") or []) for v in vs), default=0)
    hw = line.get("frequency_seconds") or 0
    return dict(id=lid, name=line["name"], vehicles=n, cars=cars, stops=line.get("stop_count") or 0,
                seats=seats, seats_per_train=seats / n if n else 0, tons=tons,
                headway=hw, rate=line.get("throughput") or 0,
                capacity_verified=round(K * (seats / n if n else 0) / hw) if n and hw else 0,
                speed=(PLAN.get(lid) or {}).get("speed_class_kmh"))


allrows = [line_row(lid) for lid in LINES if veh.get(lid)]
pax = sorted([r for r in allrows if r["seats"] > 0], key=lambda r: -r["rate"])
frt = [r for r in allrows if r["seats"] == 0]

print("=== 一、客运线路：运力供给（吞吐量 = 运力，非客流）===")
h = f"{'线路':<13}{'车':>3}{'节/列':>6}{'座位/列':>8}{'站':>4}{'间隔(UI分)':>10}{'吞吐量=年运力':>13}{'每车年运力':>10}{'速度档':>7}"
print(h); print("-" * len(h))
for r in pax:
    print(f"{r['name'][:12]:<13}{r['vehicles']:>3}{r['cars']:>6}{r['seats_per_train']:>8.0f}{r['stops']:>4}"
          f"{r['headway']/60:>10.1f}{r['rate']:>13}{r['rate']/r['vehicles']:>10.0f}{str(r['speed'] or '-'):>7}")
tot_seats = sum(r["seats_per_train"] for r in pax)
print(f"\n客运线路 {len(pax)} 条：合计 {sum(r['vehicles'] for r in pax)} 辆、"
      f"合计年运力 {sum(r['rate'] for r in pax):,}、平均单列座位 {tot_seats/len(pax):.0f}")
print(f"货运线路 {len(frt)} 条：合计 {sum(r['vehicles'] for r in frt)} 辆、"
      f"合计年运力 {sum(r['rate'] for r in frt):,}（单位=货件）")

print("\n=== 二、京广走廊：三线运力供给与调车效果 ===")
corridor = [r for r in pax if r["name"] in ("京广客运", "JY客运", "JI线路")]
print(f"{'线路':<12}{'车':>3}{'座位/列':>8}{'间隔UI分':>9}{'年运力':>9}   调车后的年运力")
for r in corridor:
    print(f"{r['name'][:11]:<12}{r['vehicles']:>3}{r['seats_per_train']:>8.0f}{r['headway']/60:>9.1f}{r['rate']:>9}")
print()
for r in corridor:
    n = r["vehicles"]
    hw = r["headway"]
    # 情景A：车辆数不变、拆小编组（总座位不变，间隔 = 原周期/车数 → 若车数不变则不变）
    # 情景B：加一列同型车（总座位增加一列，间隔 = 原间隔 × n/(n+1)）
    add_hw = hw * n / (n + 1)
    add_rate = round(K * (r["seats_per_train"]) / add_hw) * (n + 1) / (n + 1) * 1  # 每列车运力不变，班次变多
    print(f"  {r['name']}: 现 {n} 列 / {hw/60:.1f} 分 → 加 1 列后 {n+1} 列 / {add_hw/60:.1f} 分，"
          f"年运力 {r['rate']} → {round(r['rate']*(n+1)/n)}（+{round((r['rate']*(n+1)/n)/r['rate']*100-100)}%）")
jg = [r for r in corridor if r["name"] == "京广客运"][0]
print(f"\n  京广客运 16 节拆成两列 8 节：总座位不变（{jg['seats']:.0f}），间隔 {jg['headway']/60:.1f} → "
      f"{jg['headway']/2/60:.1f} 分，年运力 {jg['rate']} → {round(jg['rate']*2)}（翻倍，不花钱）")

print("\n=== 三、实测服务行为（station_events.sqlite3，68 分钟实采）===")
# 先把库复制到本地再读：游戏运行中 WAL 会锁住原库
import shutil
tmpdir = Path(r"E:\workbody\TPF2Mcp\_tmpdb")
tmpdir.mkdir(exist_ok=True)
local_db = tmpdir / "station-events.sqlite3"
shutil.copy2(MOD / "bridge/station-events.sqlite3", local_db)
con = sqlite3.connect(str(local_db))
con.row_factory = sqlite3.Row
ev = [dict(x) for x in con.execute("select * from station_events")]
print(f"事件 {len(ev)} 条：STOP（停靠）{sum(1 for e in ev if e['event_type']=='STOP')}、"
      f"PASS（通过不服务）{sum(1 for e in ev if e['event_type']=='PASS')}")

pair = defaultdict(Counter)
for e in ev:
    pair[(e["line_name"], e["station_name"])][e["event_type"]] += 1
stops_per_line = defaultdict(set)
for e in ev:
    if e["event_type"] == "STOP":
        stops_per_line[e["line_name"]].add(e["station_name"])
passes_per_line = defaultdict(set)
for e in ev:
    if e["event_type"] == "PASS":
        passes_per_line[e["line_name"]].add(e["station_name"])

print("\n走廊三线：实际停靠站数 vs 途经不服务的站")
for name in ("京广客运", "JY客运", "JI线路"):
    cfg = [r for r in corridor if r["name"] == name][0]
    print(f"  {name}: 配置 {cfg['stops']} 站 | 实测停靠 {len(stops_per_line[name])} 站 "
          f"{sorted(stops_per_line[name])}")
    extra = sorted(passes_per_line[name] - stops_per_line[name])
    if extra:
        print(f"      途经但不停：{extra}")

print("\n全线网：被本线穿过却不停靠（PASS）最多的站点")
st_pass = Counter()
for (ln, st), c in pair.items():
    if c["PASS"] and not c["STOP"]:
        st_pass[st] += c["PASS"]
for st, c in st_pass.most_common(10):
    lines = sorted({ln for (l2, s2), cc in pair.items() if s2 == st and cc["PASS"] for ln in [l2]})
    print(f"  {st:<16} 通过 {c:>3} 次，涉及线路 {len(lines)} 条：{'、'.join(lines[:4])}")
