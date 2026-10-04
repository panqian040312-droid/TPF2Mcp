# -*- coding: utf-8 -*-
"""把实测从「墙上时钟」换算到「游戏内时间」，再与运行图计划（相位图）逐项对照。

背景：本机 CPU 跟不上，游戏仿真只跑到挂钟的 ~0.48 倍。
station_events 表同时存了 observed_at（墙上）与 game_time_ms（游戏内），
因此可以把同一段实测用两套时间各算一遍，看差异到底来自哪里。
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
WORK = Path(r"E:\workbody\TPF2Mcp")
DB_COPY = WORK / "_tmpdb" / "station-events.sqlite3"

CORRIDOR = {224503: "京广客运", 98983: "JY客运", 90194: "JI线路(地铁)"}


def load_events() -> list[dict]:
    DB_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MOD / "bridge" / "station-events.sqlite3", DB_COPY)
    con = sqlite3.connect(str(DB_COPY))
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("select * from station_events order by game_time_ms")]
    con.close()
    return rows


def fmt(sec: float | None) -> str:
    if sec is None:
        return "—"
    return f"{sec:.0f}s ({sec/60:.1f}分)"


def main() -> None:
    events = load_events()
    plan = json.loads((MOD / "diagnostics" / "rail-operations" / "line-timetable-plan.json").read_text(encoding="utf-8"))
    plan_by_id = {int(l["line_id"]): l for l in plan["lines"]}

    print("=" * 78)
    print("一、两套时钟的比例（游戏时间 ÷ 墙上时间）")
    print("=" * 78)
    span_w = events[-1]["observed_at"] - events[0]["observed_at"]
    span_g = (events[-1]["game_time_ms"] - events[0]["game_time_ms"]) / 1000.0
    print(f"全表：墙上 {span_w:.0f}s / 游戏 {span_g:.0f}s → 比例 {span_g/span_w:.3f}")
    seg = max(1, len(events) // 8)
    print(f"\n{'窗口起点':>10} {'Δ墙上':>8} {'Δ游戏':>8} {'比例':>7}")
    for i in range(0, len(events) - 1, seg):
        a, b = events[i], events[min(i + seg, len(events) - 1)]
        dw = b["observed_at"] - a["observed_at"]
        dg = (b["game_time_ms"] - a["game_time_ms"]) / 1000.0
        if dw > 0:
            print(f"{time.strftime('%H:%M:%S', time.localtime(a['observed_at'])):>10} {dw:>8.0f} {dg:>8.0f} {dg/dw:>7.3f}")

    print()
    print("=" * 78)
    print("二、京广客运（列车41）实测 vs 相位图")
    print("=" * 78)
    p = plan_by_id.get(224503, {})
    print(f"相位图侧：cycle={fmt(p.get('cycle_seconds'))} headway={fmt(p.get('headway_seconds'))} "
          f"车数={p.get('vehicle_count')}")
    stops_plan = p.get("stops") or []
    print("相位图停站时刻（到站偏移 / 区间运行 / 停站时长）：")
    for s in stops_plan:
        print(f"   {s.get('sequence_index')} {str(s.get('station_name')):<14} 到 +{s.get('arrival_offset_seconds')}s  "
              f"区间 {s.get('next_leg_running_seconds')}s  停站 {s.get('scheduled_dwell_seconds')}s")

    mine = [e for e in events if e["vehicle_id"] == 159365]
    print(f"\n实测事件 {len(mine)} 条（时间已换算游戏时间）")
    base = mine[0]["game_time_ms"]
    prev = None
    for e in mine[-24:]:
        g = (e["game_time_ms"] - base) / 1000.0
        gap = "" if prev is None else f"  (+{(e['game_time_ms']-prev)/1000.0:.0f}s游戏)"
        print(f"   t={g:>7.0f}s  {e['event_type']:<4} {str(e['station_name']):<14}{gap}")
        prev = e["game_time_ms"]

    # 回到同一站的周期（游戏时间）
    print("\n回到同一站的周期（游戏时间）：")
    for st in {e["station_name"] for e in mine}:
        ts = [e["game_time_ms"] for e in mine if e["station_name"] == st and e["event_type"] == "STOP"]
        if len(ts) > 1:
            gaps = [round((ts[i + 1] - ts[i]) / 1000.0) for i in range(len(ts) - 1)]
            print(f"   {st:<16} 周期(g) {gaps}")

    print()
    print("=" * 78)
    print("三、走廊三线：实测周期（游戏时间） vs 相位图")
    print("=" * 78)
    snap = json.loads((MOD / "bridge" / "state.json").read_text(encoding="utf-8"))
    veh_by_line: dict[int, list[tuple[int, str]]] = {}
    for v in snap.get("vehicles", []):
        lid = v.get("line_id")
        if lid in CORRIDOR:
            veh_by_line.setdefault(lid, []).append((v["entity_id"], v.get("name")))
    print(f"{'线路':<14}{'车':>3}{'相位图周期':>14}{'实测周期(游戏)':>16}{'实测(墙上)':>14}{'偏差':>9}")
    for lid, name in CORRIDOR.items():
        p = plan_by_id.get(lid, {})
        cyc_plan = p.get("cycle_seconds") or ((p.get("headway_seconds") or 0) * (p.get("vehicle_count") or 1))
        members = veh_by_line.get(lid, [])
        for vid, vname in members:
            ev = [e for e in events if e["vehicle_id"] == vid]
            gts = [e for e in ev if e["event_type"] == "STOP"]
            if len(gts) < 2:
                print(f"{name:<14}{str(vname):>6}{fmt(cyc_plan):>16}{'样本不足':>14}")
                continue
            first = gts[0]["station_name"]
            same = [e["game_time_ms"] for e in gts if e["station_name"] == first]
            wall = [e["observed_at"] for e in gts if e["station_name"] == first]
            if len(same) > 1:
                cyc_g = (same[-1] - same[0]) / 1000.0 / (len(same) - 1)
                cyc_w = (wall[-1] - wall[0]) / (len(same) - 1)
            else:
                cyc_g = cyc_w = None
            dev = f"{(cyc_g/cyc_plan-1)*100:+.0f}%" if cyc_g and cyc_plan else "—"
            print(f"{name:<14}{str(vname):>6}{fmt(cyc_plan):>16}{fmt(cyc_g):>16}{fmt(cyc_w):>14}{dev:>9}")

    print()
    print("=" * 78)
    print("四、相位分布：实测到达间隔（游戏时间） vs 相位图间隔")
    print("=" * 78)
    for lid, name in CORRIDOR.items():
        p = plan_by_id.get(lid, {})
        print(f"\n{name}  相位图 headway={fmt(p.get('headway_seconds'))}  相位偏移={p.get('phase_offsets_seconds')}")
        first_station = None
        for s in (p.get("stops") or []):
            first_station = s.get("station_name")
            break
        ev = [e for e in events if e["line_id"] == lid and e["event_type"] == "STOP"]
        by_station: dict[str, list[tuple[float, str]]] = {}
        for e in ev:
            by_station.setdefault(e["station_name"], []).append((e["game_time_ms"] / 1000.0, e["vehicle_name"]))
        best = max(by_station.items(), key=lambda kv: len(kv[1])) if by_station else None
        if not best:
            print("   无实测到达样本")
            continue
        st, seq = best
        seq.sort()
        print(f"   样本最多的站：{st}（{len(seq)} 次到达）")
        gaps = [round(seq[i + 1][0] - seq[i][0]) for i in range(len(seq) - 1)]
        if gaps:
            mean = sum(gaps) / len(gaps)
            print(f"   到达间隔(游戏)：{[g for g in gaps][:12]}")
            print(f"   平均 {mean:.0f}s  最短 {min(gaps)}s  最长 {max(gaps)}s  "
                  f"离散度CV={(max(gaps)-min(gaps))/mean if mean else 0:.2f}")


if __name__ == "__main__":
    main()
