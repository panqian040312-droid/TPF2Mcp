"""验证两条平行轨道是否各自双向混跑（这是"双线却仍堵"的根因）。只读。"""
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

# 每条边在链上的位置索引（Omsk=0 -> Foshan=末端）
rank1 = {e: i for i, e in enumerate(e1)}
rank2 = {e: i for i, e in enumerate(e2)}

for tag, rank, es in [("主路径(货运那条)", rank1, e1), ("备选路径(客运那条)", rank2, e2)]:
    eset = set(es)
    # 追踪每辆车在链上位置的走向
    move = collections.defaultdict(list)
    for fr in frames:
        for v in fr["vehicles"]:
            if v["edge"] in eset:
                move[v["id"]].append(rank[v["edge"]])
    fwd = collections.Counter()
    bwd = collections.Counter()
    for vid, seq in move.items():
        ups = sum(1 for a, b in zip(seq, seq[1:]) if b > a)
        downs = sum(1 for a, b in zip(seq, seq[1:]) if b < a)
        if ups > downs:
            fwd[vid] = ups + downs
        elif downs > ups:
            bwd[vid] = ups + downs
    print(f"=== {tag} ===")
    print(f"  在该路径上被观测到的车辆: {len(move)}")
    print(f"  朝 Foshan 方向 (Omsk->Foshan): {len(fwd)} 辆 -> {sorted(fwd)}")
    print(f"  朝 Omsk 方向 (Foshan->Omsk): {len(bwd)} 辆 -> {sorted(bwd)}")
    if fwd and bwd:
        print("  >>> 两个方向都有车 == 双向混跑（会交会）")
    elif fwd or bwd:
        print("  >>> 只观测到一个方向（样本可能不全）")
    print()
    # 逐帧方向组合
    both = 0
    for fr in frames:
        dirs = set()
        for v in fr["vehicles"]:
            if v["edge"] in eset:
                seq = move.get(v["id"])
                if seq and len(seq) > 1:
                    if seq[-1] > seq[0]:
                        dirs.add("F")
                    elif seq[-1] < seq[0]:
                        dirs.add("B")
        if len(dirs) > 1:
            both += 1
    print(f"  同一时刻该路径上『两个方向都有车』的帧: {both}/{len(frames)} ({both/len(frames)*100:.0f}%)")
    print()
