"""基于逐帧采样的干线拥堵分析：区间并发列车数、占用比例、线路间冲突。只读。"""
import json
from collections import defaultdict

M = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
B = M + r"\bridge"
OUT = []


def p(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def load(x):
    with open(x, encoding="utf-8") as fh:
        return json.load(fh)


snap = load(B + r"\state.json")
net = load(B + r"\rail-network.json")
plan = load(M + r"\diagnostics\rail-operations\line-timetable-plan.json")
data = load(r"E:\workbody\TPF2Mcp\traffic_samples2.json")

rail_ids = {int(l["entity_id"]) for l in net["lines"]}
names = {int(l["entity_id"]): l["name"] for l in snap["lines"] if int(l["entity_id"]) in rail_ids}
headway = {int(i["line_id"]): i.get("headway_seconds") for i in plan["lines"]}
frames = data["frames"]
N = len(frames)

block_occ = defaultdict(int)
block_max = defaultdict(int)
block_lines = defaultdict(set)
block_names = defaultdict(set)
edge_occ = defaultdict(int)
edge_max = defaultdict(int)
edge_lines = defaultdict(set)
line_moving = defaultdict(int)
line_present = defaultdict(int)

for frame in frames:
    per_block = defaultdict(list)
    per_edge = defaultdict(list)
    for v in frame["vehicles"]:
        if v["block"] is not None:
            per_block[v["block"]].append(v)
        if v["edge"] is not None:
            per_edge[v["edge"]].append(v)
        if v["line"] is not None:
            line_present[v["line"]] += 1
            if (v.get("speed") or 0) > 1:
                line_moving[v["line"]] += 1
    for block, vs in per_block.items():
        block_occ[block] += 1
        block_max[block] = max(block_max[block], len(vs))
        for v in vs:
            if v["line"] is not None:
                block_lines[block].add(v["line"])
                block_names[block].add(str(names.get(v["line"])))
    for edge, vs in per_edge.items():
        edge_occ[edge] += 1
        edge_max[edge] = max(edge_max[edge], len(vs))
        for v in vs:
            if v["line"] is not None:
                edge_lines[edge].add(v["line"])

p(f"采样 {N} 帧 / {data['duration_seconds']} 秒（间隔 {data['interval_seconds']}s），"
  f"每帧车辆 {len(frames[-1]['vehicles'])} 辆，仿真 {data['simulation_status']}")
p(f"覆盖闭塞区间 {len(block_occ)} ｜ 覆盖轨道边 {len(edge_occ)}")

# ---------- 区间并发 ----------
concurrent = {b: m for b, m in block_max.items() if m >= 2}
p("")
p("=== 同一闭塞区间同时出现多列车（排队/追尾风险）===")
p(f"出现过的区间：{len(concurrent)} 个 / 覆盖 {len(block_occ)} 个")
ranked = sorted(concurrent.items(), key=lambda kv: (-kv[1], -block_occ[kv[0]] / N))
p(f"{'区间':>9}{'最大并发':>9}{'占用帧比例':>11}{'线路数':>7}  线路")
for block, peak in ranked[:15]:
    p(f"{block:>9}{peak:>9}{block_occ[block]/N*100:>10.1f}%{len(block_lines[block]):>7}  "
      + "、".join(sorted(block_names[block])[:4]))

# ---------- 跨线路争用 ----------
cross = {b: ls for b, ls in block_lines.items() if len(ls) >= 2}
p("")
p("=== 被两条以上铁路线共用的闭塞区间（跨线争用点）===")
p(f"共 {len(cross)} 个")
for block, ls in sorted(cross.items(), key=lambda kv: -len(kv[1]))[:12]:
    p(f"  {block}: {len(ls)} 条线 —— " + "、".join(str(names.get(x)) for x in sorted(ls)))

# ---------- 轨道边共用（干线段） ----------
shared_edges = {e: ls for e, ls in edge_lines.items() if len(ls) >= 2}
p("")
p("=== 干线共用轨道边（被多条线车辆走过）===")
p(f"共 {len(shared_edges)} 个轨道边")
trunk_pairs = defaultdict(int)
for e, ls in shared_edges.items():
    ordered = sorted(ls)
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            trunk_pairs[(ordered[i], ordered[j])] += 1
p("")
p(f"{'线路对':<34}{'共用段数':>9}{'理论车流合计/小时':>18}")
for (a, b), count in sorted(trunk_pairs.items(), key=lambda kv: -kv[1])[:10]:
    ta = 3600.0 / headway[a] if headway.get(a) else 0
    tb = 3600.0 / headway[b] if headway.get(b) else 0
    p(f"{str(names.get(a))[:14] + ' + ' + str(names.get(b))[:14]:<34}{count:>9}{ta + tb:>18.1f}")

p("")
p("=== 干线段车流最高的轨道边 ===")
traffic_edges = []
for e, ls in shared_edges.items():
    traffic = sum(3600.0 / headway[l] for l in ls if headway.get(l))
    traffic_edges.append((e, ls, traffic, edge_max.get(e, 1)))
for e, ls, traffic, peak in sorted(traffic_edges, key=lambda x: -x[2])[:10]:
    p(f"  边 {e}: {traffic:>6.1f} 列/小时（{len(ls)} 条线："
      + "、".join(str(names.get(x)) for x in sorted(ls)) + f"），同边最大并发 {peak}")

# ---------- 线路层面 ----------
p("")
p("=== 各线路车辆运行状态与区间占用 ===")
p(f"{'线路':<16}{'车':>3}{'在跑帧比':>9}{'平均占用':>9}{'最高并发区间':>12}")
line_blocks = defaultdict(list)
for block, ls in block_lines.items():
    for lid in ls:
        line_blocks[lid].append(block)
rows = []
for lid in sorted(line_present):
    blocks = line_blocks.get(lid, [])
    if not blocks:
        continue
    avg_occ = sum(block_occ[b] / N * 100 for b in blocks) / len(blocks)
    peak = max(block_max[b] for b in blocks)
    moving = line_moving[lid] / max(line_present[lid], 1) * 100
    rows.append((names.get(lid), lid, blocks, avg_occ, peak, moving))
for name, lid, blocks, avg_occ, peak, moving in sorted(rows, key=lambda r: -r[4]):
    p(f"{str(name)[:15]:<16}{len(blocks):>3}{moving:>8.0f}%{avg_occ:>8.1f}%{peak:>12}")

occupied_now = data["counts"]
p("")
p(f"采样时刻全网：闭塞区间 {occupied_now['blocks']} 个，占用 {occupied_now['occupied_blocks']} 个"
  f"（{occupied_now['occupied_blocks']/occupied_now['blocks']*100:.1f}%），信号机 {occupied_now['confirmed_signals']} 个")
cp = plan["global_conflict_plan"]
p(f"运行图冲突（1 小时视窗）：调整前 {cp['conflicts_before_shift']} → 调整后 {cp['conflicts_after_shift']}，清空间隔 {cp['clearance_seconds']}s")

with open(r"E:\workbody\TPF2Mcp\trunk_analysis2.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(OUT))
json.dump({
    "frames": N,
    "duration_seconds": data["duration_seconds"],
    "block_concurrency": {b: {"peak": m, "occupancy": block_occ[b] / N, "lines": sorted(block_lines[b])} for b, m in concurrent.items()},
    "cross_line_blocks": {b: sorted(ls) for b, ls in cross.items()},
    "shared_edges": {str(e): sorted(ls) for e, ls in shared_edges.items()},
    "trunk_pairs": [{"a": a, "b": b, "edges": c, "traffic": (3600.0 / headway[a] if headway.get(a) else 0) + (3600.0 / headway[b] if headway.get(b) else 0)} for (a, b), c in trunk_pairs.items()],
    "line_names": {str(k): v for k, v in names.items()},
}, open(r"E:\workbody\TPF2Mcp\trunk_traffic.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
