"""连续采样列车41（或任意车）的速度与状态，量化「行驶 vs 停站/折返」占比。
CSV 实时落盘，即使进程被杀也能拿到部分结果。
用法: python trace_train.py [vehicle_id] [minutes]
"""
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

VEHICLE = int(sys.argv[1]) if len(sys.argv) > 1 else 159365
MINUTES = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
OUT = Path(rf"E:\workbody\TPF2Mcp\_trace_{VEHICLE}.csv")

FIELDS = ["t", "speed_kmh", "accel", "stop_index", "edge_id", "block_id",
          "time_until_departure", "time_until_load", "doors_open", "raw_state", "auto_departure"]

with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    t0 = time.time()
    while time.time() - t0 < MINUTES * 60:
        try:
            data = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/live", timeout=10).read().decode())
            match = [v for v in data.get("vehicles", []) if v.get("entity_id") == VEHICLE]
            if match:
                v = match[0]
                writer.writerow({
                    "t": round(time.time() - t0, 1),
                    "speed_kmh": v.get("speed_kmh"), "accel": v.get("acceleration_mps2"),
                    "stop_index": v.get("stop_index"), "edge_id": v.get("edge_id"),
                    "block_id": v.get("block_id"), "time_until_departure": v.get("time_until_departure"),
                    "time_until_load": v.get("time_until_load"), "doors_open": v.get("doors_open"),
                    "raw_state": v.get("raw_state"), "auto_departure": v.get("auto_departure"),
                })
                handle.flush()
        except Exception as exc:  # noqa: BLE001
            print("skip:", exc, flush=True)
        time.sleep(5)
print("完成，写入", OUT, flush=True)
