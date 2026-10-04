"""检查主干走廊的备用路径上是否有车站，判断能否用于分流。只读。"""
import heapq
import json
import math
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
adj = collections.defaultdict(list)
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    d = math.hypot(pos[a]["x"] - pos[b]["x"], pos[a]["y"] - pos[b]["y"])
    adj[a].append((b, e["entity_id"], d))
    adj[b].append((a, e["entity_id"], d))

n2st = {}
for s in net["stations"]:
    for t in s["terminals"]:
        n2st[t["node_id"]] = (s["name"], "货运" if t.get("cargo") else "客运")


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


# Omsk 货运 / Foshan 货运
sa = [s for s in net["stations"] if s["name"] == "Omsk" and s["terminals"][0].get("cargo")][0]
sb = [s for s in net["stations"] if s["name"] == "Foshan" and s["terminals"][0].get("cargo")][0]
n0 = sa["terminals"][0]["node_id"]
n1 = sb["terminals"][0]["node_id"]
e1, d1, nd1 = dij(n0, n1)
e2, d2, nd2 = dij(n0, n1, banned=frozenset(e1))
print(f"主路径 {d1/1000:.2f} km，节点 {len(nd1)}")
print(f"备选路径 {d2/1000:.2f} km，节点 {len(nd2)}")
hit_alt = [(n2st[n]) for n in nd2 if n in n2st]
hit_main = [(n2st[n]) for n in nd1 if n in n2st]
print(f"  主路径上经过的站台: {hit_main}")
print(f"  备选路径上经过的站台: {hit_alt if hit_alt else '（一个车站都没有）'}")
print()
# 主路径上被哪 5 条线走
print("主路径 vs 备选路径 的节点重合度:")
print(f"  共享节点 {len(set(nd1) & set(nd2))} 个")
mid1 = {(pos[n]['x'], pos[n]['y']) for n in nd1}
mid2 = {(pos[n]['x'], pos[n]['y']) for n in nd2}
print(f"  起点终点是否相同: 起 {nd1[0]==nd2[0]}, 终 {nd1[-1]==nd2[-1]}")
