# -*- coding: utf-8 -*-
"""采样列车41（京广客运）的停站段，按**游戏内时间**测量停留时长。

用途：核对停站等待上限 180 -> 60（2026-09-27 18:52 执行）的实际效果。
判据不需要等一整圈：列车到 Hanoi（stop_index 2）后停留多久，是那 77 秒终端停留的直接对照。

续采：重复运行即追加到同一 CSV（_dwell_after.csv），每次结束打印累计的停站段。
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "http://127.0.0.1:8765/api/live"
VEH = 159365
OUT = Path(r"E:\workbody\TPF2Mcp\_dwell_after.csv")
STATION_NAMES = {243069: "天津(终端)", 105581: "广州北站", 148720: "Hanoi中央车站(终端)"}
STOP_INDEX_NAMES = {0: "天津(终端)", 1: "广州北站", 2: "Hanoi中央车站(终端)"}


def sample(seconds: float, interval: float = 4.0) -> int:
    fresh = not OUT.exists()
    handle = OUT.open("a", newline="", encoding="utf-8")
    writer = csv.writer(handle)
    if fresh:
        writer.writerow(["wall", "game_s", "speed", "state", "stop_index", "edge", "t_until_dep", "block"])
    start = time.time()
    rows = 0
    while time.time() - start < seconds:
        try:
            data = json.loads(urllib.request.urlopen(API, timeout=15).read().decode())
            game_ms = (((data.get("simulation") or {}).get("clock") or {}).get("game_time"))
            vehicle = next((v for v in data.get("vehicles", []) if v.get("entity_id") == VEH), None)
            if vehicle is not None and game_ms:
                writer.writerow([round(time.time(), 2), round(game_ms / 1000.0, 1), vehicle.get("speed_kmh"),
                                 vehicle.get("raw_state"), vehicle.get("stop_index"), vehicle.get("edge_id"),
                                 vehicle.get("time_until_departure"), vehicle.get("block_id")])
                handle.flush()
                rows += 1
                if rows % 15 == 0:
                    where = ("停在 " + STOP_INDEX_NAMES.get(vehicle.get("stop_index"), "?")) if vehicle.get("raw_state") == 2 \
                        else f"运行中(下一个停站序 {vehicle.get('stop_index')})"
                    print(f"  已采 {rows} 帧（{time.time()-start:.0f}s/{seconds:.0f}s）"
                          f" | 列车41 {where}"
                          f" state={vehicle.get('raw_state')} 速度={vehicle.get('speed_kmh'):.0f}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print("  skip:", exc, flush=True)
        time.sleep(interval)
    handle.close()
    return rows


def report() -> None:
    if not OUT.exists():
        print("还没有采样数据")
        return
    with OUT.open(encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("game_s")]
    print(f"\n累计 {len(rows)} 帧 | 游戏时间跨度 "
          f"{float(rows[-1]['game_s'])-float(rows[0]['game_s']):.0f} 游戏秒"
          f"（墙上 {(float(rows[-1]['wall'])-float(rows[0]['wall']))/60:.1f} 分钟）")
    # 停站段：state==2（在站）连续帧
    segments: list[dict] = []
    current: dict | None = None
    for row in rows:
        at_stop = str(row["state"]) == "2"
        key = row.get("stop_index")
        if at_stop:
            if current is None or current["stop_index"] != key:
                if current:
                    segments.append(current)
                current = {"stop_index": key, "start": float(row["game_s"]), "end": float(row["game_s"]), "frames": 1,
                           "dep": row.get("t_until_dep")}
            else:
                current["end"] = float(row["game_s"])
                current["frames"] += 1
                current["dep"] = row.get("t_until_dep")
        elif current is not None:
            segments.append(current)
            current = None
    if current:
        segments.append(current)
    done = [s for s in segments if s["frames"] >= 2]
    print(f"\n检出的停站段（state=2，游戏内时间）：{len(done)} 段")
    for s in done:
        name = STOP_INDEX_NAMES.get(int(s["stop_index"]) if str(s["stop_index"]).isdigit() else -1, s["stop_index"])
        dep = s.get("dep")
        print(f"   stop_index {s['stop_index']} {name}: {s['end']-s['start']:.0f} 游戏秒"
              f"（{s['frames']} 帧，末帧 time_until_departure={dep}）")
    print("\n对照：改前 Hanoi 终端停留 51–103 游戏秒（中位 77 秒）；上限当时是 180，现在是 60。")


if __name__ == "__main__":
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 540
    print(f"采样列车41 停站段，{seconds:.0f} 秒（墙上）…")
    got = sample(seconds)
    print(f"本轮写入 {got} 帧")
    report()
