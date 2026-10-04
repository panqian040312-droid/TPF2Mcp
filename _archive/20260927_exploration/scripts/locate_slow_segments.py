"""定位主干走廊内低速轨道段所在的站间区间。只读。"""
import json
import math
import heapq
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
top = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json", encoding="utf-8"))
pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
eall = {e["entity_id"]: e for e in net["edges"]}

# 站台节点 -> 站名
n2st = {}
for s in net["stations"]:
    for t in s["terminals"]:
        n2st[t["node_id"]] = s["name"]

corr = [x for x in top["corridors"] if len(x["line_names"]) >= 6][0]
es = corr["edge_ids"]
# 沿链排序：找到度1的端点，沿链走下去
deg = collections.Counter()
adj = collections.defaultdict(list)
for e in es:
    a, b = eall[e]["node0"], eall[e]["node1"]
    adj[a].append((b, e))
    adj[b].append((a, e))
    deg[a] += 1
    deg[b] += 1
ends = [n for n, d in deg.items() if d == 1]
if len(ends) != 2:
    print("走廊不是简单链，端点数:", len(ends))
    raise SystemExit(0)

order = []
cur, prev = ends[0], None
while True:
    nxt = [(v, e) for v, e in adj[cur] if v != prev]
    if not nxt:
        break
    v, e = nxt[0]
    order.append((cur, v, e))
    prev, cur = cur, v
print(f"走廊链：{len(order)} 段，端点 {n2st.get(ends[0], '?'+str(ends[0]))} → {n2st.get(ends[1], '?'+str(ends[1]))}")
print()
# 累计里程 + 标注慢速段
acc = 0.0
slow = []
station_at = []
for a, b, e in order:
    pa, pb = pos[a], pos[b]
    L = math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
    v = eall[e]["speed_limit_mps"]
    res = eall[e]["track_resource_file"]
    if a in n2st:
        station_at.append((acc, n2st[a]))
        print(f"  [{acc/1000:>6.2f} km] ● {n2st[a]}")
    if v < 60:
        slow.append((round(acc, 1), round(L, 1), round(v * 3.6), res))
    acc += L
if ends[1] in n2st:
    station_at.append((acc, n2st[ends[1]]))
    print(f"  [{acc/1000:>6.2f} km] ● {n2st[ends[1]]}")
print()
print(f"慢速段（< 216 km/h）共 {len(slow)} 段：")
for s in slow[:20]:
    print(f"   里程 {s[0]:>7.1f} m, 长 {s[1]:>6.1f} m, 限速 {s[2]:>4} km/h, {s[3]}")
