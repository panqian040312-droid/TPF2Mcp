"""检查两条平行轨道之间是否存在跨线道岔（横向连接），以及两端分叉点结构。只读。"""
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
A, B = set(nd1), set(nd2)

print(f"A 轨(货运 7.90km) 节点 {len(A)} 个；B 轨(客运 9.03km) 节点 {len(B)} 个；共享 {len(A & B)} 个")
print()

# 跨线边：一端在 A，一端在 B
cross = []
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    if (a in A and b in B) or (a in B and b in A):
        L = math.hypot(pos[a]["x"] - pos[b]["x"], pos[a]["y"] - pos[b]["y"])
        cross.append((e["entity_id"], a, b, round(L, 1)))
print(f"=== 跨线边（一端在 A、一端在 B，即横向连接/道岔）===")
print(f"数量: {len(cross)}")
for c in cross[:20]:
    na, nb = c[1], c[2]
    print(f"  edge {c[0]}: {na} <-> {nb}  长 {c[3]} m")
print()

print("=== 两端分叉点的连接情况 ===")
for nd in (n0, n1):
    print(f"\n节点 {nd} (坐标 x={pos[nd]['x']:.1f}, y={pos[nd]['y']:.1f}) 度数 {len(adj[nd])}:")
    for v, eid, d in adj[nd]:
        side = "A轨" if v in A else ("B轨" if v in B else "其他")
        print(f"  --edge {eid}--> node {v} ({side})  长 {d:.1f} m")
print()

print("=== 车站站台轨道与其他节点的连接（Omsk 货运 3 台）===")
for t in sa["terminals"]:
    nd = t["node_id"]
    print(f"\n站台节点 {nd} 度数 {len(adj[nd])}:")
    for v, eid, d in adj[nd]:
        side = "A轨" if v in A else ("B轨" if v in B else "其他")
        print(f"  --edge {eid}--> node {v} ({side})  长 {d:.1f} m")
