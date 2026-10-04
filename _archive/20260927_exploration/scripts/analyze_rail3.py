"""第三轮：规模聚合与密度指标。只读。"""
import json
from collections import defaultdict
from math import hypot

M = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
B = M + r"\bridge"
OUT = []


def p(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


net = load(B + r"\rail-network.json")
live = load(B + r"\live-rail-state.json")
snap = load(B + r"\state.json")
ctl = load(B + r"\rail-control-state.json")

nodes = {n["entity_id"]: n for n in net["nodes"]}
print("node keys:", list(next(iter(nodes.values())).keys()))

# 轨道总长（用节点坐标近似）
total = 0.0
for e in net["edges"]:
    a, b = nodes.get(e["node0"]), nodes.get(e["node1"])
    if not a or not b:
        continue
    pa, pb = a.get("position") or a, b.get("position") or b
    if "x" in pa and "x" in pb:
        total += hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
p("轨道总长(km)", round(total / 1000, 1))

diag = live["line_diagnostics"]
lens = [(d["name"], (d.get("route_length_m") or 0) / 1000, d["vehicle_count"]) for d in diag]
p("线路总里程(km, 按线路里程求和)", round(sum(l for _, l, _ in lens), 1))
p("线路平均配车", round(sum(v for _, _, v in lens) / len(lens), 2))
one = [x for x in lens if x[2] == 1]
two = [x for x in lens if x[2] == 2]
p("配车=1 的线", len(one), "| 配车=2", len(two), "| 配车>=3", len([x for x in lens if x[2] >= 3]))
p("里程最长的 5 条:", sorted(lens, key=lambda x: -x[1])[:5])

pax = [x for x in lens if "客运" in str(x[0])]
p("客运线", len(pax), "平均配车", round(sum(v for _, _, v in pax) / max(len(pax), 1), 2), "平均里程km",
  round(sum(l for _, l, _ in pax) / max(len(pax), 1), 1))

# 编组
veh = snap["vehicles"]
rail_ids = {int(l["entity_id"]) for l in net["lines"]}
rail_v = [v for v in veh if v.get("line_id") in rail_ids]
parts = [len(v.get("consist_parts") or []) for v in rail_v]
p("在册铁路车辆", len(rail_v), "| 平均编组节数", round(sum(parts) / max(len(parts), 1), 2),
  "| 单节车(1节)数量", parts.count(1))
# 车辆 name 前缀统计
pref = defaultdict(int)
for v in rail_v:
    pref[str(v.get("name"))[:2]] += 1
p("铁路车辆名前缀 top:", sorted(pref.items(), key=lambda kv: -kv[1])[:8])

# 车站：每条线的停站数 & 平均站距
st = [(d["name"], len([s for s in next(l["stops"] for l in net["lines"] if l.get("name") == d["name"])]) if any(l.get("name") == d["name"] for l in net["lines"]) else 0) for d in diag]
p("平均停站数", round(sum(c for _, c in st) / max(len(st), 1), 2), "| 最少", min(c for _, c in st), "| 最多", max(c for _, c in st))

p("信号机", len(ctl["signals"]), "| 每公里信号机", round(len(ctl["signals"]) / max(total / 1000, 1), 2))
p("闭塞区间", len(ctl["blocks"]), "| 每公里闭塞分区", round(len(ctl["blocks"]) / max(total / 1000, 1), 2))

with open(r"E:\workbody\TPF2Mcp\rail_analysis_raw3.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(OUT))
