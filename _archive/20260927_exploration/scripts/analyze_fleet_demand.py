# -*- coding: utf-8 -*-
"""按真实客流（引擎 getSimPersonsForLine / getSimCargosForLine）对全部铁路线排序。

判据刻意避开"引擎 rate"（已证伪：那是运力公式，不含需求）：
  * 实载率   = 车上乘客 ÷ 在册座位
  * 候车压力 = 候车 ÷ max(车上, 1)
  * 等待     = 候车等待中位数（均值会被坏样本污染，只用中位）
  * 空闲     = 实载率低 且 候车少 且 车不止一辆
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median

WORK = Path(r"E:\workbody\TPF2Mcp")
FEED = WORK / "_dl2.json"
COST = WORK / "ui" / "rail-map" / "line-cost-profile.json"
SNAPSHOT = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge\state.json")


def vehicles_by_line() -> dict[int, int]:
    """车辆数从存档快照取：客流接口对货运线不返回 vehicles。"""
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    counts: dict[int, int] = {}
    for vehicle in snapshot.get("vehicles", []):
        line_id = vehicle.get("line_id")
        if isinstance(line_id, int) and not isinstance(line_id, bool):
            counts[line_id] = counts.get(line_id, 0) + 1
    return counts


def num(value) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def fmt(sec) -> str:
    if not isinstance(sec, (int, float)) or sec <= 0:
        return "—"
    return f"{sec/60:.1f}分" if sec >= 60 else f"{sec:.0f}秒"


def count(value) -> int:
    """vehicles 字段在不同版本里可能是 int、list 或 dict（车辆→装载）。"""
    if isinstance(value, dict) or isinstance(value, list):
        return len(value)
    return int(value) if isinstance(value, (int, float)) else 0


def main() -> None:
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    lines = feed.get("lines") or {}
    costs = {}
    if COST.exists():
        costs = (json.loads(COST.read_text(encoding="utf-8")) or {}).get("lines") or {}

    rows = []
    fleet = vehicles_by_line()
    for key, entry in lines.items():
        pax = entry.get("pax") or {}
        cargo = entry.get("cargo") or {}
        seats = num(entry.get("seats"))
        onboard = num(pax.get("onboard"))
        waiting = num(pax.get("waiting"))
        c_on, c_wait = num(cargo.get("onboard")), num(cargo.get("waiting"))
        is_pax = seats > 0
        load = entry.get("load_factor")
        load = float(load) if isinstance(load, (int, float)) else ((onboard / seats) if seats else None)
        cost = costs.get(str(key)) or {}
        rows.append({
            "id": int(key), "name": entry.get("line_name") or str(key),
            "vehicles": fleet.get(int(key), count(entry.get("vehicles"))),
            "seats": seats, "onboard": onboard, "waiting": waiting,
            "median_wait": pax.get("median_wait_s"),
            "c_on": c_on, "c_wait": c_wait,
            "load": load, "kind": "客" if is_pax else "货",
            "free": cost.get("free_purchase") or 0, "cheap": cost.get("cheap_running") or 0,
        })

    pax_rows = [r for r in rows if r["kind"] == "客"]
    frt_rows = [r for r in rows if r["kind"] == "货"]

    print("=" * 96)
    print("一、客运线路：按实载率降序（座位>0）")
    print("=" * 96)
    print(f"{'线路':<14}{'车':>3}{'座位':>7}{'车上':>6}{'候车':>6}{'实载率':>8}{'等待中位':>10}{'车源':>8}")
    for r in sorted(pax_rows, key=lambda x: -(x["load"] or 0)):
        tag = "零购置" if r["free"] else ("成本打折" if r["cheap"] else "")
        load = f"{r['load']*100:.0f}%" if r["load"] is not None else "—"
        print(f"{str(r['name'])[:13]:<14}{r['vehicles']:>3}{int(r['seats']):>7}{int(r['onboard']):>6}"
              f"{int(r['waiting']):>6}{load:>8}{fmt(r['median_wait']):>10}{tag:>8}")

    print("\n" + "=" * 96)
    print("二、货运线路：按在车量降序")
    print("=" * 96)
    print(f"{'线路':<14}{'车':>3}{'在车':>6}{'候运':>6}{'在车/候运':>10}")
    for r in sorted(frt_rows, key=lambda x: -x["c_on"]):
        ratio = f"{r['c_on']/max(r['c_wait'],1):.1f}" if r["c_wait"] else "—"
        print(f"{str(r['name'])[:13]:<14}{r['vehicles']:>3}{int(r['c_on']):>6}{int(r['c_wait']):>6}{ratio:>10}")

    print("\n" + "=" * 96)
    print("三、分类结论")
    print("=" * 96)
    tight = [r for r in pax_rows if (r["load"] or 0) >= 0.85 and r["waiting"] >= 100]
    queues = [r for r in pax_rows if r["waiting"] >= 2 * max(r["onboard"], 1) and r["waiting"] >= 200]
    idle = [r for r in pax_rows if (r["load"] or 0) <= 0.30 and r["waiting"] < 60 and r["vehicles"] >= 2]
    long_wait = [r for r in pax_rows if isinstance(r["median_wait"], (int, float)) and r["median_wait"] > 900
                 and r["waiting"] >= 50]
    print("\n① 接近满载且有排队（加车首选）：")
    for r in tight:
        print(f"   {r['name']}：{r['vehicles']} 车 / {int(r['seats'])} 座，实载 {r['load']*100:.0f}%，"
              f"候车 {int(r['waiting'])}，等待中位 {fmt(r['median_wait'])}")
    if not tight:
        print("   无（没有同时满足 实载≥85% 且 候车≥100 的线）")
    print("\n② 候车远多于车上（班次不足）：")
    for r in queues:
        print(f"   {r['name']}：车上 {int(r['onboard'])} vs 候车 {int(r['waiting'])}"
              f"（{r['waiting']/max(r['onboard'],1):.1f} 倍），等待中位 {fmt(r['median_wait'])}")
    if not queues:
        print("   无")
    print("\n③ 明显空闲（可考虑调走车，但需先确认不是峰值间隙）：")
    for r in idle:
        print(f"   {r['name']}：{r['vehicles']} 车，实载 {r['load']*100:.0f}%，候车 {int(r['waiting'])}")
    if not idle:
        print("   无")
    print("\n④ 等待中位超过 15 分钟且仍有排队（服务频率问题）：")
    for r in long_wait:
        print(f"   {r['name']}：等待中位 {fmt(r['median_wait'])}，候车 {int(r['waiting'])}，{r['vehicles']} 车")
    if not long_wait:
        print("   无")

    print("\n" + "=" * 96)
    print("四、货运动脉排查：候运 >100 但**车上一件都没有**（要么没配车，要么车没在装）")
    print("=" * 96)
    dead = [r for r in frt_rows if r["c_wait"] >= 100 and r["c_on"] == 0]
    if not dead:
        print("   无")
    for r in sorted(dead, key=lambda x: -x["c_wait"]):
        flag = "⚠ 未配车" if r["vehicles"] == 0 else f"{r['vehicles']} 辆车但空载"
        print(f"   {str(r['name'])[:14]:<15} 候运 {int(r['c_wait']):>5} | {flag}")

    print("\n" + "=" * 96)
    print("五、总览")
    print("=" * 96)
    tot_seats = sum(r["seats"] for r in pax_rows)
    tot_on = sum(r["onboard"] for r in pax_rows)
    tot_wait = sum(r["waiting"] for r in pax_rows)
    print(f"  客车 {len(pax_rows)} 条 / {sum(r['vehicles'] for r in pax_rows)} 辆 / 座位 {int(tot_seats)}"
          f" / 车上 {int(tot_on)} / 候车 {int(tot_wait)} → 整体实载率 {tot_on/max(tot_seats,1)*100:.1f}%")
    print(f"  货车 {len(frt_rows)} 条 / {sum(r['vehicles'] for r in frt_rows)} 辆"
          f" / 在车 {int(sum(r['c_on'] for r in frt_rows))} / 候运 {int(sum(r['c_wait'] for r in frt_rows))}")
    print(f"  采样时刻(游戏毫秒) {feed.get('sampled_at_game_ms') or '—'}")


if __name__ == "__main__":
    main()
