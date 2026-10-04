# -*- coding: utf-8 -*-
"""第 1 步（停站等待上限 180->60）的效果核对。

方法刻意与改前一致：
  * 整圈      = 相邻两次「天津 STOP」的游戏时间间隔
  * 终端停留  = 同一区段往返耗时之差（中山西 <-> 天津 / 中山西 <-> Hanoi）
                这个差就是列车在终端"停着不走"的时间，不需要记录发车事件
事件按 observed_at（墙上）切分改动时刻前后，时长一律用 game_time_ms。
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from statistics import median

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
DB_COPY = Path(r"E:\workbody\TPF2Mcp\_tmpdb\station-events.sqlite3")
VEH = 159365
CHANGE_WALL = 1790506301.0      # 2026-09-27 18:51:41 本地时间，首次写入该策略
BASELINE_CYCLE = 1005.0         # 改前整圈中位（游戏秒，4 次测量）
BASELINE_HANOI = (51, 103)      # 改前 Hanoi 终端停留区间（游戏秒）


def load() -> list[dict]:
    DB_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MOD / "bridge" / "station-events.sqlite3", DB_COPY)
    con = sqlite3.connect(str(DB_COPY))
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("select * from station_events order by game_time_ms, id")]
    con.close()
    # 去重：同一车+站+类型，游戏时间相差 <5 s 视为重复上报
    out: list[dict] = []
    for row in rows:
        if any(prev["vehicle_id"] == row["vehicle_id"] and prev["station_id"] == row["station_id"]
               and prev["event_type"] == row["event_type"]
               and 0 <= row["game_time_ms"] - prev["game_time_ms"] < 5000 for prev in out[-6:]):
            continue
        out.append(row)
    return out


def stops(events: list[dict], station: str, kind: str = "STOP", after: float = 0.0) -> list[float]:
    return [e["game_time_ms"] / 1000.0 for e in events
            if e["vehicle_id"] == VEH and e["station_name"] == station and e["event_type"] == kind
            and e["observed_at"] >= after]


def leg(events: list[dict], a: str, b: str, after: float = 0.0) -> list[float]:
    """a 到 b 的相邻耗时（游戏秒）。"""
    aa = sorted(stops(events, a, "PASS", after) + stops(events, a, "STOP", after))
    bb = sorted(stops(events, b, "PASS", after) + stops(events, b, "STOP", after))
    gaps = []
    for value in aa:
        nxt = [x for x in bb if x > value]
        if nxt:
            gaps.append(round(nxt[0] - value))
    return gaps


def arrival_leg(events: list[dict], ref: str, terminal: str, after: float = 0.0) -> list[float]:
    """抵达段：每个终端到站，减去它**紧邻之前**的一次基准站通过 → 纯运行时间。"""
    rr = sorted(stops(events, ref, "PASS") + stops(events, ref, "STOP"))
    tt = sorted(stops(events, terminal, "STOP", after) + stops(events, terminal, "PASS", after))
    gaps = []
    for value in tt:
        prev = [x for x in rr if x < value]
        if prev:
            gaps.append(round(value - prev[-1]))
    return gaps


def departure_leg(events: list[dict], terminal: str, ref: str, after: float = 0.0) -> list[float]:
    """离站段：每个终端停站，到它之后**紧邻第一次**基准站通过 → 运行 + 停留。"""
    rr = sorted(stops(events, ref, "PASS") + stops(events, ref, "STOP"))
    tt = sorted(stops(events, terminal, "STOP", after))
    gaps = []
    for value in tt:
        nxt = [x for x in rr if x > value]
        if nxt:
            gaps.append(round(nxt[0] - value))
    return gaps


def dwell_pairs(events: list[dict], terminal: str, ref: str, after: float = 0.0,
                before: float | None = None) -> list[int]:
    """逐圈精确停留：对每个终端停站 t，取前一个/后一个基准站通过 p、n，
    停留 = (n - t) - (t - p)。同一个班次内配对，避免把不同班次混在一起。"""
    rr = sorted(stops(events, ref, "PASS") + stops(events, ref, "STOP"))
    out = []
    for e in events:
        if e["vehicle_id"] != VEH or e["station_name"] != terminal or e["event_type"] != "STOP":
            continue
        if e["observed_at"] < after or (before is not None and e["observed_at"] >= before):
            continue
        t = e["game_time_ms"] / 1000.0
        prev = [x for x in rr if x < t]
        nxt = [x for x in rr if x > t]
        if prev and nxt:
            out.append(round((nxt[0] - t) - (t - prev[-1])))
    return out


def main() -> None:
    events = load()
    mine = [e for e in events if e["vehicle_id"] == VEH]
    if not mine:
        print("没有列车41 的事件")
        return
    print("列车41 事件共 %d 条 | 覆盖 %s – %s（墙上）"
          % (len(mine),
             __import__("time").strftime("%H:%M:%S", __import__("time").localtime(mine[0]["observed_at"])),
             __import__("time").strftime("%H:%M:%S", __import__("time").localtime(mine[-1]["observed_at"]))))
    print("改动时刻：18:51:41（墙上）")

    print("\n=== 一、整圈（相邻两次「天津 STOP」，游戏秒）===")
    ts_all = stops(events, "天津")
    pre = [g for g in (round(ts_all[i + 1] - ts_all[i]) for i in range(len(ts_all) - 1)) if g >= 60]
    ts_post = stops(events, "天津", after=CHANGE_WALL)
    print(f"  改前：{len(ts_all)} 次到站，有效间隔 {pre} → 中位 {median(pre):.0f} 秒（基线 {BASELINE_CYCLE:.0f}）")
    print(f"  改后：{len(ts_post)} 次到站 → 还差一次才能出间隔（预计约 441,95x 游戏秒到达）")

    print("\n=== 二、终端停留：逐圈配对（游戏秒）===")
    for terminal, base in (("Hanoi中央车站", BASELINE_HANOI), ("天津", None)):
        before_list = dwell_pairs(events, terminal, "中山西站", after=0.0, before=CHANGE_WALL)
        after_list = dwell_pairs(events, terminal, "中山西站", after=CHANGE_WALL)
        print(f"\n  {terminal}")
        print(f"    改前 n={len(before_list)} {before_list}"
              + (f" → 中位 {median(before_list):.0f}" if before_list else ""))
        print(f"    改后 n={len(after_list)} {after_list}"
              + (f" → 中位 {median(after_list):.0f}" if after_list else ""))
    ctrl_before = dwell_pairs(events, "Jeddah", "中山西站", after=0.0, before=CHANGE_WALL)
    print(f"\n  对照 Jeddah（非终端，应≈0）：改前 {ctrl_before}")


    print("\n=== 三、原始事件流（改后）===")
    for e in mine:
        if e["observed_at"] >= CHANGE_WALL:
            print("  %s  %-4s %-14s game=%d"
                  % (__import__("time").strftime("%H:%M:%S", __import__("time").localtime(e["observed_at"])),
                     e["event_type"], str(e["station_name"])[:13], e["game_time_ms"]))


if __name__ == "__main__":
    main()
