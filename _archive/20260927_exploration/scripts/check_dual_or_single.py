"""验证 Omsk-Foshan 之间到底是单线还是双线：两条平行路径的边级几何关系 + 连接点。只读。"""
import heapq
import json
import math
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
frames = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\traffic_frames.json", encoding="utf-8"))["frames"]
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

S1, S2 = set(e1), set(e2)
print(f"主路径 {d1/1000:.2f} km ({len(e1)} 边) / 备选 {d2/1000:.2f} km ({len(e2)} 边)")
print(f"两者共享的边: {len(S1 & S2)} 条")
print(f"共享的节点: {len(set(nd1) & set(nd2))} 个 -> {sorted(set(nd1) & set(nd2))[:10]}")
print()


def mid(e):
    a, b = eall[e]["node0"], eall[e]["node1"]
    return ((pos[a]["x"] + pos[b]["x"]) / 2, (pos[a]["y"] + pos[b]["y"]) / 2)


m1 = [mid(e) for e in e1]
m2 = [mid(e) for e in e2]


def nearest(p, pts):
    best, bd = None, 1e18
    for q in pts:
        d = math.hypot(p[0] - q[0], p[1] - q[1])
        if d < bd:
            bd, best = d, q
    return bd


ds = [nearest(p, m1) for p in m2]
ds.sort()
print("备选路径每条边到主路径的最近距离（边中点）：")
print(f"  最小 {ds[0]:.1f} m | 5% {ds[len(ds)//20]:.1f} | 25% {ds[len(ds)//4]:.1f} | "
      f"中位 {ds[len(ds)//2]:.1f} | 75% {ds[len(ds)*3//4]:.1f} | 最大 {ds[-1]:.1f}")
close = sum(1 for x in ds if x < 25)
print(f"  距离 < 25 m 的边: {close}/{len(ds)} ({close/len(ds)*100:.0f}%)")
print()
print("判读：若绝大多数边中点相距 10–30 m 且方向平行，说明是紧挨着的两条平行轨道（双线）。")
print()

# 采样：两条路径各自的并发
for tag, es in [("主路径", S1), ("备选路径", S2)]:
    per = [sum(1 for v in fr["vehicles"] if v["edge"] in es) for fr in frames]
    occ = sum(1 for x in per if x > 0)
    cnt = collections.Counter()
    for fr in frames:
        for v in fr["vehicles"]:
            if v["edge"] in es:
                cnt[v["line"]] += 1
    tot = sum(cnt.values()) or 1
    print(f"{tag}: 平均并发 {sum(per)/len(per):.2f}，峰值 {max(per)}，有车 {occ}/{len(per)} 帧")
    for k, v in cnt.most_common(5):
        print(f"    {names.get(k,'?'):<20} {v/tot*100:>5.1f}%")
    print()
