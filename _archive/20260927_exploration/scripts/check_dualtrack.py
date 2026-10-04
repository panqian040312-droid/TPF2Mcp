"""检测主干走廊内部是否存在平行轨道（复线）。只读。"""
import json
import math
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
top = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json", encoding="utf-8"))
pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
eall = {e["entity_id"]: e for e in net["edges"]}

corr = [x for x in top["corridors"] if len(x["line_names"]) >= 6][0]
es = corr["edge_ids"]
mids = {}
for e in es:
    a, b = eall[e]["node0"], eall[e]["node1"]
    pa, pb = pos[a], pos[b]
    mids[e] = ((pa["x"] + pb["x"]) / 2, (pa["y"] + pb["y"]) / 2, a, b)

pairs = 0
samples = []
for i in range(len(es)):
    for j in range(i + 1, len(es)):
        e1, e2 = es[i], es[j]
        m1, m2 = mids[e1], mids[e2]
        d = math.hypot(m1[0] - m2[0], m1[1] - m2[1])
        if d < 8 and not ({m1[2], m1[3]} & {m2[2], m2[3]}):
            pairs += 1
            if len(samples) < 8:
                samples.append((e1, e2, round(d, 1)))

def elen(e):
    a, b = eall[e]["node0"], eall[e]["node1"]
    return math.hypot(pos[a]["x"] - pos[b]["x"], pos[a]["y"] - pos[b]["y"])

ls = sorted(elen(e) for e in es)
print("走廊总览")
print(f"  边数 {len(es)}, 总长 {sum(ls)/1000:.2f} km, 中位 {ls[len(ls)//2]:.1f} m, 最长 {ls[-1]:.1f} m")
print(f"  平行边对(中点接近且无共享节点): {pairs}")
for s in samples:
    print("   ", s)
print()
print("track_type:", dict(collections.Counter(eall[e]["track_type"] for e in es)))
print("track_resource:", dict(collections.Counter(eall[e]["track_resource_file"] for e in es)))
print("限速(m/s):", dict(collections.Counter(round(eall[e]["speed_limit_mps"]) for e in es)))
print()
# 节点度数（限走廊内）
deg = collections.Counter()
nset = set()
for e in es:
    nset.add(eall[e]["node0"])
    nset.add(eall[e]["node1"])
    deg[eall[e]["node0"]] += 1
    deg[eall[e]["node1"]] += 1
print(f"走廊内节点 {len(nset)} 个，度数分布:", dict(collections.Counter(deg.values())))
print(f"度>=3 的节点数: {sum(1 for v in deg.values() if v >= 3)}")
