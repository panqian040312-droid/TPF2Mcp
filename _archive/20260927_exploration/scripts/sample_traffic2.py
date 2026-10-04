"""采样实时数据（保留每次采样的车辆明细），用于区间并发与冲突分析。只读。"""
import json
import time
import urllib.request

OUT = r"E:\workbody\TPF2Mcp\traffic_samples2.json"
DURATION = 180
INTERVAL = 3

frames = []
counts = None
simulation = None
start = time.time()
while time.time() - start < DURATION:
    try:
        data = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/live", timeout=15).read())
    except Exception as error:
        print("采样失败:", error)
        time.sleep(INTERVAL)
        continue
    counts = data.get("counts")
    simulation = data.get("simulation")
    frames.append({
        "t": round(time.time() - start, 1),
        "vehicles": [
            {
                "id": v.get("entity_id"),
                "line": v.get("line_id"),
                "edge": v.get("edge_id"),
                "block": v.get("block_id"),
                "speed": v.get("speed_kmh"),
            }
            for v in (data.get("vehicles") or [])
        ],
    })
    print(f"帧 {len(frames)}: {len(frames[-1]['vehicles'])} 辆")
    time.sleep(INTERVAL)

payload = {
    "duration_seconds": round(time.time() - start, 1),
    "interval_seconds": INTERVAL,
    "frames": frames,
    "counts": counts,
    "simulation_status": (simulation or {}).get("status"),
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False)
print("已写入", OUT, "| 帧数", len(frames), "| 时长", payload["duration_seconds"], "秒")
