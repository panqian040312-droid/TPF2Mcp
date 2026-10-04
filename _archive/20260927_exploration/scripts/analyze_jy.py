"""JY客运 专项分析：从已保存的快照/事件库/采样文件里挖，不需要游戏运行。

数据源（全部在盘上）：
- bridge/state.json            线路与车辆快照（停站表、编组、容量）
- bridge/rail-network.json     车站名与几何
- bridge/station-events.sqlite3 真实停站事件（含 game_time_ms 游戏内时间）
- _dl2.json                    20:05 全线路客流采样（车上/候车/中位等待/逐车装载/OD）
- traffic_samples2.json        60 帧 × 每车位置（用于看列车在线上的实际间隔）

用法：python analyze_jy.py
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path

WORK = Path(r"E:\workbody\TPF2Mcp")
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
BRIDGE = MOD / "bridge"
LINE_ID = 98983          # JY客运
TMP_DB = WORK / "_tmpdb" / "station-events.sqlite3"

# 列车41/走廊其它线的车辆号，用于对照
JY_VEHICLES = {134839: "列车6", 234337: "列车12", 215084: "列车14", 344868: "列车21"}
JJ_VEHICLE = 159365      # 京广 列车41
JI_VEHICLES = {100835: "车100835", 253726: "车253726"}


def load_events() -> list[dict]:
    TMP_DB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE / "station-events.sqlite3", TMP_DB)
    con = sqlite3.connect(str(TMP_DB))
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute("select * from station_events order by game_time_ms, id")]


def dedup(events: list[dict], window_ms: int = 5000) -> list[dict]:
    """去掉相邻重复上报（同车同站同类型且游戏时间差 < window）。"""
    out: list[dict] = []
    for e in events:
        if any(p["vehicle_id"] == e["vehicle_id"] and p["station_id"] == e["station_id"]
               and p["event_type"] == e["event_type"]
               and 0 <= e["game_time_ms"] - p["game_time_ms"] < window_ms
               for p in out[-8:]):
            continue
        out.append(e)
    return out


def main() -> None:
    snap = json.loads((BRIDGE / "state.json").read_text(encoding="utf-8"))
    net = json.loads((BRIDGE / "rail-network.json").read_text(encoding="utf-8"))
    feed = json.loads((WORK / "_dl2.json").read_text(encoding="utf-8"))
    station_name = {int(s["entity_id"]): s["name"] for s in net["stations"]}

    line = next(x for x in snap["lines"] if x["entity_id"] == LINE_ID)
    stops = [int(s["station_id"]) for s in line["stops"]]
    stop_names = [station_name.get(sid, f"站{sid}") for sid in stops]
    vehicles = [v for v in snap["vehicles"] if v.get("line_id") == LINE_ID]

    print("=" * 92)
    print("一、JY客运 线路画像")
    print("=" * 92)
    print(f"停站 {line['stop_count']} 个：" + " → ".join(f"{i}.{n}" for i, n in enumerate(stop_names)))
    print(f"在册车辆 {len(vehicles)} 列 | 引擎班次 {line['frequency_seconds']:.1f} s（口径可疑，见报告）")
    capacity = 0
    print()
    print(f"{'车号':<8}{'节数':>4}{'座位':>6}{'模型':<34}")
    for v in sorted(vehicles, key=lambda x: x["entity_id"]):
        parts = v.get("consist_parts") or []
        model = (parts[0].get("model_name") or "").split("/")[-1] if parts else "-"
        capacity += v.get("capacity_total") or 0
        print(f"{v['name']:<8}{len(parts):>4}{v.get('capacity_total') or 0:>6}  {model:<34}")
    print(f"{'合计':<8}{'':>4}{capacity:>6}")

    print()
    print("=" * 92)
    print("二、实测客流（_dl2.json，20:05 采样）")
    print("=" * 92)
    entry = feed["lines"][str(LINE_ID)]
    pax = entry["pax"]
    print(f"车上 {pax['onboard']} 人 | 候车 {pax['waiting']} 人 | 合计 {pax['total']} 人")
    print(f"等待：中位 {pax['median_wait_s']:.0f} s（{pax['median_wait_s'] / 60:.1f} 分）"
          f"| P90 {pax['p90_wait_s']:.0f} s | 最长 {pax['max_wait_s']:.0f} s | 超 1 小时 {pax['waiting_over_1h']} 人")
    print(f"在册座位 {entry['seats']} | 整体实载率 {(entry['load_factor'] or 0) * 100:.1f}%")
    print()
    print("逐车装载：")
    for row in sorted(entry["vehicle_load"], key=lambda r: -(r["onboard"] or 0)):
        seats = row.get("seats") or 0
        load = (row["onboard"] / seats * 100) if seats else 0
        print(f"   {JY_VEHICLES.get(row['vehicle_id'], row['vehicle_id']):<10} 车上 {row['onboard']:>4} / 座位 {seats:>4}"
              f"  = {load:>5.1f}%")

    waiting_from: dict[int, int] = defaultdict(int)
    onboard_from: dict[int, int] = defaultdict(int)
    for j in entry.get("by_journey") or []:
        waiting_from[j.get("from")] += j.get("waiting") or 0
        onboard_from[j.get("from")] += j.get("onboard") or 0
    print()
    print("各站候车（按上车站点，_dl2 采样）：")
    print(f"{'站':<18}{'候车':>7}{'车上':>7}  占比")
    total_wait = sum(waiting_from.values()) or 1
    for idx, count in sorted(waiting_from.items(), key=lambda kv: -kv[1]):
        name = stop_names[idx] if isinstance(idx, int) and 0 <= idx < len(stop_names) else f"stop {idx}"
        print(f"{name:<18}{count:>7}{onboard_from.get(idx, 0):>7}  {count / total_wait * 100:>5.1f}%")

    events = dedup(load_events())
    jy_events = [e for e in events if e["line_id"] == LINE_ID]
    span_game = (events[-1]["game_time_ms"] - events[0]["game_time_ms"]) / 1000 if events else 0
    print()
    print("=" * 92)
    print(f"三、实测运行（station_events，去重后 {len(events)} 条；JY {len(jy_events)} 条；"
          f"覆盖 {span_game / 3600:.1f} 游戏小时）")
    print("=" * 92)
    # 每列车完整一圈的耗时
    print("各车单圈耗时（游戏秒，相邻两次回到首个停站的间隔）：")
    for vid, name in JY_VEHICLES.items():
        mine = [e for e in jy_events if e["vehicle_id"] == vid]
        if not mine:
            print(f"   {name}: 无事件")
            continue
        first_station = mine[0]["station_name"]
        ts = [e["game_time_ms"] / 1000 for e in mine if e["station_name"] == first_station]
        gaps = [round(ts[i + 1] - ts[i]) for i in range(len(ts) - 1)]
        good = [g for g in gaps if g > 300]
        text = f"   {name}: 事件 {len(mine)} 条 | 单圈" + (f" {good}" if good else " 样本不足")
        if good:
            text += f" | 中位 {statistics.median(good):.0f} s（{statistics.median(good) / 60:.1f} 分）"
        print(text)

    # 每个站的发车间隔（衡量"车是否均匀铺开"）
    print()
    print("各站发车间隔（游戏秒）：理想值 = 单圈 ÷ 4 列；明显不匀说明有扎堆")
    print(f"{'站':<18}{'次数':>5}{'中位':>8}{'最小':>8}{'最大':>8}{'最大/最小':>10}  说明")
    ideal = statistics.median([1616.0]) / 4  # 占位，稍后用实测单圈替换
    for idx, name in enumerate(stop_names):
        ts = sorted(e["game_time_ms"] / 1000 for e in jy_events if e["station_name"] == name)
        if len(ts) < 3:
            print(f"{name:<18}{len(ts):>5}{'—':>8}{'—':>8}{'—':>8}{'—':>10}  样本不足")
            continue
        gaps = [round(ts[i + 1] - ts[i]) for i in range(len(ts) - 1)]
        good = [g for g in gaps if 30 < g < 3000]
        if len(good) < 2:
            print(f"{name:<18}{len(ts):>5}{'—':>8}{'—':>8}{'—':>8}{'—':>10}  样本不足")
            continue
        med = statistics.median(good)
        ratio = max(good) / max(min(good), 1)
        flag = "扎堆" if ratio >= 3 else ("偏不匀" if ratio >= 2 else "较匀")
        print(f"{name:<18}{len(ts):>5}{med:>8.0f}{min(good):>8}{max(good):>8}{ratio:>10.1f}  {flag}")

    # 停站时长
    print()
    print("各站停站时长（游戏秒，STOP 到下一条同车事件的间隔）：")
    dwell: dict[str, list[int]] = defaultdict(list)
    for vid in JY_VEHICLES:
        mine = [e for e in jy_events if e["vehicle_id"] == vid]
        for i, e in enumerate(mine[:-1]):
            if e["event_type"] == "STOP":
                dwell[e["station_name"]].append(round((mine[i + 1]["game_time_ms"] - e["game_time_ms"]) / 1000))
    for name, values in sorted(dwell.items(), key=lambda kv: -statistics.median(kv[1])):
        good = [v for v in values if 0 < v < 600]
        if good:
            print(f"   {name:<18} 中位 {statistics.median(good):>5.0f} s | 样本 {len(good)} | 最大 {max(good)}")

    # 共用轨道
    print()
    print("=" * 92)
    print("四、JY客运 与谁共用轨道（trunk_traffic.json）")
    print("=" * 92)
    trunk = json.loads((WORK / "trunk_traffic.json").read_text(encoding="utf-8"))
    names = {int(k): v for k, v in (trunk.get("line_names") or {}).items()}
    for pair in sorted(trunk.get("trunk_pairs") or [], key=lambda p: -(p.get("edges") or 0)):
        if LINE_ID not in (pair.get("a"), pair.get("b")):
            continue
        other = pair["b"] if pair["a"] == LINE_ID else pair["a"]
        print(f"   JY客运 ↔ {names.get(other, other):<12} 共用 {pair.get('edges')} 段 | "
              f"{pair.get('traffic') or 0:.1f} 列/小时")


if __name__ == "__main__":
    main()
