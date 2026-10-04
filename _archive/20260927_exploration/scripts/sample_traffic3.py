"""逐帧采样 /api/live，保留每车速度/状态/闭塞，用于量化拥堵。只读。

用法: python sample_traffic3.py [轮数] [间隔秒]
输出: _tmpdb/traffic_frames.json
"""
import json
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8765/api/live"
OUT = r"E:\workbody\TPF2Mcp\_tmpdb\traffic_frames.json"

ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 240
# mod 侧 live-rail-state.json 约每 2 秒墙上刷新一帧；间隔小于 2 秒会读到重复帧
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

frames = []
t0 = time.time()
for i in range(ROUNDS):
    try:
        raw = urllib.request.urlopen(URL, timeout=15).read()
        d = json.loads(raw)
    except Exception as error:  # noqa: BLE001
        sys.stderr.write(f"\n[skip {i}] {error}")
        time.sleep(INTERVAL)
        continue
    sim = d.get("simulation") or {}
    clock = sim.get("clock") or {}
    deltas = sim.get("deltas") or {}
    veh = []
    for v in d.get("vehicles") or []:
        veh.append({
            "id": v.get("entity_id"),
            "line": v.get("line_id"),
            "edge": v.get("edge_id"),
            "block": v.get("block_id"),
            "kmh": v.get("speed_kmh"),
            "raw": v.get("raw_state"),
            "doors": v.get("doors_open"),
            "stop": v.get("stop_index"),
            "until_dep": v.get("time_until_departure"),
        })
    frames.append({
        "wall": round(time.time() - t0, 2),
        "sampled_at": d.get("sampled_at"),
        "game_time": clock.get("game_time"),
        "wall_seconds": deltas.get("wall_seconds"),
        "game_delta": deltas.get("game_time"),
        "vehicles": veh,
    })
    sys.stderr.write(f"\r{i + 1}/{ROUNDS}")
    sys.stderr.flush()
    time.sleep(INTERVAL)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump({"rounds": ROUNDS, "interval": INTERVAL, "frames": frames}, fh, ensure_ascii=False)
sys.stderr.write(f"\nsaved {len(frames)} frames -> {OUT}\n")
