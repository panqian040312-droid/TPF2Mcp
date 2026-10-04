"""TPF2 铁路网问题分析：拓扑风险 + 线路运营 + 车辆/信号。只读，不改游戏数据。"""
import json
import sys
from collections import defaultdict, deque

M = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
B = M + r"\bridge"
OUT = []


def p(*args):
    line = " ".join(str(a) for a in args)
    OUT.append(line)
    print(line)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


snap = load(B + r"\state.json")          # 全存档快照
net = load(B + r"\rail-network.json")    # 铁路图
live = load(B + r"\live-rail-state.json")  # 实时
ctl = load(B + r"\rail-control-state.json")  # 信号与闭塞

# ---------- 1. 拓扑 ----------
nodes = {n["entity_id"]: n for n in net["nodes"]}
adj = defaultdict(set)
deg = defaultdict(int)
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    adj[a].add(b)
    adj[b].add(a)
    deg[a] += 1
    deg[b] += 1

p("=== 1. 拓扑 ===")
p("节点", len(nodes), "| 边", len(net["edges"]), "| 车站", len(net["stations"]), "| 机务段", len(net["depots"]))

seen = set()
comps = []
for start in adj:
    if start in seen:
        continue
    q = deque([start])
    seen.add(start)
    size = 0
    while q:
        cur = q.popleft()
        size += 1
        for nb in adj[cur]:
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    comps.append(size)
comps.sort(reverse=True)
p("连通分量数", len(comps), "| 最大分量", comps[0], f"({comps[0]/len(adj)*100:.1f}%)", "| 其余:", comps[1:12])

# 割边（单点故障咽喉）
disc, low, timer = {}, {}, [0]
bridges = []
visited = set()
for root in list(adj):
    if root in visited:
        continue
    stack = [(root, None, iter(adj[root]))]
    visited.add(root)
    disc[root] = low[root] = timer[0]
    timer[0] += 1
    while stack:
        cur, parent, it = stack[-1]
        advanced = False
        for nb in it:
            if nb == parent:
                parent = None  # 只跳过一条平行边
                continue
            if nb not in visited:
                visited.add(nb)
                disc[nb] = low[nb] = timer[0]
                timer[0] += 1
                stack.append((nb, cur, iter(adj[nb])))
                advanced = True
                break
            else:
                low[cur] = min(low[cur], disc[nb])
        if advanced:
            continue
        stack.pop()
        if stack:
            par = stack[-1][0]
            low[par] = min(low[par], low[cur])
            if low[cur] > disc[par]:
                bridges.append((par, cur))
p("割边（拆除即断网的关键区段）:", len(bridges), "/", len(net["edges"]),
  f"= {len(bridges)/len(net['edges'])*100:.1f}%")
dead = [n for n, d in deg.items() if d == 1]
p("度=1 端点（尽头/断头轨道）:", len(dead))

# ---------- 2. 线路运营 ----------
p("")
p("=== 2. 线路运营（36 条铁路线）===")
snap_lines = {int(l["entity_id"]): l for l in snap["lines"]}
net_line_ids = {int(l["entity_id"]) for l in net["lines"]}
rail_lines = {k: v for k, v in snap_lines.items() if k in net_line_ids}
p("铁路线", len(rail_lines), "| 全网线路", len(snap_lines))

diag = {int(d["line_id"]): d for d in live["line_diagnostics"]}
rows = []
for lid, d in diag.items():
    s = snap_lines.get(lid, {})
    freq = s.get("frequency_seconds")
    tp = s.get("throughput")
    stops = s.get("stop_count")
    rows.append({
        "id": lid,
        "name": d.get("name") or s.get("name"),
        "veh": d.get("vehicle_count"),
        "located": d.get("located_vehicle_count"),
        "len_km": (d.get("route_length_m") or 0) / 1000,
        "target_m": d.get("target_spacing_m"),
        "min_m": d.get("minimum_spacing_m"),
        "cv": d.get("spacing_cv"),
        "diag": d.get("diagnosis"),
        "demand": d.get("demand_status"),
        "freq_s": freq,
        "throughput": tp,
        "stops": stops,
    })

rows.sort(key=lambda r: -(r["cv"] or 0))
p("")
p("间距均匀度最差的 10 条（spacing_cv 越大 = 车辆越扎堆）:")
p(f"{'线路':<14}{'车':>3}{'里程km':>8}{'目标间距m':>10}{'最小间距m':>10}{'CV':>7}{'班次s':>8}  诊断")
for r in rows[:10]:
    p(f"{str(r['name'])[:13]:<14}{r['veh'] or 0:>3}{r['len_km']:>8.1f}{(r['target_m'] or 0):>10.0f}"
      f"{(r['min_m'] or 0):>10.0f}{(r['cv'] or 0):>7.2f}{(r['freq_s'] or 0):>8.0f}  {r['diag']}")

p("")
p("车少 / 班次稀 / 里程长的 10 条（潜在运力不足）:")
rows2 = sorted(rows, key=lambda r: -(r["len_km"] / max(r["veh"] or 1, 1)))
p(f"{'线路':<14}{'车':>3}{'里程km':>8}{'km/车':>7}{'班次s':>8}{'吞吐':>9}{'停站':>5}")
for r in rows2[:10]:
    p(f"{str(r['name'])[:13]:<14}{r['veh'] or 0:>3}{r['len_km']:>8.1f}{r['len_km']/max(r['veh'] or 1,1):>7.1f}"
      f"{(r['freq_s'] or 0):>8.0f}{(r['throughput'] or 0):>9.1f}{(r['stops'] or 0):>5}")

diag_kinds = defaultdict(int)
for r in rows:
    diag_kinds[str(r["diag"])] += 1
p("")
p("诊断分布:", dict(diag_kinds))

# ---------- 3. 车辆 ----------
p("")
p("=== 3. 车辆 ===")
veh_all = snap["vehicles"]
p("存档车辆总数", len(veh_all), "| 铁路在轨", live["counts"]["rail_vehicles"])
rail_veh = [v for v in veh_all if v.get("line_id") in net_line_ids]
p("归属铁路线的车辆", len(rail_veh))
cap = defaultdict(int)
cnt = defaultdict(int)
for v in rail_veh:
    cap[v["line_id"]] += v.get("capacity_total") or 0
    cnt[v["line_id"]] += 1
top = sorted(cap.items(), key=lambda kv: -kv[1])[:5]
p("单车容量最大的 5 条线(总容量):", [(snap_lines.get(k, {}).get("name"), cnt[k], v) for k, v in top])

# ---------- 4. 信号与闭塞 ----------
p("")
p("=== 4. 信号与闭塞 ===")
p("信号机", len(ctl["signals"]), "| 闭塞区间", len(ctl["blocks"]), "| 占用", ctl["counts"].get("occupied_blocks"),
  "| 占用率", f"{ctl['counts'].get('occupied_blocks',0)/max(len(ctl['blocks']),1)*100:.1f}%")
p("限制说明:", json.dumps(live.get("limitations", {}), ensure_ascii=False))

# ---------- 5. 全网口径对比 ----------
p("")
p("=== 5. 全存档口径（含公路/水运/航空）===")
p("线路", len(snap["lines"]), "| 车站", len(snap["stations"]), "| 车辆", len(snap["vehicles"]),
  "| 城镇", len(snap["towns"]), "| 工业", len(snap["industries"]))
p("快照时间戳", snap["timestamp"], "(seconds)")

with open(r"E:\workbody\TPF2Mcp\rail_analysis_raw.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(OUT))
