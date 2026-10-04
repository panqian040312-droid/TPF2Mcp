"""重建新存档 16 条铁路线的实际走行路径，找出多线共用的单线走廊（潜在堵点）。只读。

输出: _tmpdb/rail_topology.json
"""
import heapq
import json
import math
import collections

BRIDGE = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
OUT = r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json"

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


def shortest(src, dst):
    """Dijkstra，返回 (edge 序列, 总长)。"""
    if src == dst:
        return [], 0.0
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


stations = {s["entity_id"]: s for s in net["stations"]}
# 站台轨道节点 -> 车站名（用于把走廊落到具体车站）
n2station = {}
for s in net["stations"]:
    for t in s["terminals"]:
        n2station[t["node_id"]] = s["name"]
report = {"lines": [], "edge_use": {}, "shared": [], "errors": []}
edge_use = collections.defaultdict(set)
edge_line_reach = collections.defaultdict(lambda: collections.defaultdict(int))

for L in net["lines"]:
    lid = L["entity_id"]
    seq = [(st["node_id"], st["station_group_id"]) for st in L["stops"]]
    all_edges = []
    total = 0.0
    ok = True
    for i in range(len(seq) - 1):
        a, _ = seq[i]
        b, _ = seq[i + 1]
        edges, d = shortest(a, b)
        if edges is None:
            report["errors"].append({"line": L["name"], "from": a, "to": b})
            ok = False
            continue
        all_edges += edges
        total += d
    if ok:
        for eid in all_edges:
            edge_use[eid].add(lid)
    names = []
    for _, gid in seq:
        s = stations.get(gid)
        names.append(s["name"] if s else "?")
    report["lines"].append({
        "line_id": lid,
        "name": L["name"],
        "stops": names,
        "path_edges": len(all_edges),
        "path_length_m": round(total, 1),
        "unique_edges": len(set(all_edges)),
        "reused_edges": len(all_edges) - len(set(all_edges)),
    })

report["edge_use"] = {str(k): sorted(v) for k, v in edge_use.items() if len(v) > 1}

# 把共用边按"连通块"聚成走廊
shared = {k: set(v) for k, v in edge_use.items() if len(v) > 1}
node2shared = collections.defaultdict(set)
eid2nodes = {}
for e in net["edges"]:
    if e["entity_id"] in shared:
        eid2nodes[e["entity_id"]] = (e["node0"], e["node1"])
        node2shared[e["node0"]].add(e["entity_id"])
        node2shared[e["node1"]].add(e["entity_id"])

seen = set()
corridors = []
for eid in shared:
    if eid in seen:
        continue
    stack = [eid]
    comp = []
    seen.add(eid)
    while stack:
        cur = stack.pop()
        comp.append(cur)
        for nd in eid2nodes[cur]:
            for nb in node2shared[nd]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
    lines_in = set()
    length = 0.0
    for e in comp:
        lines_in |= shared[e]
        length += elen[e]
    # 这条走廊覆盖了哪些车站（按停站节点）
    cnodes = set()
    for e in comp:
        cnodes.update(eid2nodes[e])
    hit_stations = sorted({n2station[n] for n in cnodes if n in n2station})
    corridors.append({
        "edges": len(comp),
        "edge_ids": sorted(comp),
        "length_m": round(length, 1),
        "line_ids": sorted(lines_in),
        "line_names": sorted({next(l["name"] for l in net["lines"] if l["entity_id"] == x) for x in lines_in}),
        "stations": hit_stations,
    })
corridors.sort(key=lambda c: (-len(c["line_names"]), -c["length_m"]))
report["corridors"] = corridors

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=1)

print(f"线路 {len(report['lines'])} 条，未连通 {len(report['errors'])} 段")
print()
print(f"{'线名':<16}{'站':>3}{'路径边':>7}{'路径km':>8}{'重复边':>7}")
for r in sorted(report["lines"], key=lambda x: x["name"]):
    print(f"{r['name']:<16}{len(r['stops']):>3}{r['path_edges']:>7}{r['path_length_m']/1000:>8.1f}{r['reused_edges']:>7}")
print()
print(f"被 ≥2 条线共用的边: {len(shared)} / {len(net['edges'])}")
print()
print("=== 共用走廊（按线路数排序）===")
for c in corridors[:15]:
    print(f"  {len(c['line_names'])} 线 × {c['length_m']/1000:>6.2f} km | 边{c['edges']:>4} | {' + '.join(c['line_names'])}")
