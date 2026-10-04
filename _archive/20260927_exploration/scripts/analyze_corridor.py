"""干线走廊联合分析：与京广客运共线的所有线路 + 共用区段 + 站点 + 联合运行策略。只读。"""
import json
import math
from collections import defaultdict
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
B = MOD / "bridge"
CORE = "京广客运"

net = json.loads((B / "rail-network.json").read_text(encoding="utf-8"))
snap = json.loads((B / "state.json").read_text(encoding="utf-8"))
live = json.loads((B / "live-rail-state.json").read_text(encoding="utf-8"))
control = json.loads((B / "rail-control-state.json").read_text(encoding="utf-8"))
plan = json.loads((MOD / "diagnostics/rail-operations/line-timetable-plan.json").read_text(encoding="utf-8"))
samples = [json.loads(Path(p).read_text(encoding="utf-8"))
           for p in (r"E:\workbody\TPF2Mcp\traffic_samples.json", r"E:\workbody\TPF2Mcp\traffic_samples2.json")]

nodes = {n["entity_id"]: n["position"] for n in net["nodes"]}
edges = {e["entity_id"]: e for e in net["edges"]}
stations = {s["entity_id"]: s for s in net["stations"]}
names = {int(l["entity_id"]): l["name"] for l in snap["lines"]}
core_id = next(l["entity_id"] for l in snap["lines"] if l["name"] == CORE)
plan_by_line = {int(p["line_id"]): p for p in plan["lines"]}
diag_by_line = {int(d["line_id"]): d for d in live["line_diagnostics"]}
veh_by_line = defaultdict(list)
for v in snap["vehicles"]:
    if v.get("line_id") in plan_by_line:
        veh_by_line[v["line_id"]].append(v)

# 汇总两次采样的 edge->lines
edge_lines = defaultdict(set)
for data in samples:
    if "edge_lines" in data:
        for key, value in data["edge_lines"].items():
            edge_lines[int(key)].update(int(x) for x in value if x is not None)
    for frame in data.get("frames", []):
        for v in frame.get("vehicles", []):
            if v.get("edge") is not None and v.get("line") is not None:
                edge_lines[v["edge"]].add(v["line"])

# 走廊：与核心线共线的线路（含传递）
corridor = {core_id}
changed = True
while changed:
    changed = False
    for e, ls in edge_lines.items():
        if ls & corridor and not ls <= corridor:
            corridor |= ls
            changed = True

print(f"=== 干线走廊（与 {CORE} 连通共线）===")
print(f"涉及线路 {len(corridor)} 条：" + "、".join(sorted(str(names[i]) for i in corridor)))

print()
print("=== 走廊内各线路运行参数 ===")
print(f"{'线路':<14}{'车':>3}{'节数/列':>9}{'班次s':>7}{'周期s':>7}{'停站':>5}{'速度等级':>9}{'里程km':>8}{'年运量':>8}{'每车年运量':>11}{'停站等待上限':>13}")
line_info = {}
for lid in sorted(corridor, key=lambda x: str(names.get(x))):
    li = {int(l["entity_id"]): l for l in snap["lines"]}.get(lid) or {}
    entry = plan_by_line.get(lid, {})
    diag = diag_by_line.get(lid, {})
    vs = veh_by_line.get(lid, [])
    consist = [len(v.get("consist_parts") or []) for v in vs]
    stops = li.get("stops") or []
    max_wait = max((s.get("policy", {}).get("max_waiting_time") or 0 for s in stops), default=0)
    annual = (li.get("throughput") or 0) * (li.get("stop_count") or 0)
    wait_span = f"{min((s.get('policy',{}).get('min_waiting_time') or 0) for s in stops)}–{max_wait}" if stops else "—"
    line_info[lid] = {"entry": entry, "diag": diag, "vehicles": vs, "consist": consist,
                      "line": li, "annual": annual, "max_wait": max_wait}
    print(f"{str(names.get(lid))[:13]:<14}{len(vs):>3}"
          f"{(str(sorted(set(consist))) if consist else '—'):>9}"
          f"{entry.get('headway_seconds', 0):>7.0f}{entry.get('cycle_seconds', 0):>7.0f}"
          f"{li.get('stop_count', 0):>5}{entry.get('speed_class_kmh', '—'):>9}"
          f"{li.get('frequency_seconds', 0):>8.0f}{annual:>8.0f}"
          f"{round(annual/max(len(vs),1)):>11}{wait_span:>13}")

