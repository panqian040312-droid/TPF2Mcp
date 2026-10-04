"""京广客运线路级分析：路径限速剖面、单双线、信号闭塞、混跑冲突、加车可行性。只读。"""
import heapq
import json
import math
from collections import defaultdict
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
B = MOD / "bridge"
TARGET = "京广客运"

net = json.loads((B / "rail-network.json").read_text(encoding="utf-8"))
snap = json.loads((B / "state.json").read_text(encoding="utf-8"))
live = json.loads((B / "live-rail-state.json").read_text(encoding="utf-8"))
control = json.loads((B / "rail-control-state.json").read_text(encoding="utf-8"))
plan = json.loads((MOD / "diagnostics/rail-operations/line-timetable-plan.json").read_text(encoding="utf-8"))
samples = json.loads(Path(r"E:\workbody\TPF2Mcp\traffic_samples2.json").read_text(encoding="utf-8"))

line = next(l for l in snap["lines"] if l["name"] == TARGET)
entry = next(l for l in plan["lines"] if l["line_name"] == TARGET)
diag = next(d for d in live["line_diagnostics"] if d["line_id"] == line["entity_id"])

nodes = {n["entity_id"]: n["position"] for n in net["nodes"]}
stations = {s["entity_id"]: s for s in net["stations"]}

adj = defaultdict(list)
pair_edges = defaultdict(list)
for e in net["edges"]:
    a, b = e["node0"], e["node1"]
    pa, pb = nodes.get(a), nodes.get(b)
    length = math.dist((pa["x"], pa["y"]), (pb["x"], pb["y"])) if pa and pb else 0.0
    adj[a].append((b, length, e))
    adj[b].append((a, length, e))
    pair_edges[tuple(sorted((a, b)))].append(e)


def shortest(start, goal):
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    seen = set()
    while heap:
        d, cur = heapq.heappop(heap)
        if cur in seen:
            continue
        seen.add(cur)
        if cur == goal:
            break
        for nxt, length, edge in adj[cur]:
            nd = d + length
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = (cur, edge)
                heapq.heappush(heap, (nd, nxt))
    if goal not in prev and goal != start:
        return None
    path = []
    cur = goal
    while cur != start:
        parent, edge = prev[cur]
        path.append(edge)
        cur = parent
    return list(reversed(path))


print(f"=== {TARGET}（线路 id {line['entity_id']}）===")
print(f"车数 {diag['vehicle_count']} ｜ 里程 {diag['route_length_m']/1000:.1f} km ｜ 班次 {entry["headway_seconds"]:.0f}s"
      f" ｜ 最小间距 {diag.get('minimum_spacing_m')} ｜ 诊断 {diag['diagnosis']}")
print(f"计划：速度等级 {entry['speed_class_kmh']} km/h（车顶速 {entry['speed_basis']['consist_top_speed_kmh']}，"
      f"基础设施最低限速 {entry['speed_basis']['infrastructure_min_speed_limit_kmh']}）")
print(f"编组长 {entry['stops'][0]['platform_fit']['train_length_m']} m ｜ 停站 {len(entry['stops'])}")

# 站点序列（按线路停站顺序），用 terminal node 作为端点
ordered = []
for stop in line["stops"]:
    station = stations.get(stop["station_id"])
    if not station:
        continue
    terminals = station.get("terminals") or []
    selected = None
    for idx, stop_plan in enumerate(entry["stops"]):
        pass
    ordered.append((station, terminals))
plan_stops = {s["station_name"]: s for s in entry["stops"]}

print()
print("=== 停站与站台 ===")
print(f"{'站名':<16}{'terminal数':>10}{'计划停站s':>10}{'区间运行s':>10}{'下一段限速':>12}")
legs = []
for i, (station, terminals) in enumerate(ordered):
    ps = plan_stops.get(station["name"], {})
    print(f"{station['name'][:15]:<16}{len(terminals):>10}{ps.get('scheduled_dwell_seconds', '—'):>10}"
          f"{ps.get('next_leg_running_seconds', '—'):>10}")
    if i + 1 < len(ordered):
        legs.append((station, ordered[i + 1][0], ps.get("next_leg_running_seconds")))

