"""统计每个车站同一时刻停放的车数（对比站台数），判断该扩哪个站。只读。"""
import json
import collections

BRIDGE = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(BRIDGE + r"\rail-network.json", encoding="utf-8"))
data = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\traffic_frames.json", encoding="utf-8"))
frames = data["frames"]

stn = {s["entity_id"]: s for s in net["stations"]}
# 每条线的站序：stop_index -> (站名, 站台数, 客/货)
line_stops = {}
for L in net["lines"]:
    seq = []
    for st in L["stops"]:
        s = stn.get(st["station_group_id"])
        if s:
            seq.append((s["name"], len(s["terminals"]), "货运" if s["terminals"][0].get("cargo") else "客运"))
        else:
            seq.append(("?", 0, "?"))
    line_stops[L["entity_id"]] = seq

# 逐帧统计每站有多少车处于"停站"状态
occ = collections.defaultdict(list)
for fr in frames:
    per = collections.Counter()
    for v in fr["vehicles"]:
        if v["raw"] != 2:          # 只在停站状态计数
            continue
        seq = line_stops.get(v["line"])
        if not seq:
            continue
        idx = v.get("stop")
        if idx is None or idx < 0 or idx >= len(seq):
            continue
        nm, npf, kind = seq[idx]
        per[(nm, npf, kind)] += 1
    for key, c in per.items():
        occ[key].append(c)

print("=== 各站『同时停站车辆数』峰值 vs 站台数 ===")
print(f"{'车站':<20}{'类型':<5}{'站台':>5}{'峰值占车':>9}{'平均':>7}{'均值/站台':>10}")
print("-" * 62)
rows = []
for (nm, npf, kind), series in occ.items():
    peak = max(series)
    avg = sum(series) / len(series)
    rows.append((peak, avg, npf, nm, kind))
for peak, avg, npf, nm, kind in sorted(rows, reverse=True):
    flag = ""
    if npf and peak > npf:
        flag = "  <== 峰值超站台"
    elif npf and avg / npf > 0.8:
        flag = "  <== 常年接近满"
    print(f"{nm:<20}{kind:<5}{npf:>5}{peak:>9}{avg:>7.2f}{avg/npf if npf else 0:>10.2f}{flag}")
print()
print("说明：只统计 raw_state=2（在站停靠）的车。峰值 > 站台数说明确实在排队等站台。")
