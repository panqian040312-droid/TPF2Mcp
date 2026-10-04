"""穷举 Omsk 货运站所有站台 -> Foshan 货运站所有站台的所有路径，统计到底有几条独立轨道。只读。"""
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


def dij(src, dst):
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
            nd = du + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = (u, eid)
                heapq.heappush(pq, (nd, v))
    if dst not in dist:
        return None, None
    edges = []
    cur = dst
    while cur != src:
        p, eid = prev[cur]
        edges.append(eid)
        cur = p
    edges.reverse()
    return edges, dist[dst]


oa = [s for s in net["stations"] if s["name"] == "Omsk" and s["terminals"][0].get("cargo")][0]
fb = [s for s in net["stations"] if s["name"] == "Foshan" and s["terminals"][0].get("cargo")][0]
print("Omsk 货运站台:", [t["node_id"] for t in oa["terminals"]])
print("Foshan 货运站台:", [t["node_id"] for t in fb["terminals"]])
print()

seen_paths = {}
print(f"{'Omsk台':>9} -> {'Foshan台':<9}{'km':>7}{'边数':>6}  路径指纹(前3边)")
print("-" * 70)
for t0 in oa["terminals"]:
    for t1 in fb["terminals"]:
        es, d = dij(t0["node_id"], t1["node_id"])
        if es is None:
            print(f"{t0['node_id']:>9} -> {t1['node_id']:<9}   不连通")
            continue
        fp = tuple(sorted(es))
        key = fp
        if key in seen_paths:
            tag = f"  [与 {seen_paths[key]} 相同]"
        else:
            seen_paths[key] = f"{t0['node_id']}->{t1['node_id']}"
            tag = f"  [新路径 #{len(seen_paths)}]"
        print(f"{t0['node_id']:>9} -> {t1['node_id']:<9}{d/1000:>7.2f}{len(es):>6}{tag}")
print()
print(f"==> 共有 {len(seen_paths)} 条不同的轨道走向")
