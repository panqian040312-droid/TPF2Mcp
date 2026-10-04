"""分析逐帧采样：区分"停站"与"区间滞留"，统计走廊并发占用。只读。"""
import json
import collections
import statistics

BRIDGE = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
FRAMES = r"E:\workbody\TPF2Mcp\_tmpdb\traffic_frames.json"
TOPO = r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json"

with open(FRAMES, encoding="utf-8") as fh:
    data = json.load(fh)
with open(BRIDGE + r"\rail-network.json", encoding="utf-8") as fh:
    net = json.load(fh)
with open(TOPO, encoding="utf-8") as fh:
    topo = json.load(fh)

names = {l["entity_id"]: l["name"] for l in net["lines"]}
veh_name = {}
frames = data["frames"]
if not frames:
    raise SystemExit("没有采样帧")

# 状态分类：停站(raw=2 或门开) / 区间滞留(raw!=2 且速度很低) / 行驶
cls = collections.defaultdict(collections.Counter)
speeds = collections.defaultdict(list)
edge_seq = collections.defaultdict(list)
static_run = collections.defaultdict(int)   # 连续滞留帧
max_run = collections.defaultdict(int)
prev_state = {}

for fr in frames:
    for v in fr["vehicles"]:
        vid = v["id"]
        veh_name[vid] = vid
        kmh = v["kmh"] or 0
        raw = v["raw"]
        doors = v["doors"]
        speeds[vid].append(kmh)
        edge_seq[vid].append(v["edge"])
        if raw == 2 or doors:
            cls[vid]["停站"] += 1
            static_run[vid] = 0
        elif kmh < 5:
            cls[vid]["区间滞留"] += 1
            static_run[vid] += 1
            max_run[vid] = max(max_run[vid], static_run[vid])
        else:
            cls[vid]["行驶"] += 1
            static_run[vid] = 0

# 每帧每边并发
edge_conc = collections.defaultdict(lambda: collections.Counter())
for fr in frames:
    per = collections.Counter(v["edge"] for v in fr["vehicles"] if v["edge"] is not None)
    for e, c in per.items():
        edge_conc[e][c] += 1

n = len(frames)
print(f"采样 {n} 帧，间隔 {data.get('interval')}s，车辆 {len(speeds)}")
print()
print(f"{'车':<8}{'线名':<16}{'停站%':>7}{'区间滞留%':>10}{'最长连续滞留':>13}{'速度中位':>9}{'走过边数':>9}")
print("-" * 80)
rows = []
for vid in sorted(speeds, key=lambda x: -cls[x]["区间滞留"]):
    line = next((fr_v["line"] for fr in frames for fr_v in fr["vehicles"] if fr_v["id"] == vid), None)
    c = cls[vid]
    tot = sum(c.values()) or 1
    uniq = len({e for e in edge_seq[vid] if e is not None})
    med = statistics.median(speeds[vid]) if speeds[vid] else 0
    rows.append((vid, names.get(line, "?"), c, tot, max_run[vid], med, uniq))
    print(f"{vid:<8}{names.get(line,'?'):<16}{c['停站']/tot*100:>6.0f}%{c['区间滞留']/tot*100:>9.0f}%{max_run[vid]:>13}{med:>9.0f}{uniq:>9}")
print()
print("=== 并发最高的轨道边（同一时刻几列车压在同一条边上）===")
top_edges = sorted(edge_conc.items(), key=lambda kv: -max(kv[1]))[:12]
for e, c in top_edges:
    mx = max(c)
    secs = sum(v for k, v in c.items() if k >= 2)
    print(f"  edge {e}: 最大并发 {mx} 列，并发出现 {secs} 帧")
print()
print("=== 共用走廊上的并发 ===")
for c in topo["corridors"]:
    if len(c["line_names"]) < 2:
        continue
    es = set(c["edge_ids"])
    per_frame = []
    for fr in frames:
        cnt = sum(1 for v in fr["vehicles"] if v["edge"] in es)
        per_frame.append(cnt)
    occ = sum(1 for x in per_frame if x > 0)
    print(f"  {len(c['line_names'])}线 {c['length_m']/1000:>5.2f}km 车站[{'/'.join(c['stations']) or '-'}]: "
          f"并发最大 {max(per_frame)}，平均 {sum(per_frame)/len(per_frame):.2f}，有车 {occ}/{len(per_frame)} 帧")
