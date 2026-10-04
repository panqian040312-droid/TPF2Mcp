"""判定京广客运在 Hanoi/天津 的 160 秒停留属于哪种：
  - time_until_departure 从大值递减 → 按停站策略/时刻表等（改策略有效）
  - 停在 0 附近且车不动     → 被站台/信号占住（改策略无用，要动站台或让行）
每 3 秒一帧，逐帧落盘。
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

TARGET = 159365
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 7.0
OUT = Path(r"E:\workbody\TPF2Mcp\_dwell_probe.csv")

handle = OUT.open("w", encoding="utf-8")
handle.write("t,speed,block,time_until_departure,time_until_load,doors,stop_index\n")
handle.flush()

t0 = time.time()
stops = []          # 连续的停车片段
current = None
while time.time() - t0 < MINUTES * 60:
    try:
        data = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/live", timeout=10).read().decode())
        me = next((v for v in data.get("vehicles", []) if v.get("entity_id") == TARGET), None)
        if me:
            speed = float(me.get("speed_kmh") or 0)
            row = (round(time.time() - t0, 1), speed, me.get("block_id"),
                   me.get("time_until_departure"), me.get("time_until_load"),
                   me.get("doors_open"), me.get("stop_index"))
            handle.write(",".join(str(x) for x in row) + "\n")
            handle.flush()
            if speed < 1:
                if current is None:
                    current = {"start": row[0], "end": row[0], "dep_first": row[3], "dep_last": row[3], "load_first": row[4], "n": 1}
                else:
                    current["end"] = row[0]
                    current["dep_last"] = row[3]
                    current["load_first"] = current["load_first"]
                    current["n"] += 1
            elif current is not None:
                stops.append(current)
                current = None
    except Exception as exc:  # noqa: BLE001
        print("skip", exc, flush=True)
    time.sleep(3)
if current is not None:
    stops.append(current)
handle.close()

print(f"\n采样 {MINUTES:.0f} 分钟，停车片段 {len(stops)} 个：")
for item in stops:
    dep_first = float(item["dep_first"]) if item["dep_first"] is not None else None
    dep_last = float(item["dep_last"]) if item["dep_last"] is not None else None
    duration = item["end"] - item["start"]
    verdict = "?"
    if dep_first is not None and dep_first > 60:
        verdict = "按策略/时刻表等（departure 从 %.0f 递减到 %.1f）→ 改停站策略有效" % (dep_first, dep_last)
    elif dep_first is not None and abs(dep_first) < 5 and duration > 60:
        verdict = "被占住（departure≈0 却停了 %.0f 秒）→ 改策略无效，要动站台/让行" % duration
    elif dep_first is None:
        verdict = "无 departure 字段"
    print("   停 %5.0f 秒  t=%.0f→%.0f  time_until_departure %s → %s  |  %s"
          % (duration, item["start"], item["end"], dep_first, dep_last, verdict))
print("CSV:", OUT)