print()
print("=== 走廊内车辆的车型构成 ===")
for lid in sorted(corridor, key=lambda x: str(names.get(x))):
    for v in veh_by_line.get(lid, []):
        models = sorted({str(p.get("model_name")) for p in (v.get("consist_parts") or [])})
        print(f"  {str(names.get(lid))[:12]:<14}{v['name']:<8}{len(v.get('consist_parts') or []):>3} 节  容量{v.get('capacity_total'):>5}  "
              f"{models[:2]}")

# 共用区段
print()
print("=== 共用区段（实测两条以上线路都走过）===")
shared = {e: ls for e, ls in edge_lines.items() if len(ls & corridor) >= 2}
pair_map = defaultdict(list)
for e, ls in shared.items():
    ins = sorted(ls & corridor)
    for i in range(len(ins)):
        for j in range(i + 1, len(ins)):
            pair_map[(ins[i], ins[j])].append(e)


def nearest_station(node_id):
    pos = nodes.get(node_id)
    if not pos:
        return "?"
    best, best_d = None, 1e18
    for st in net["stations"]:
        c = st["center"]
        d = math.dist((pos["x"], pos["y"]), (c["x"], c["y"]))
        if d < best_d:
            best_d, best = d, st
    return f"{best['name']}({best_d:.0f}m)" if best else "?"


print(f"{'线路对':<32}{'共用段数':>9}{'合计车流/小时':>14}  区段两端的车站")
for (a, b), es in sorted(pair_map.items(), key=lambda kv: -len(kv[1])):
    ta = 3600.0 / (plan_by_line.get(a, {}).get("headway_seconds") or 1)
    tb = 3600.0 / (plan_by_line.get(b, {}).get("headway_seconds") or 1)
    ends = set()
    for e in es[:6]:
        edge = edges.get(e)
        if edge:
            ends.add(nearest_station(edge["node0"]))
            ends.add(nearest_station(edge["node1"]))
    print(f"{str(names.get(a))[:14] + ' + ' + str(names.get(b))[:14]:<32}{len(es):>9}{ta+tb:>14.1f}  {'、'.join(sorted(ends)[:4])}")

print()
print("=== 走廊共用车站（被两条以上走廊内线路停靠）===")
st_lines = defaultdict(set)
for lid in corridor:
    for stop in (line_info[lid]["line"].get("stops") or []):
        st_lines[stop["station_id"]].add(lid)
for sid, ls in sorted(st_lines.items(), key=lambda kv: -len(kv[1])):
    if len(ls) < 2:
        continue
    st = stations.get(sid)
    if not st:
        continue
    detail = []
    for lid in sorted(ls):
        entry = plan_by_line.get(lid, {})
        detail.append(f"{names.get(lid)}({entry.get('headway_seconds', 0):.0f}s)")
    print(f"  {st['name'][:14]:<16} {len(st.get('terminals') or [])} 到发线  ← " + "、".join(detail))

print()
print("=== 走廊内线路的运行图相位与冲突 ===")
for lid in sorted(corridor, key=lambda x: str(names.get(x))):
    entry = plan_by_line.get(lid, {})
    print(f"  {str(names.get(lid))[:14]:<16}相位 {entry.get('phase_offsets_seconds')}  "
          f"全局平移 {entry.get('global_phase_shift_seconds')}  冲突 {entry.get('station_conflicts_before_shift')}"
          f" → {entry.get('station_conflicts_after_shift')}")

print()
print("=== 走廊共用区段的信号密度 ===")
sig_edges = defaultdict(int)
for s in control["signals"]:
    sig_edges[s["edge_id"]] += 1
seg_len = 0.0
sig_count = 0
for e in shared:
    edge = edges.get(e)
    if not edge:
        continue
    a, b = nodes.get(edge["node0"]), nodes.get(edge["node1"])
    if a and b:
        seg_len += math.dist((a["x"], a["y"]), (b["x"], b["y"]))
    sig_count += sig_edges.get(e, 0)
print(f"  共用边 {len(shared)} 条，合计 {seg_len/1000:.2f} km，信号机 {sig_count} 处"
      f"（{sig_count/max(seg_len/1000,0.001):.2f} 个/km）")
