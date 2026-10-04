# -*- coding: utf-8 -*-
"""用真实的连续两帧复现运行时的 record_frame 调用序列，定位重复事件为何没被挡下。"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
WORK = Path(r"E:\workbody\TPF2Mcp")
sys.path.insert(0, str(MOD / "mcp_server" / "src"))
from tpf2_mcp.station_log import StationEventStore  # noqa: E402

LIVE = MOD / "bridge" / "live-rail-state.json"
MANIFEST = MOD / "rail-network-manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot(tag: str) -> tuple[dict, float]:
    data = load_json(LIVE)
    stamp = LIVE.stat().st_mtime
    shutil.copy2(LIVE, WORK / f"_frame_{tag}.json")
    clock = ((data.get("simulation") or {}).get("clock") or {}).get("game_time")
    print(f"  {tag}: game_time={clock}  file_mtime={stamp:.2f}  车辆 {len(data.get('vehicles') or [])} 辆")
    return data, stamp


def main() -> None:
    print("抓两帧真实数据（间隔 3 秒，模拟一次轮询间隔）")
    f1, t1 = snapshot("1")
    time.sleep(3.0)
    f2, t2 = snapshot("2")
    manifest = load_json(MANIFEST)
    print(f"  清单：线路 {len(manifest.get('lines') or [])} 条，车站 {len(manifest.get('stations') or [])} 个")
    save_id = "world-v1-3be64aa7d6888335915d90b1"

    with tempfile.TemporaryDirectory() as tmp:
        store = StationEventStore(Path(tmp) / "e.sqlite3")
        n1 = store.record_frame(f1, manifest, save_id, observed_at=t1)
        print(f"\n第 1 次 record_frame → 写入 {n1} 条")
        rows1 = store.query(0, save_id, 0) if False else None
        n2 = store.record_frame(f2, manifest, save_id, observed_at=t2)
        print(f"第 2 次 record_frame → 写入 {n2} 条（同一批车多数仍在同一站，理想应为 0）")
        if n2:
            print("\n第 2 次被写入的行：")
            import sqlite3
            con = sqlite3.connect(str(Path(tmp) / "e.sqlite3"))
            for r in con.execute("select vehicle_name,station_name,event_type,game_time_ms from station_events order by id desc limit 12"):
                print("   ", r)
        print("\n内部状态：presence 条目 %d，_last_emit 条目 %d，_frame_index %d"
              % (len(store._presence), len(store._last_emit), store._frame_index))
        deltas = ((f2.get("simulation") or {}).get("deltas") or {})
        print("第 2 帧的 deltas:", deltas)


if __name__ == "__main__":
    main()
