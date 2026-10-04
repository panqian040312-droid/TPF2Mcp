"""第二轮：割边影响面、枢纽负荷、闭塞占用、分量构成。只读。"""
import json
from collections import defaultdict, deque

M = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
B = M + r"\bridge"
OUT = []


def p(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


net = load(B + r"\rail-network.json")
live = load(B + r"\live-rail-state.json")
ctl = load(B + r"\rail-control-state.json")
snap = load(B + r"\state.json")

adj = defaultdict(set)
edges = []
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    adj[a].add(b)
    adj[b].add(a)
    edges.append((a, b, e["entity_id"]))

node_station = {}
for s in net["stations"]:
    ns = {s["entity_id"]}
    for c in s.get("child_station_ids") or []:
        ns.add(c)
    for eid in ns:
        node_station[eid] = s.get("name")

# 连通分量标注
comp_of = {}
cid = 0
for start in adj:
    if start in comp_of:
        continue
    q = deque([start])
    comp_of[start] = cid
    size = 0
    while q:
        cur = q.popleft()
        size += 1
        for nb in adj[cur]:
            if nb not in comp_of:
                comp_of[nb] = cid
                q.append(nb)
    cid += 1
comp_size = defaultdict(int)
for n, c in comp_of.items():
    comp_size[c] += 1

# 割边：用 Tarjan 记录，并统计每条割边两侧的子树大小
disc, low, timer = {}, {}, [0]
bridges = []
visited = set()
for root in list(adj):
    if root in visited:
        continue
    visited.add(root)
    disc[root] = low[root] = timer[0]
    timer[0] += 1
    stack = [(root, None, iter(adj[root]))]
    sub = {root: 1}
    while stack:
        cur, parent, it = stack[-1]
        advanced = False
        for nb in it:
            if nb == parent:
                parent = None
                continue
            if nb not in visited:
                visited.add(nb)
                disc[nb] = low[nb] = timer[0]
                timer[0] += 1
                sub[nb] = 1
                stack.append((nb, cur, iter(adj[nb])))
                advanced = True
                break
            low[cur] = min(low[cur], disc[nb])
        if advanced:
            continue
        stack.pop()
        if stack:
            par = stack[-1][0]
            sub[par] += sub[cur]
            low[par] = min(low[par], low[cur])
            if low[cur] > disc[par]:
                bridges.append((par, cur, sub[cur]))

p("=== 割边影响面（拆除后会被切出的节点数）===")
bridges.sort(key=lambda x: -x[2])
p(f"{'节点A':>8}{'节点B':>8}{'切出节点数':>12}  端点车站")
for a, b, s in bridges[:12]:
    sa = node_station.get(a) or node_station.get(b) or "-"
    p(f"{a:>8}{b:>8}{s:>12}  {sa}")

p("")
p("=== 连通分量构成 ===")
p("分量总数", len(set(comp_of.values())))
# 每个分量里有多少车站 / 多少线路径过
comp_stations = defaultdict(set)
for eid, name in node_station.items():
    if eid in comp_of:
        comp_stations[comp_of[eid]].add(name)
line_touch = defaultdict(set)
for l in net["lines"]:
    for st in l.get("stops", []):
        gid = st.get("station_group_id")
        for eid, nm in node_station.items():
            pass
    for st in l.get("stops", []):
        nid = st.get("node_id")
        if nid in comp_of:
            line_touch[comp_of[nid]].add(l.get("name"))
sizes = sorted(((comp_size[c], len(comp_stations[c]), len(line_touch[c])) for c in comp_size), reverse=True)
p(f"{'节点数':>8}{'车站数':>8}{'线路数':>8}")
for s, st, ln in sizes[:12]:
    p(f"{s:>8}{st:>8}{ln:>8}")

p("")
p("=== 枢纽车站（被多条铁路线共用）===")
st_lines = defaultdict(set)
for l in net["lines"]:
    for st in l.get("stops", []):
        gid = st.get("station_group_id")
        if gid:
            st_lines[gid].add(l.get("name"))
name_of = {s["entity_id"]: s.get("name") for s in net["stations"]}
hubs = sorted(st_lines.items(), key=lambda kv: -len(kv[1]))
for gid, lines in hubs[:12]:
    p(f"  {str(name_of.get(gid, gid))[:12]:<14} 线路数 {len(lines):>2}  {sorted(x for x in lines if x)[:6]}")

p("")
p("=== 闭塞占用（来自实时计数）===")
c = live["counts"]
p("闭塞区间", c["blocks"], "| 占用", c["occupied_blocks"], f"| 占用率 {c['occupied_blocks']/c['blocks']*100:.1f}%",
  "| 信号机", c["confirmed_signals"], "/ 候选", c["signal_candidates"])
diag = live["line_diagnostics"]
insuff = [d for d in diag if d.get("diagnosis") == "INSUFFICIENT_TRAINS"]
p("车不足线路数", len(insuff), "/", len(diag))
p("车不足线路示例:", [(d["name"], d["vehicle_count"], round((d.get("route_length_m") or 0) / 1000, 1)) for d in insuff[:8]])

with open(r"E:\workbody\TPF2Mcp\rail_analysis_raw2.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(OUT))
