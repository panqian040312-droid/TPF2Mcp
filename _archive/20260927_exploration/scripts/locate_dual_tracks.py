"""定位两条平行轨道的几何位置与两端接入的站台，供用户在地图上确认。只读。"""
import heapq
import json
import math
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
eall = {e["entity_id"]: e for e in net["edges"]}
names = {l["entity_id"]: l["name"] for l in net["lines"]}

adj = collections.defaultdict(list)
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    d = math.hypot(pos[a]["x"] - pos[b]["x"], pos[a]["y"] - pos[b]["y"])
    adj[a].append((b, e["entity_id"], d))
    adj[b].append((a, e["entity_id"], d))


def dij(src, dst, banned=frozenset()):
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    seen = set()
    while pq:
        du, u = heapq.heappop(pq)
        if u in seen:
            continue
        seen.add(u)
        if u == dst:
            break
        for v, eid, w in adj[u]:
            if eid in banned:
                continue
            nd = du + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = (u, eid)
                heapq.heappush(pq, (nd, v))
    if dst not in dist:
        return None, None, None
    edges, nodes = [], []
    cur = dst
    while cur != src:
        p, eid = prev[cur]
        edges.append(eid)
        nodes.append(cur)
        cur = p
    nodes.append(src)
    edges.reverse()
    nodes.reverse()
    return edges, dist[dst], nodes


sa = [s for s in net["stations"] if s["name"] == "Omsk" and s["terminals"][0].get("cargo")][0]
sb = [s for s in net["stations"] if s["name"] == "Foshan" and s["terminals"][0].get("cargo")][0]
n0, n1 = sa["terminals"][0]["node_id"], sb["terminals"][0]["node_id"]
e1, d1, nd1 = dij(n0, n1)
e2, d2, nd2 = dij(n0, n1, banned=frozenset(e1))

print("=== 两条平行轨道的走向（沿链每 20% 取一个点）===")
for tag, nodes in [("A 短(7.90km 货运)", nd1), ("B 长(9.03km 客运)", nd2)]:
    print(f"\n{tag}:  起点 node {nodes[0]} -> 终点 node {nodes[-1]}")
    step = max(1, len(nodes) // 5)
    for i in range(0, len(nodes), step):
        p = pos[nodes[i]]
        print(f"   {i/len(nodes)*100:>3.0f}%  node={nodes[i]:<8} x={p['x']:>9.1f} y={p['y']:>9.1f}")
print()
print("=== 两条路径中间有无连接（道岔）===")
common = set(nd1) & set(nd2)
print(f"共享节点: {sorted(common)}  (共 {len(common)} 个)")
print(f"A 节点数 {len(nd1)}，B 节点数 {len(nd2)}")
print("若只有起终点共享 -> 两条轨道在中间完全不相连，列车无法中途换线")
print()
print("=== 两端车站各自接了哪些轨道 ===")
n2st = {}
for s in net["stations"]:
    for t in s["terminals"]:
        n2st[t["node_id"]] = (s["name"], "货运" if t.get("cargo") else "客运", t["node_id"])
for nm in ("Omsk", "Foshan", "Zhengzhou", "Kolkata"):
    print(f"\n{nm}:")
    for s in net["stations"]:
        if s["name"] != nm:
            continue
        kind = "货运" if s["terminals"][0].get("cargo") else "客运"
        nodes = [t["node_id"] for t in s["terminals"]]
        inA = [x for x in nodes if x in set(nd1)]
        inB = [x for x in nodes if x in set(nd2)]
        print(f"  {kind}站 站台数 {len(s['terminals'])} 站台节点 {nodes}")
        print(f"    接在 A 短线上: {inA}")
        print(f"    接在 B 长线上: {inB}")
    print()
