"""量化主干走廊的需求与错峰空间：每条线在走廊上的时间占比。只读。"""
import json
import collections

BRIDGE = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(BRIDGE + r"\rail-network.json", encoding="utf-8"))
top = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json", encoding="utf-8"))
frames = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\traffic_frames.json", encoding="utf-8"))["frames"]

names = {l["entity_id"]: l["name"] for l in net["lines"]}
corr = [c for c in top["corridors"] if len(c["line_names"]) >= 6][0]
CEDGE = set(corr["edge_ids"])
CLINES = set(corr["line_ids"])

# 每辆车的线归属
vline = {}
for fr in frames:
    for v in fr["vehicles"]:
        vline[v["id"]] = v["line"]

n = len(frames)
in_corr = collections.Counter()      # 车 -> 在走廊的帧数
total = collections.Counter()        # 车 -> 总帧数
line_frames = collections.Counter()  # 线 -> 该线所有车在走廊的帧数
line_total = collections.Counter()

for fr in frames:
    for v in fr["vehicles"]:
        vid = v["id"]
        total[vid] += 1
        line_total[vline[vid]] += 1
        if v["edge"] in CEDGE:
            in_corr[vid] += 1
            line_frames[vline[vid]] += 1

print(f"采样 {n} 帧；走廊长 {corr['length_m']/1000:.2f} km，{len(CEDGE)} 条边")
print()
print(f"{'车辆':<8}{'线名':<16}{'在走廊帧数':>10}{'总帧数':>8}{'占比':>7}")
print("-" * 55)
rows = []
for vid in sorted(in_corr, key=lambda x: -in_corr[x]):
    if vline.get(vid) not in CLINES:
        continue
    pct = in_corr[vid] / total[vid] * 100
    rows.append((vid, names.get(vline[vid], "?"), in_corr[vid], total[vid], pct))
    print(f"{vid:<8}{names.get(vline[vid],'?'):<16}{in_corr[vid]:>10}{total[vid]:>8}{pct:>6.0f}%")
print()
print(f"{'线路':<16}{'在走廊帧':>10}{'总帧':>8}{'线内占比':>9}")
print("-" * 45)
for lid in sorted(line_frames, key=lambda x: -line_frames[x]):
    print(f"{names.get(lid,'?'):<16}{line_frames[lid]:>10}{line_total[lid]:>8}{line_frames[lid]/line_total[lid]*100:>8.0f}%")
print()
occ = sum(in_corr.values())
print(f"走廊总占用: {occ} 车-帧 / {occ/n:.2f} 列平均并发")
print(f"走廊被占用帧数: {sum(1 for fr in frames if any(v['edge'] in CEDGE for v in fr['vehicles']))}/{n}")
print()
print("=== 关键提问：有没有错峰空间 ===")
print("若某线的车『几乎全部时间』都在走廊上，则该线没有可错峰的空档。")
for vid, nm, ic, tt, pct in rows:
    flag = "  <== 常驻走廊，无法错峰" if pct > 80 else ("  <== 大部分时间在走廊" if pct > 50 else "")
    print(f"  {nm:<16}{pct:>5.0f}%{flag}")
