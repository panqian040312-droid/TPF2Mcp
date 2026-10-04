"""检测站对之间是否存在平行轨道（双向/多线），判断能否靠改线分流。只读。"""
import heapq
import json
import math
import collections

BRIDGE = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
with open(BRIDGE + r"\rail-network.json", encoding="utf-8") as fh:
    net = json.load(fh)

pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
adj = collections.defaultdict(list)
elen = {}
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    pa, pb = pos[a], pos[b]
    d = math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
    elen[e["entity_id"]] = d
    adj[a].append((b, e["entity_id"], d))
    adj[b].append((a, e["entity_id"], d))


def dijkstra(src, dst, banned=frozenset()):
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
        return None, None
    edges = []
    cur = dst
    while cur != src:
        p, eid = prev[cur]
        edges.append(eid)
        cur = p
    edges.reverse()
    return edges, dist[dst]


stations = {s["entity_id"]: s for s in net["stations"]}
# 收集所有线路用到的"站对"
pairs = collections.Counter()
for L in net["lines"]:
    seq = [st["node_id"] for st in L["stops"]]
    for i in range(len(seq) - 1):
        g0 = L["stops"][i]["station_group_id"]
        g1 = L["stops"][i + 1]["station_group_id"]
        if g0 == g1:
            continue
        key = tuple(sorted((g0, g1)))
        pairs[key] += 1

print(f"{'站对':<36}{'主路径km':>9}{'平行路径km':>11}{'倍率':>7}  结论")
print("-" * 100)
results = []
for (g0, g1), cnt in pairs.most_common():
    n0 = stations.get(g0, {}).get("name", "?"),
    n1 = stations.get(g1, {}).get("name", "?")
    s0 = next((s for s in net["stations"] if s["entity_id"] == g0), None)
    s1 = next((s for s in net["stations"] if s["entity_id"] == g1), None)
    if not s0 or not s1:
        continue
    t0 = s0["terminals"][0]["node_id"]
    t1 = s1["terminals"][0]["node_id"]
    e1, d1 = dijkstra(t0, t1)
    if e1 is None:
        print(f"{s0['name'] + ' - ' + s1['name']:<36}  不连通")
        continue
    e2, d2 = dijkstra(t0, t1, banned=frozenset(e1))
    ratio = (d2 / d1) if d2 else None
    verdict = "无平行线（单线）"
    if d2 is not None and ratio < 1.6:
        verdict = f"有平行线（可分流）"
    results.append({"pair": f"{s0['name']} - {s1['name']}", "main_m": round(d1, 1),
                    "alt_m": round(d2, 1) if d2 else None, "ratio": round(ratio, 2) if ratio else None,
                    "lines": cnt, "verdict": verdict})
    print(f"{s0['name'] + ' - ' + s1['name']:<36}{d1/1000:>9.2f}{(d2/1000 if d2 else 0):>11.2f}"
          f"{(f'{ratio:.2f}' if ratio else '-'):>7}  {verdict}")

with open(r"E:\workbody\TPF2Mcp\_tmpdb\parallel_tracks.json", "w", encoding="utf-8") as fh:
    json.dump(results, fh, ensure_ascii=False, indent=1)
