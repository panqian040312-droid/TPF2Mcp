"""检查主干走廊的备用路径上现在有哪些线路在跑，判断能否分流。只读。"""
import heapq
import json
import math
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
top = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json", encoding="utf-8"))
pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
adj = collections.defaultdict(list)
elen = {}
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    d = math.hypot(pos[a]["x"] - pos[b]["x"], pos[a]["y"] - pos[b]["y"])
    elen[e["entity_id"]] = d
    adj[a].append((b, e["entity_id"], d))
    adj[b].append((a, e["entity_id"], d))

names = {l["entity_id"]: l["name"] for l in net["lines"]}
use = {int(k): set(v) for k, v in top["edge_use"].items()}


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
# 找 Omsk 与 Foshan 的节点
def find(name):
    return [s for s in net["stations"] if s["name"] == name]

for a_name, b_name in [("Omsk", "Foshan"), ("Zhengzhou", "Omsk")]:
    A = find(a_name)
    B = find(b_name)
    for sa in A:
        for sb in B:
            if sa["terminals"][0].get("cargo") != sb["terminals"][0].get("cargo"):
                continue
            n0 = sa["terminals"][0]["node_id"]
            n1 = sb["terminals"][0]["node_id"]
            e1, d1 = dij(n0, n1)
            if e1 is None:
                continue
            e2, d2 = dij(n0, n1, banned=frozenset(e1))
            kind = "货运" if sa["terminals"][0].get("cargo") else "客运"
            print(f"=== {a_name}({kind}) → {b_name}({kind}) ===")
            print(f"  主路径 {d1/1000:.2f} km，被线共用情况：")
            lines_main = set()
            for e in e1:
                lines_main |= use.get(e, set())
            print(f"    经过的边中被共用的数量: {sum(1 for e in e1 if e in use)}/{len(e1)}")
            print(f"    使用者: {' + '.join(sorted(names[l] for l in lines_main)) or '(无线路用)'}")
            if e2:
                lines_alt = set()
                for e in e2:
                    lines_alt |= use.get(e, set())
                print(f"  备选路径 {d2/1000:.2f} km（倍率 {d2/d1:.2f}），使用者:")
                print(f"    {' + '.join(sorted(names[l] for l in lines_alt)) or '（无任何线路使用 —— 完全闲置！）'}")
            print()
            break
