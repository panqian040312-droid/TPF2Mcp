# -*- coding: utf-8 -*-
"""按游戏内时间重算走廊三线的实测，并与相位图逐项对照（含事件去重与周期检测）。"""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
WORK = Path(r"E:\workbody\TPF2Mcp")
DB_COPY = WORK / "_tmpdb" / "station-events.sqlite3"
CORRIDOR = {224503: "京广客运", 98983: "JY客运", 90194: "JI线路(地铁)"}
VEH_FOCUS = 159365  # 列车41


def load() -> list[dict]:
    DB_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MOD / "bridge" / "station-events.sqlite3", DB_COPY)
    con = sqlite3.connect(str(DB_COPY))
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("select * from station_events order by game_time_ms, id")]
    con.close()
    return rows


def dedup(events: list[dict], window_ms: int = 5000) -> tuple[list[dict], int, int]:
    """同一车、同一站、同一类型，游戏时间相差 < window 视为重复上报，只保留第一条。"""
    out: list[dict] = []
    exact = 0
    seen_key: set[tuple] = set()
    for e in events:
        key = (e["vehicle_id"], e["station_id"], e["event_type"], e["game_time_ms"])
        if key in seen_key:
            exact += 1
            continue
        seen_key.add(key)
        dup = False
        for prev in reversed(out[-6:]):
            if prev["vehicle_id"] != e["vehicle_id"]:
                continue
            if prev["station_id"] == e["station_id"] and prev["event_type"] == e["event_type"] \
                    and e["game_time_ms"] - prev["game_time_ms"] < window_ms:
                dup = True
                break
        if not dup:
            out.append(e)
    return out, exact, len(events) - exact - len(out)


