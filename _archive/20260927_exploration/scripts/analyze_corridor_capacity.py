"""计算主干走廊的理论最短通过时间（按逐边限速），用于和实测对比。只读。"""
import json
import math

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
top = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json", encoding="utf-8"))
pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
eall = {e["entity_id"]: e for e in net["edges"]}

corr = [x for x in top["corridors"] if len(x["line_names"]) >= 6][0]
es = corr["edge_ids"]

# 按限速分组统计算长度
by_limit = {}
total_l = 0.0
t_min = 0.0
for e in es:
    ed = eall[e]
    a, b = ed["node0"], ed["node1"]
    pa, pb = pos[a], pos[b]
    L = math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
    v = ed["speed_limit_mps"]
    total_l += L
    t_min += L / v
    g = by_limit.setdefault(round(v), [0, 0.0])
    g[0] += 1
    g[1] += L

print(f"走廊 {total_l/1000:.2f} km，{len(es)} 条边")
print(f"按轨道限速理论最短通过时间: {t_min:.1f} 秒（{total_l/t_min:.1f} m/s = {total_l/t_min*3.6:.0f} km/h）")
print()
print(f"{'限速 m/s':>9}{'km/h':>7}{'边数':>6}{'长度 km':>10}{'长度占比':>9}")
for v in sorted(by_limit):
    n, L = by_limit[v]
    print(f"{v:>9}{v*3.6:>7.0f}{n:>6}{L/1000:>10.2f}{L/total_l*100:>8.0f}%")
print()
print("实测参考（佛山原木运输 列车13 的 raw_sectionTimes）:")
print("  Omsk→Foshan        364.8 秒（走廊主体，7.90 km）")
print("  Foshan→Zhengzhou   173.2 秒（4.83 km）")
print("  Zhengzhou→Omsk     190.6 秒（3.07 km）")
print()
# 用列车顶速 160km/h=44.4m/s 也压一遍
v_cap = 160 / 3.6
t_cap = sum(
    math.hypot(
        pos[eall[e]["node0"]]["x"] - pos[eall[e]["node1"]]["x"],
        pos[eall[e]["node0"]]["y"] - pos[eall[e]["node1"]]["y"],
    ) / min(v_cap, eall[e]["speed_limit_mps"])
    for e in es
)
print(f"按列车顶速 160 km/h 与轨道限速取小: 理论最短 {t_cap:.1f} 秒")
