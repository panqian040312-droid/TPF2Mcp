"""看走廊并发的时间分布：稳定过载 还是 忽高忽低（可错峰）。只读。"""
import json
import collections

top = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\rail_topology.json", encoding="utf-8"))
data = json.load(open(r"E:\workbody\TPF2Mcp\_tmpdb\traffic_frames.json", encoding="utf-8"))
frames = data["frames"]
corr = [c for c in top["corridors"] if len(c["line_names"]) >= 6][0]
CEDGE = set(corr["edge_ids"])

series = []
for fr in frames:
    series.append(sum(1 for v in fr["vehicles"] if v["edge"] in CEDGE))

hist = collections.Counter(series)
print(f"采样 {len(series)} 帧，走廊并发分布：")
for k in sorted(hist):
    bar = "#" * hist[k]
    print(f"  {k} 列: {hist[k]:>4} 帧 ({hist[k]/len(series)*100:>5.1f}%) {bar}")

mean = sum(series) / len(series)
var = sum((x - mean) ** 2 for x in series) / len(series)
print()
print(f"平均 {mean:.2f}，标准差 {var**0.5:.2f}，最小 {min(series)}，最大 {max(series)}")
print(f"并发 <= 1 的帧: {sum(1 for x in series if x <= 1)}/{len(series)}"
      f" ({sum(1 for x in series if x <= 1)/len(series)*100:.0f}%)")
print()
print("判读：")
print("  · 若并发集中在 2-3 且标准差小 → 稳定过载，错峰没用，必须减车/分流/复线")
print("  · 若在 1 和 4-5 之间大幅摆动 → 有扎堆，错峰有效")