# 逐段路径 + 限速剖面
total_length = 0.0
speed_hist = defaultdict(float)
low_segments = []
signal_edges = {s["edge_id"] for s in control["signals"]}
track_types = defaultdict(float)
print()
print("=== 区间路径与限速剖面（最短路径近似，非游戏内实际径路）===")
for a_station, b_station, runtime in legs:
    start = (a_station.get("terminals") or [{}])[0].get("node_id")
    goal = (b_station.get("terminals") or [{}])[0].get("node_id")
    path = shortest(start, goal) if start and goal else None
    if not path:
        print(f"  {a_station['name']} → {b_station['name']}: 路径未找到")
        continue
    length = sum(math.dist((nodes[e["node0"]]["x"], nodes[e["node0"]]["y"]),
                           (nodes[e["node1"]]["x"], nodes[e["node1"]]["y"])) for e in path)
    total_length += length
    limits = [round(e["speed_limit_mps"] * 3.6, 1) for e in path]
    low = [e for e in path if e["speed_limit_mps"] * 3.6 < 160]
    low_len = 0.0
    for e in low:
        seg = math.dist((nodes[e["node0"]]["x"], nodes[e["node0"]]["y"]),
                        (nodes[e["node1"]]["x"], nodes[e["node1"]]["y"]))
        low_len += seg
    for e in path:
        seg = math.dist((nodes[e["node0"]]["x"], nodes[e["node0"]]["y"]),
                        (nodes[e["node1"]]["x"], nodes[e["node1"]]["y"]))
        speed_hist[round(e["speed_limit_mps"] * 3.6)] += seg
        track_types[e.get("track_resource_file", "?")] += seg
    singles = sum(1 for e in path if len(pair_edges[tuple(sorted((e["node0"], e["node1"])))]) == 1)
    print(f"  {a_station['name'][:10]} → {b_station['name'][:10]}: {length/1000:6.1f} km ｜ {len(path):>4} 条边 ｜ "
          f"限速 {min(limits):>5.0f}–{max(limits):>5.0f} km/h ｜ <160 的段落 {low_len/1000:5.2f} km"
          f"（{low_len/length*100 if length else 0:4.1f}%）｜ 单线边 {singles}/{len(path)} ｜ 计划 {runtime}s")

print()
print("=== 全线限速分布（按里程加权）===")
for speed in sorted(speed_hist, reverse=True):
    length_km = speed_hist[speed] / 1000
    print(f"  限速 {speed:>5.0f} km/h：{length_km:6.2f} km（{length_km/(total_length/1000)*100:5.1f}%）")
print(f"  合计 {total_length/1000:.1f} km")

avg_limit = sum(s * l for s, l in speed_hist.items()) / sum(speed_hist.values())
print(f"  里程加权平均限速：{avg_limit:.1f} km/h")

print()
print("=== 线路技术构成 ===")
for name, length in sorted(track_types.items(), key=lambda kv: -kv[1])[:6]:
    print(f"  轨道 {name}: {length/1000:.2f} km")
print(f"  单线边占比：{sum(1 for e in net['edges'] if len(pair_edges[tuple(sorted((e['node0'], e['node1'])))]) == 1)}/{len(net['edges'])}（全网）")

print()
print("=== 信号与闭塞沿线 ===")
route_edges = set()
for a_station, b_station, _ in legs:
    start = (a_station.get("terminals") or [{}])[0].get("node_id")
    goal = (b_station.get("terminals") or [{}])[0].get("node_id")
    path = shortest(start, goal)
    if path:
        route_edges.update(e["entity_id"] for e in path)
route_signals = [s for s in control["signals"] if s["edge_id"] in route_edges]
print(f"  线路经过 {len(route_edges)} 条轨道边，其中设信号机 {len(route_signals)} 处"
      f"（密度 {len(route_signals)/max(total_length/1000,0.1):.2f} 个/km）")
print(f"  全网闭塞区间 {len(control['blocks'])} 个，当前占用 {live['counts']['occupied_blocks']}")

# 混跑：其他线路也走这些边
edge_lines = defaultdict(set)
for frame in samples["frames"]:
    for v in frame["vehicles"]:
        if v["edge"] is not None and v["line"] is not None:
            edge_lines[v["edge"]].add(v["line"])
names = {int(l["entity_id"]): l["name"] for l in snap["lines"]}
shared = {e: ls for e, ls in edge_lines.items() if len(ls) >= 2}
route_shared = [(e, ls) for e, ls in shared.items() if e in route_edges]
print()
print(f"=== 混跑情况（采样 3 分钟）===")
print(f"  本线路径上有 {len(route_shared)} 条边被其他线路共用")
for e, ls in route_shared[:6]:
    others = [str(names.get(x)) for x in sorted(ls) if names.get(x) != TARGET]
    print(f"    边 {e}: 与 {'、'.join(others)} 共用")

print()
print("=== 本线车辆实测速度（3 分钟采样）===")
speeds = []
for frame in samples["frames"]:
    for v in frame["vehicles"]:
        if names.get(v["line"]) == TARGET and v.get("speed") is not None:
            speeds.append(v["speed"])
if speeds:
    moving = [s for s in speeds if s > 1]
    print(f"  样本 {len(speeds)} 个 ｜ 移动样本 {len(moving)} ｜ 平均 {sum(moving)/len(moving):.1f} km/h"
          f" ｜ 最高 {max(speeds):.1f} km/h ｜ 静止占比 {(1-len(moving)/len(speeds))*100:.0f}%")
else:
    print("  无速度样本")
