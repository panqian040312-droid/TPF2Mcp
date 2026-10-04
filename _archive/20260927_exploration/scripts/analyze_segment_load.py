"""把主干走廊按站间切段，统计每段并发与占用线，定位真正最堵的一段。只读。"""
import json
import math
import collections

BRIDGE = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(BRIDGE + r"\rail-network.json", encoding="utf-8"))
top = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json", encoding="utf-8"))
frames = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\traffic_frames.json", encoding="utf-8"))["frames"]

pos = {n["entity_id"]: n["position"] for n in net["nodes"]}
eall = {e["entity_id"]: e for e in net["edges"]}
n2st = {}
for s in net["stations"]:
    for t in s["terminals"]:
        n2st[t["node_id"]] = s["name"]
names = {l["entity_id"]: l["name"] for l in net["lines"]}

corr = [c for c in top["corridors"] if len(c["line_names"]) >= 6][0]
es = corr["edge_ids"]
adj = collections.defaultdict(list)
deg = collections.Counter()
for e in es:
    a, b = eall[e]["node0"], eall[e]["node1"]
    adj[a].append((b, e))
    adj[b].append((a, e))
    deg[a] += 1
    deg[b] += 1
ends = [n for n, d in deg.items() if d == 1]

order = []
cur, prev = ends[0], None
while True:
    nxt = [(v, e) for v, e in adj[cur] if v != prev]
    if not nxt:
        break
    v, e = nxt[0]
    order.append((cur, v, e))
    prev, cur = cur, v

# 按站切段
segments = []
seg = {"edges": [], "start": n2st.get(ends[0], "?"), "end": None, "len": 0.0}
for a, b, e in order:
    seg["edges"].append(e)
    pa, pb = pos[a], pos[b]
    seg["len"] += math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
    if b in n2st and n2st[b] != n2st.get(a):
        seg["end"] = n2st[b]
        segments.append(seg)
        seg = {"edges": [], "start": n2st[b], "end": None, "len": 0.0}
if seg["edges"]:
    seg["end"] = n2st.get(ends[1], "?")
    segments.append(seg)

print(f"{'区间':<26}{'长km':>7}{'边数':>6}{'平均并发':>9}{'峰值':>5}{'占用帧':>7}  主要占用线路")
print("-" * 100)
for s in segments:
    eset = set(s["edges"])
    per = [sum(1 for v in fr["vehicles"] if v["edge"] in eset) for fr in frames]
    occ = sum(1 for x in per if x > 0)
    cnt = collections.Counter()
    for fr in frames:
        for v in fr["vehicles"]:
            if v["edge"] in eset:
                cnt[v["line"]] += 1
    tot = sum(cnt.values()) or 1
    top3 = " + ".join(f"{names.get(k,'?')}({v/tot*100:.0f}%)" for k, v in cnt.most_common(3))
    print(f"{s['start'] + ' → ' + str(s['end']):<26}{s['len']/1000:>7.2f}{len(s['edges']):>6}"
          f"{sum(per)/len(per):>9.2f}{max(per):>5}{occ:>7}  {top3}")
