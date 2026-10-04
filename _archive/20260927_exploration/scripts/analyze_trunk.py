"""干线车流与拥堵分析：共用轨道区段、理论车流、实测闭塞占用。只读。"""
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
samples = load(r"E:\workbody\TPF2Mcp\traffic_samples.json")

rail_ids = {int(l["entity_id"]) for l in net["lines"]}
lines = {int(l["entity_id"]): l for l in snap["lines"] if int(l["entity_id"]) in rail_ids}
headway = {}
for item in plan["lines"]:
    headway[int(item["line_id"])] = item.get("headway_seconds")
name_of = {lid: l.get("name") for lid, l in lines.items()}

edge_lines = {int(k): v for k, v in samples["edge_lines"].items()}
edge_samples = {int(k): v for k, v in samples["edge_samples"].items()}
block_samples = {k: v for k, v in samples["block_samples"].items()}
block_lines = {k: v for k, v in samples["block_lines"].items()}
n_samples = samples["samples"]

p(f"采样：{n_samples} 次 / {samples['duration_seconds']} 秒（间隔 {samples['interval_seconds']}s）")
p(f"覆盖轨道边 {len(edge_lines)} / {len(net['edges'])} ｜ 覆盖闭塞区间 {len(block_lines)} / 1478")

# ---------- 共用轨道 ----------
shared = {e: v for e, v in edge_lines.items() if len(v) >= 2}
by_count = defaultdict(int)
for e, v in shared.items():
    by_count[len(v)] += 1
p("")
p("=== 共用轨道的分布（被几条线路的车辆走过）===")
for k in sorted(by_count):
    p(f"  {k} 条线路共用：{by_count[k]} 个轨道边")

# 每条共用边的理论车流
trunk = []
for e, lids in shared.items():
    traffic = sum(3600.0 / headway[lid] for lid in lids if headway.get(lid))
    trunk.append({"edge": e, "lines": sorted(lids), "traffic_per_hour": traffic, "samples": edge_samples.get(e, 0)})
trunk.sort(key=lambda r: (-len(r["lines"]), -r["traffic_per_hour"]))
p("")
p("=== 最繁忙的干线段（按共用线路数）===")
p(f"{'轨道边':>9}{'线路数':>7}{'理论车流/小时':>14}  涉及线路")
for r in trunk[:12]:
    names = "、".join(str(name_of.get(l)) for l in r["lines"][:6])
    p(f"{r['edge']:>9}{len(r['lines']):>7}{r['traffic_per_hour']:>14.1f}  {names}")

# 全网干线车流汇总
p("")
p("=== 全网干线负荷（按线路对汇总）===")
pair_traffic = defaultdict(float)
for e, lids in shared.items():
    for i in range(len(lids)):
        for j in range(i + 1, len(lids)):
            key = tuple(sorted((lids[i], lids[j])))
            pair_traffic[key] += 1
top_pairs = sorted(pair_traffic.items(), key=lambda kv: -kv[1])[:10]
for (a, b), edge_count in top_pairs:
    ta = 3600.0 / headway[a] if headway.get(a) else 0
    tb = 3600.0 / headway[b] if headway.get(b) else 0
    p(f"  {str(name_of.get(a))[:12]:<14} + {str(name_of.get(b))[:12]:<14} 共用 {edge_count:>4} 段，"
      f"合计理论车流 {ta + tb:>5.1f} 列/小时")

# ---------- 闭塞占用 ----------
occ = sorted(((b, s / n_samples * 100) for b, s in block_samples.items()), key=lambda kv: -kv[1])
p("")
p("=== 闭塞区间实测占用率 Top 15 ===")
p(f"{'区间':>9}{'占用率%':>9}{'共用线路数':>11}  线路")
for block, rate in occ[:15]:
    lids = block_lines.get(block, [])
    names = "、".join(str(name_of.get(l)) for l in lids[:3])
    p(f"{block:>9}{rate:>9.1f}{len(lids):>11}  {names}")
busy = [x for _, x in occ if x >= 50]
mid = [x for _, x in occ if 20 <= x < 50]
p("")
p(f"占用率 ≥50%（接近饱和）的区间：{len(busy)} 个 ｜ 20–50%（偏忙）：{len(mid)} 个 ｜ 覆盖区间总数 {len(occ)}")

# 线路平均占用率（该线车辆所在区间）
line_block = defaultdict(list)
for block, rate in occ:
    for lid in block_lines.get(block, []):
        line_block[lid].append(rate)
p("")
p("=== 各线路所在区间的平均占用率（越高越挤）===")
rows = sorted(line_block.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))
for lid, rates in rows[:12]:
    p(f"  {str(name_of.get(lid))[:14]:<16} 平均 {sum(rates)/len(rates):>5.1f}%  最高 {max(rates):>5.1f}%  样本区间 {len(rates)}")

# ---------- 运行图冲突 ----------
cp = plan["global_conflict_plan"]
p("")
p("=== 运行图层面已存在的冲突（1 小时视窗）===")
p(f"相位调整前 {cp['conflicts_before_shift']} 次 → 调整后 {cp['conflicts_after_shift']} 次"
  f"（已消除 {cp['conflicts_removed']}）｜ 清空时间 {cp['clearance_seconds']}s")

p("")
p("=== 加车风险评估（按线路）===")
p("说明：车流已接近饱和的干线共用段越多，加车的边际风险越高；占用率低则加车余量大。")
for lid, rates in rows:
    avg = sum(rates) / len(rates)
    verdict = "余量大" if avg < 5 else ("需观察" if avg < 15 else "接近饱和")
    p(f"  {str(name_of.get(lid))[:14]:<16} 平均占用 {avg:>5.1f}%  → {verdict}")

with open(r"E:\workbody\TPF2Mcp\trunk_analysis.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(OUT))
json.dump({"samples": n_samples, "sampled_at": None, "trunk_edges": trunk[:60],
           "block_occupancy": [{"block_id": b, "rate": r} for b, r in occ[:80]]},
          open(r"E:\workbody\TPF2Mcp\trunk_traffic.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