def detect_period(seq: list[dict]) -> tuple[int | None, float | None, list[float]]:
    """在访问序列里找最小周期 p（按站名比对），返回 (p, 周期秒中位, 各次周期)。"""
    names = [e["station_name"] for e in seq]
    gt = [e["game_time_ms"] / 1000.0 for e in seq]
    n = len(names)
    for p in range(2, n // 2 + 1):
        pairs = n - p
        if pairs < 2:
            break
        hit = sum(1 for i in range(pairs) if names[i] == names[i + p])
        if hit / pairs >= 0.8:
            cyc = sorted(gt[i + p] - gt[i] for i in range(pairs) if names[i] == names[i + p])
            med = cyc[len(cyc) // 2]
            return p, med, [round(c) for c in cyc]
    return None, None, []


def main() -> None:
    raw = load()
    events, exact, near = dedup(raw)
    print("=" * 80)
    print("〇、事件表去重情况（发现数据缺陷）")
    print("=" * 80)
    print(f"原始 {len(raw)} 条 → 去重后 {len(events)} 条  "
          f"(完全相同 {exact} 条, 同一车同站同类相距<5s游戏时间 {near} 条)")

    plan = json.loads((MOD / "diagnostics" / "rail-operations" / "line-timetable-plan.json").read_text(encoding="utf-8"))
    plan_by_id = {int(l["line_id"]): l for l in plan["lines"]}

    print()
    print("=" * 80)
    print("一、京广客运（列车41）：实测分段耗时（游戏时间） vs 相位图")
    print("=" * 80)
    p = plan_by_id[224503]
    print(f"相位图：整圈 {p['cycle_seconds']:.0f}s（{p['cycle_seconds']/60:.1f}分）")
    off = {s["station_name"]: s for s in p["stops"]}
    legs_plan = []
    names_plan = [s["station_name"] for s in p["stops"]]
    for i, s in enumerate(p["stops"]):
        nxt = p["stops"][(i + 1) % len(p["stops"])]
        legs_plan.append((s["station_name"], nxt["station_name"], s["next_leg_running_seconds"], s["scheduled_dwell_seconds"]))
    for a, b, run, dwell in legs_plan:
        print(f"   相位图 {a:<12}→{b:<14} 区间 {run}s + 停站 {dwell}s")

    seq = [e for e in events if e["vehicle_id"] == VEH_FOCUS]
    print(f"\n实测（游戏时间，去重后 {len(seq)} 条）")
    t0 = seq[0]["game_time_ms"] / 1000.0
    prev = None
    for e in seq:
        g = e["game_time_ms"] / 1000.0 - t0
        gap = "" if prev is None else f"  (+{e['game_time_ms']/1000.0-prev:.0f}s)"
        print(f"   t={g:>7.0f}s  {e['event_type']:<4} {str(e['station_name']):<14}{gap}")
        prev = e["game_time_ms"] / 1000.0

    print("\n分段耗时（相邻停站之间，游戏时间）：")
    stops = [e for e in seq if e["event_type"] == "STOP"]
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        d = (b["game_time_ms"] - a["game_time_ms"]) / 1000.0
        plan_pair = next((x for x in legs_plan if x[0] == a["station_name"] and x[1] == b["station_name"]), None)
        ref = f"{plan_pair[2] + plan_pair[3]}s" if plan_pair else "—"
        print(f"   {a['station_name']:<12}→{b['station_name']:<14} 实测 {d:>6.0f}s | 相位图 {ref:>8}")
    cyc = [stops[i + 1]["game_time_ms"] / 1000.0 - stops[i]["game_time_ms"] / 1000.0
           for i in range(len(stops) - 1)
           if stops[i]["station_name"] == "天津" and stops[i + 1]["station_name"] == "天津"]
    if cyc:
        print(f"\n整圈（天津→天津，游戏时间）：{[round(c) for c in cyc]}  中位 {sorted(cyc)[len(cyc)//2]:.0f}s"
              f" | 相位图 {p['cycle_seconds']:.0f}s  偏差 {(sorted(cyc)[len(cyc)//2]/p['cycle_seconds']-1)*100:+.1f}%")

    print()
    print("=" * 80)
    print("二、三线整圈周期：实测（游戏时间） vs 相位图（含墙上时钟对照）")
    print("=" * 80)
    ratio_wall = (raw[-1]["observed_at"] - raw[0]["observed_at"]) / ((raw[-1]["game_time_ms"] - raw[0]["game_time_ms"]) / 1000.0)
    print(f"（本机挂钟 ÷ 游戏时间 = {ratio_wall:.2f}，即墙上测得的时长要除以它才是游戏时间）\n")
    print(f"{'线路':<14}{'车辆':<8}{'相位图整圈':>11}{'实测整圈(游戏)':>15}{'等效墙上':>11}{'偏差':>9}{'周期长度(站数)':>14}")
    for lid, name in CORRIDOR.items():
        pp = plan_by_id.get(lid, {})
        cyc_plan = pp.get("cycle_seconds")
        vids = sorted({e["vehicle_id"] for e in events if e["line_id"] == lid})
        for vid in vids:
            vseq = [e for e in events if e["vehicle_id"] == vid]
            p_len, med, _ = detect_period(vseq)
            vname = next((e["vehicle_name"] for e in vseq), str(vid))
            if med is None:
                print(f"{name:<14}{str(vname):<8}{cyc_plan:>11.0f}{'未检出':>15}{'—':>11}{'—':>9}{'—':>14}")
                continue
            dev = f"{(med/cyc_plan-1)*100:+.0f}%" if cyc_plan else "—"
            print(f"{name:<14}{str(vname):<8}{cyc_plan:>11.0f}{med:>15.0f}{med*ratio_wall:>11.0f}{dev:>9}{p_len:>14}")

    print()
    print("=" * 80)
    print("三、相位间隔：相位图 headway vs 实测到达间隔（游戏时间）")
    print("=" * 80)
    for lid, name in CORRIDOR.items():
        pp = plan_by_id.get(lid, {})
        ev = [e for e in events if e["line_id"] == lid]
        by_st: dict[str, list[tuple[float, str]]] = {}
        for e in ev:
            by_st.setdefault(e["station_name"], []).append((e["game_time_ms"] / 1000.0, e["vehicle_name"]))
        if not by_st:
            continue
        st, arr = max(by_st.items(), key=lambda kv: len(kv[1]))
        arr.sort()
        gaps = [round(arr[i + 1][0] - arr[i][0]) for i in range(len(arr) - 1)]
        hw = pp.get("headway_seconds")
        vc = pp.get("vehicle_count") or 1
        print(f"\n{name}  相位图 headway={hw:.0f}s（{hw/60:.1f}分, {vc} 车）  相位偏移={pp.get('phase_offsets_seconds')}")
        print(f"   观测站 {st}：{len(arr)} 次到达，游戏时间间隔 {gaps[:14]}")
        if gaps:
            mean = sum(gaps) / len(gaps)
            print(f"   平均 {mean:.0f}s = 相位图的 {mean/hw*100:.0f}%｜最短 {min(gaps)}s｜最长 {max(gaps)}s")


if __name__ == "__main__":
    main()
