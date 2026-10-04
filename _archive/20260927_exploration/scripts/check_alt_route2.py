"""核查主干走廊的备选路径到底是什么：被哪些线路使用、几何上是否与主路径平行。只读。

修正上一版的 bug：之前判断"闲置"用的是只含『被 >=2 条线共用』的边表，
所以"不在表里"≠"没有线路使用"。本脚本用完整映射重算。
"""
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
elen = {}
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    d = math.hypot(pos[a]["x"] - pos[b]["x"], pos[a]["y"] - pos[b]["y"])
    elen[e["entity_id"]] = d
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


# 完整重建：每条线走过哪些边（不过滤）
edge_lines_full = collections.defaultdict(set)
line_paths = {}
for L in net["lines"]:
    lid = L["entity_id"]
    seq = [st["node_id"] for st in L["stops"]]
    all_e = []
    ok = True
    for i in range(len(seq) - 1):
        ed, d, nd = dij(seq[i], seq[i + 1])
        if ed is None:
            ok = False
            break
        all_e += ed
    if ok:
        line_paths[lid] = all_e
        for e in all_e:
            edge_lines_full[e].add(lid)

print(f"完整重建 {len(line_paths)} 条线；被任意线路使用的边 {len(edge_lines_full)} / {len(net['edges'])}")
print()

# Omsk 货运 -> Foshan 货运
sa = [s for s in net["stations"] if s["name"] == "Omsk" and s["terminals"][0].get("cargo")][0]
sb = [s for s in net["stations"] if s["name"] == "Foshan" and s["terminals"][0].get("cargo")][0]
n0, n1 = sa["terminals"][0]["node_id"], sb["terminals"][0]["node_id"]
e1, d1, nd1 = dij(n0, n1)
e2, d2, nd2 = dij(n0, n1, banned=frozenset(e1))

for tag, es, nodes, dist in [("主路径", e1, nd1, d1), ("备选路径", e2, nd2, d2)]:
    used = collections.Counter()
    for e in es:
        for l in edge_lines_full.get(e, ()):  # 完整映射
            used[l] += 1
    print(f"=== {tag} {dist/1000:.2f} km，{len(es)} 条边 ===")
    print(f"  有线路使用的边: {sum(1 for e in es if e in edge_lines_full)} / {len(es)}")
    if used:
        for l, c in used.most_common():
            print(f"    {names[l]:<20} 占用该路径 {c} 条边 ({c/len(es)*100:.0f}%)")
    else:
        print("    确实没有任何线路使用")
    # 几何：与主路径的距离
    mset = {(round(pos[n]["x"]), round(pos[n]["y"])) for n in nodes}
    print()
print("=== 备选路径 vs 主路径 的几何关系 ===")
m1 = [(pos[n]["x"], pos[n]["y"]) for n in nd1]
m2 = [(pos[n]["x"], pos[n]["y"]) for n in nd2]


def mind(p, pts):
    return min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in pts)


ds = [mind(p, m1) for p in m2[1:-1]]
print(f"备选路径各点到主路径的最近距离: 最小 {min(ds):.0f} m, 中位 {sorted(ds)[len(ds)//2]:.0f} m, 最大 {max(ds):.0f} m")
print(f"  起点 {nd2[0]} ({n0}), 终点 {nd2[-1]} ({n1})")
print()
# 备选路径经过的站台
n2st = {}
for s in net["stations"]:
    for t in s["terminals"]:
        n2st[t["node_id"]] = (s["name"], "货运" if t.get("cargo") else "客运")
print("备选路径经过的站台节点（含所在站）:")
seen = set()
for n in nd2:
    if n in n2st and n2st[n] not in seen:
        seen.add(n2st[n])
        print("   ", n2st[n])
