"""完整版：逐站对算实际路径，判断哪些段真的经过主走廊、走哪个方向。只读。"""
import heapq
import json
import math
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
eall = {e["entity_id"]: e for e in net["edges"]}
stn = {s["entity_id"]: s for s in net["stations"]}

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
    return edges, dist[dst]


sa = [s for s in net["stations"] if s["name"] == "Omsk" and s["terminals"][0].get("cargo")][0]
sb = [s for s in net["stations"] if s["name"] == "Foshan" and s["terminals"][0].get("cargo")][0]
n0, n1 = sa["terminals"][0]["node_id"], sb["terminals"][0]["node_id"]
eA, dA = dij(n0, n1)
RANK = {e: i for i, e in enumerate(eA)}          # A 轨链上位置
ASET = set(eA)

LINE_STOPS = {}
for L in net["lines"]:
    groups = [stn.get(st["station_group_id"]) for st in L["stops"]]
    kinds = [("货运" if s["terminals"][0].get("cargo") else "客运") for s in groups if s]
    if not kinds or kinds.count("货运") < kinds.count("客运"):
        continue
    LINE_STOPS[L["entity_id"]] = (L["name"], [s for s in groups if s])

print("=== 各货运线【每一段】是否经过主走廊、方向如何 ===")
for lid, (nm, groups) in sorted(LINE_STOPS.items(), key=lambda kv: kv[1][0]):
    seq = groups + [groups[0]]     # 闭环
    print(f"\n{nm}")
    for i in range(len(seq) - 1):
        ga, gb = seq[i], seq[i + 1]
        if ga is None or gb is None:
            continue
        ta = ga["terminals"][0]["node_id"]
        tb = gb["terminals"][0]["node_id"]
        es, d = dij(ta, tb)
        if es is None:
            print(f"   {ga['name']} → {gb['name']}: 不连通")
            continue
        inA = [e for e in es if e in ASET]
        if not inA:
            print(f"   {ga['name']} → {gb['name']}  ({d/1000:.2f} km): 不经过主走廊")
            continue
        ranks = [RANK[e] for e in inA]
        up = sum(1 for a, b in zip(ranks, ranks[1:]) if b > a)
        dn = sum(1 for a, b in zip(ranks, ranks[1:]) if b < a)
        direction = "朝 Foshan（东行）" if up >= dn else "朝 Omsk（西行）"
        track = "A 轨" if up >= dn else "C 轨（新建）"
        print(f"   {ga['name']} → {gb['name']}  ({d/1000:.2f} km): 经过主走廊 {len(inA)}/{len(es)} 边，"
              f"{direction} → 路径牌放【{track}】")
