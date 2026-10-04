# -*- coding: utf-8 -*-
"""station_log 去重逻辑的离线自检（不碰游戏，用合成帧验证）。

验证的缺陷：旧实现每帧把 presence 整体覆盖为"仅本帧所见"，车辆一旦在站内被采样缺帧，
就丢失 station:type 记录，下一帧回到同一站被当成新到站 → 同一次停站被记两次。
线上实测该缺陷造成 24% 的重复行（并伪造出"1 秒间隔""8 秒整圈"这类假数据）。

三个场景各自独立，均符合列车的真实运动（同一站的两次真实到站之间，必然隔着一整个区间）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(r"E:\workbody\TPF2Mcp") / "mcp_server" / "src"))
from tpf2_mcp.station_log import StationEventStore  # noqa: E402

MANIFEST = {
    "lines": [{"entity_id": 1, "name": "测试线", "stops": [{"station_group_id": 100}, {"station_group_id": 200}]}],
    "stations": [
        {"entity_id": 100, "name": "甲站", "terminals": [{"platform_edge_ids": [9001]}]},
        {"entity_id": 200, "name": "乙站", "terminals": [{"platform_edge_ids": [9002]}]},
        {"entity_id": 300, "name": "丙站（不在本线停站表内）", "terminals": [{"platform_edge_ids": [9003]}]},
    ],
}
SAVE = "test-save"


def frame(game_ms: int, *, stop_index: int | None = None, raw_state: int = 2, have: bool = True,
          speed: float = 0.0, edge: int | None = None) -> dict:
    vehicles = []
    if have:
        vehicles.append({"entity_id": 7, "name": "测试车", "line_id": 1, "stop_index": stop_index,
                         "raw_state": raw_state, "speed_kmh": speed, "edge_id": edge})
    return {"simulation": {"clock": {"game_time": game_ms}}, "vehicles": vehicles}


def at_甲(ms: int) -> dict:
    return frame(ms, stop_index=0, raw_state=2)


def at_乙(ms: int) -> dict:
    return frame(ms, stop_index=1, raw_state=2)


AT_甲 = at_甲
AT_乙 = at_乙

SCENARIOS: list[tuple[str, list[tuple[str, dict, int]]]] = [
    ("场景A：站内缺帧不应重复记到站（本次修复的缺陷）", [
        ("到达甲站", AT_甲(1_000_000), 1),
        ("同站重复帧", AT_甲(1_001_000), 0),
        ("缺帧（车辆不在帧里）", frame(1_002_000, have=False), 0),
        ("缺帧后回到甲站 ← 旧版在此重复写一条", AT_甲(1_003_000), 0),
        ("再次缺帧", frame(1_004_000, have=False), 0),
        ("再次回到甲站", AT_甲(1_005_000), 0),
    ]),
    ("场景B：真正的下一次到站必须记录", [
        ("甲站", AT_甲(2_000_000), 1),
        ("开到乙站", AT_乙(2_100_000), 1),
        ("回到甲站（96 秒后，真实新到站）", AT_甲(2_196_000), 1),
        ("回到乙站（再次）", AT_乙(2_300_000), 1),
    ]),
    ("场景C：PASS 只记不在本线停站表内的车站", [
        ("甲站", AT_甲(3_000_000), 1),
        ("驶过丙站站台 → PASS", frame(3_010_000, stop_index=0, raw_state=3, speed=60.0, edge=9003), 1),
        ("驶过乙站站台（在停站表 → 不记）", frame(3_020_000, stop_index=0, raw_state=3, speed=60.0, edge=9002), 0),
    ]),
    ("场景D：长时间缺帧后回来仍应记录", [
        ("甲站", AT_甲(4_000_000), 1),
        ("缺帧 1", frame(4_010_000, have=False), 0),
        ("缺帧 2", frame(4_020_000, have=False), 0),
        ("缺帧 3", frame(4_030_000, have=False), 0),
        ("缺帧 4", frame(4_040_000, have=False), 0),
        ("缺帧 5", frame(4_050_000, have=False), 0),
        ("缺帧 6（超过 TTL）", frame(4_060_000, have=False), 0),
        ("重新出现且仍在甲站（长间隔，应记录）", AT_甲(4_500_000), 1),
    ]),
]


def run() -> None:
    ok = True
    for title, steps in SCENARIOS:
        print(f"\n{title}")
        with tempfile.TemporaryDirectory() as tmp:
            store = StationEventStore(Path(tmp) / "events.sqlite3")
            for label, payload, expect in steps:
                got = store.record_frame(payload, MANIFEST, SAVE, observed_at=1_790_000_000.0)
                flag = "✓" if got == expect else "✗"
                if got != expect:
                    ok = False
                print(f"  {flag} {label:<44} 写入 {got}（预期 {expect}）")
            rows = [dict(r) for r in store.query(100, SAVE, 50) + store.query(300, SAVE, 50)]
            if rows:
                print("   记录明细：" + " | ".join(
                    f"{r['event_type']} {r['station_name']}@{r['game_time_ms']}" for r in sorted(rows, key=lambda x: x["game_time_ms"])))
    print("\n结论：", "去重逻辑正确" if ok else "存在不符合预期的用例")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    run()
