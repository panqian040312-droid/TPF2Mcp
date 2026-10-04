"""京广客运实测轨迹分析：车辆实际走过的轨道边、限速、复线、信号、待避点。只读。"""
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

names = {int(l["entity_id"]): l["name"] for l in snap["lines"]}
target_id = next(l["entity_id"] for l in snap["lines"] if l["name"] == TARGET)
entry = next(l for l in plan["lines"] if l["line_name"] == TARGET)
lines_named = {int(l["entity_id"]): l for l in snap["lines"]}

nodes = {n["entity_id"]: n["position"] for n in net["nodes"]}
edges = {e["entity_id"]: e for e in net["edges"]}
stations = {s["entity_id"]: s for s in net["stations"]}

# 1) 实测轨迹：该线车辆走过的边（按首次出现顺序）
observed = []
seen = set()
for frame in samples["frames"]:
    for v in frame["vehicles"]:
        if v["line"] == target_id and v["edge"] is not None and v["edge"] not in seen:
            seen.add(v["edge"])
            observed.append(v["edge"])

print(f"=== {TARGET} 实测轨迹（3 分钟采样）===")
print(f"观测到 {len(observed)} 条不同的轨道边")


def seg_len(edge):
    a, b = nodes.get(edge["node0"]), nodes.get(edge["node1"])
    return math.dist((a["x"], a["y"]), (b["x"], b["y"])) if a and b else 0.0


limits = []
for eid in observed:
    e = edges.get(eid)
    if not e:
        continue
    limits.append((eid, round(e["speed_limit_mps"] * 3.6, 1), seg_len(e), e.get("track_resource_file", "?"),
                   e.get("track_type")))

total = sum(x[2] for x in limits)
print(f"观测里程 {total/1000:.2f} km")
print()
print("=== 实测路段限速分布（按里程加权）===")
hist = defaultdict(float)
for eid, kmh, length, res, ttype in limits:
    hist[kmh] += length
for kmh in sorted(hist, reverse=True):
    print(f"  {kmh:>6.0f} km/h：{hist[kmh]/1000:5.2f} km（{hist[kmh]/total*100 if total else 0:5.1f}%）")
weighted = sum(k * l for k, l in hist.items()) / total if total else 0
print(f"  里程加权平均限速：{weighted:.1f} km/h")
low = [x for x in limits if x[1] < 160]
print(f"  低于 160 km/h 的路段：{len(low)} 条，共 {sum(x[2] for x in low)/1000:.2f} km"
      f"（{sum(x[2] for x in low)/total*100 if total else 0:.1f}%）")

print()
print("=== 低限速路段明细（<200 km/h）===")
print(f"{'边':>9}{'限速':>7}{'长度m':>8}{'轨道类型':>10}  轨道资源")
for eid, kmh, length, res, ttype in sorted([x for x in limits if x[1] < 200], key=lambda x: x[1])[:12]:
    print(f"{eid:>9}{kmh:>7.0f}{length:>8.0f}{str(ttype):>10}  {res}")

# 2) 复线检测：几何平行边（中点接近且方向一致）
def midpoint(e):
    a, b = nodes.get(e["node0"]), nodes.get(e["node1"])
    return ((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2) if a and b else (0, 0)


def direction(e):
    a, b = nodes.get(e["node0"]), nodes.get(e["node1"])
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    norm = math.hypot(dx, dy) or 1
    return (dx / norm, dy / norm)


buckets = defaultdict(list)
for e in net["edges"]:
    mx, my = midpoint(e)
    buckets[(round(mx / 20), round(my / 20))].append(e)

parallel_count = 0
parallel_edges = set()
for key, items in buckets.items():
    if len(items) < 2:
        continue
    for i, e1 in enumerate(items):
        for e2 in items[i + 1:]:
            if e1["node0"] in (e2["node0"], e2["node1"]) or e1["node1"] in (e2["node0"], e2["node1"]):
                continue
            mx1, my1 = midpoint(e1)
            mx2, my2 = midpoint(e2)
            if math.hypot(mx1 - mx2, my1 - my2) > 25:
                continue
            d1, d2 = direction(e1), direction(e2)
            dot = abs(d1[0] * d2[0] + d1[1] * d2[1])
            if dot > 0.97:
                parallel_count += 1
                parallel_edges.add(e1["entity_id"])
                parallel_edges.add(e2["entity_id"])
                break

observed_parallel = sum(1 for eid in observed if eid in parallel_edges)
print()
print("=== 复线（双轨）情况 ===")
print(f"全网检出平行轨道边 {len(parallel_edges)} 条（{parallel_count} 对）／共 {len(net['edges'])} 条")
print(f"本线观测到的 {len(observed)} 条边中，有平行邻边的 {observed_parallel} 条"
      f"（{observed_parallel/max(len(observed),1)*100:.0f}%）→ 其余为单线区段")

# 3) 沿线信号
signal_edges = defaultdict(int)
for s in control["signals"]:
    signal_edges[s["edge_id"]] += 1
route_signals = sum(signal_edges.get(eid, 0) for eid in observed)
print()
print(f"=== 信号与闭塞 ===")
print(f"本线观测路段设信号机 {route_signals} 处（{route_signals/max(total/1000,0.001):.2f} 个/km）")
route_signal_edges = [eid for eid in observed if signal_edges.get(eid)]
print(f"有信号的边 {len(route_signal_edges)}/{len(observed)}")
block_ids = {s.get("block_id") for s in control["blocks"]} if control.get("blocks") and isinstance(control["blocks"][0], dict) else None
print(f"全网闭塞区间 {len(control['blocks'])} 个，当前占用 {live['counts']['occupied_blocks']}")

# 4) 混跑：同一批边还有其他线的车
edge_lines = defaultdict(set)
for frame in samples["frames"]:
    for v in frame["vehicles"]:
        if v["edge"] is not None and v["line"] is not None:
            edge_lines[v["edge"]].add(v["line"])
shared = [(eid, edge_lines[eid]) for eid in observed if len(edge_lines.get(eid, set())) >= 2]
print()
print(f"=== 混跑 ===")
print(f"本线观测路段中与他人共用 {len(shared)} 条边")
for eid, ls in shared[:8]:
    others = [str(names.get(x)) for x in sorted(ls) if x != target_id]
    e = edges.get(eid, {})
    print(f"  边 {eid}（限速 {round(e.get('speed_limit_mps', 0)*3.6)} km/h）: 与 {'、'.join(others)} 共用")

# 5) 本线车辆与观察到的停站时长
print()
print("=== 停站与周转 ===")
print(f"计划：停站 {len(entry['stops'])} 处，停站时间 "
      f"{[s['scheduled_dwell_seconds'] for s in entry['stops']]}s，"
      f"区间运行 {[s['next_leg_running_seconds'] for s in entry['stops']]}s")
print(f"周期 {entry['cycle_seconds']}s ｜ 班次 {entry['headway_seconds']:.0f}s ｜ 车数 {entry['vehicle_count']}")
for stop in lines_named[target_id]["stops"]:
    print(f"  停站策略：最大等待 {stop['policy']['max_waiting_time']}s，"
          f"最小等待 {stop['policy']['min_waiting_time']}s，装载模式 {stop['policy']['load_mode']}")

# 6) 站点站台数（待避潜力）
print()
print("=== 站点站台（terminals）===")
for stop in lines_named[target_id]["stops"]:
    st = stations.get(stop["station_id"])
    if st:
        print(f"  {st['name']}: {len(st.get('terminals') or [])} 个站台/到发线")
