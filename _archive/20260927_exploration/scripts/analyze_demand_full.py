"""全线路真实客流分析：读取 /api/demand-live 快照 + 存档快照，输出表格与报告。"""
import json
from pathlib import Path

ROOT = Path(r"E:\workbody\TPF2Mcp")
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")

live = json.load(open(ROOT / "_dl.json", encoding="utf-8"))
snap = json.load(open(MOD / "bridge/state.json", encoding="utf-8"))
net = json.load(open(MOD / "bridge/rail-network.json", encoding="utf-8"))

RAIL = {int(l["entity_id"]) for l in net["lines"]}
lines_by_id = {int(l["entity_id"]): l for l in snap["lines"]}
veh_per_line: dict[int, int] = {}
for v in snap["vehicles"]:
    lid = v.get("line_id")
    if isinstance(lid, int):
        veh_per_line[lid] = veh_per_line.get(lid, 0) + 1

rows = []
for key, item in live["lines"].items():
    lid = int(key)
    meta = lines_by_id.get(lid, {})
    pax = item.get("pax") or {}
    cargo = item.get("cargo") or {}
    rows.append({
        "id": lid, "name": item.get("line_name") or meta.get("name"),
        "vehicles": veh_per_line.get(lid, 0),
        "stops": meta.get("stop_count"), "rate": meta.get("throughput") or 0,
        "headway": meta.get("frequency_seconds") or 0,
        "onboard": pax.get("onboard") or 0, "waiting": pax.get("waiting") or 0,
        "avg_wait": pax.get("avg_wait_s"), "seats": item.get("seats") or 0,
        "load": item.get("load_factor"),
        "cargo_on": cargo.get("onboard") or 0, "cargo_wait": cargo.get("waiting") or 0,
        "cargo_cap": item.get("cargo_capacity") or 0,
        "cargo_types": item.get("cargo_types") or [],
        "vehicle_load": item.get("vehicle_load") or [],
        "journey": item.get("by_journey") or [],
    })

pax_lines = [r for r in rows if r["seats"] > 0]
cargo_lines = [r for r in rows if r["seats"] == 0]
pax_lines.sort(key=lambda r: -(r["load"] or 0))

out = []
def p(text=""):
    print(text)
    out.append(text)

p(f"# 全线路真实客流（引擎实测，{len(rows)} 条铁路线）")
p()
tot_on = sum(r["onboard"] for r in pax_lines)
tot_wait = sum(r["waiting"] for r in pax_lines)
tot_seats = sum(r["seats"] for r in pax_lines)
p(f"铁路客运合计：在车 {tot_on:,} 人 ｜ 候车 {tot_wait:,} 人 ｜ 在册座位 {tot_seats:,} ｜ 整体实载率 {(tot_on/tot_seats*100 if tot_seats else 0):.1f}%")
p(f"铁路货运合计：在车 {sum(r['cargo_on'] for r in cargo_lines):,} 件 ｜ 候运 {sum(r['cargo_wait'] for r in cargo_lines):,} 件")
p()
p("## 客运线路（按实载率降序）")
h = f"{'线路':<14}{'车':>3}{'站':>4}{'座位':>7}{'车上':>6}{'候车':>7}{'实载率':>8}{'平均等待':>10}{'班次':>8}{'运力rate':>9}"
p(h); p("-" * len(h))
for r in pax_lines:
    wait_txt = f"{r['avg_wait']:.0f}s" if r.get("avg_wait") is not None else "—"
    p(f"{str(r['name'])[:13]:<14}{r['vehicles']:>3}{r['stops'] or 0:>4}{r['seats']:>7}{r['onboard']:>6}{r['waiting']:>7}"
      f"{(r['load'] or 0)*100:>7.0f}%{wait_txt:>10}{r['headway']/60:>7.1f}m{r['rate']:>9}")
p()
p("## 逐列车实载率（只有实测数据的列车）")
h2 = f"{'线路':<14}{'列车':>9}{'座位':>6}{'车上':>6}{'实载率':>8}"
p(h2)
for r in pax_lines:
    for v in r["vehicle_load"]:
        seats = v.get("seats") or 0
        on = v.get("onboard") or 0
        p(f"{str(r['name'])[:13]:<14}{v['vehicle_id']:>9}{seats:>6}{on:>6}{(on/seats*100 if seats else 0):>7.0f}%")
p()
p("## 货运线路（按在车件数降序）")
cargo_lines.sort(key=lambda r: -r["cargo_on"])
h3 = f"{'线路':<14}{'车':>3}{'载重容量':>9}{'车上':>6}{'候运':>6}{'平均等待':>10}"
p(h3)
for r in cargo_lines:
    wait_txt = f"{r['avg_wait']:.0f}s" if r.get("avg_wait") is not None else "—"
    p(f"{str(r['name'])[:13]:<14}{r['vehicles']:>3}{r['cargo_cap']:>9}{r['cargo_on']:>6}{r['cargo_wait']:>6}{wait_txt:>10}")
p()
p("## 诊断分类")
sat = [r for r in pax_lines if (r["load"] or 0) >= 0.9]
mid = [r for r in pax_lines if 0.5 <= (r["load"] or 0) < 0.9]
low = [r for r in pax_lines if (r["load"] or 0) < 0.5]
p(f"- 运力饱和（实载率 ≥90%）：{', '.join(f'{r['name']}({r['load']*100:.0f}%)' for r in sat) or '无'}")
p(f"- 中等（50–90%）：{', '.join(f'{r['name']}({r['load']*100:.0f}%)' for r in mid) or '无'}")
p(f"- 偏空（<50%）：{', '.join(f'{r['name']}({r['load']*100:.0f}%)' for r in low) or '无'}")
p()
p("### 候车远多于在车（班次不足的信号：候车 ≥ 2×车上 且 ≥200 人）")
for r in sorted(pax_lines, key=lambda x: -(x["waiting"] / max(x["onboard"], 1))):
    if r["waiting"] >= 2 * max(r["onboard"], 1) and r["waiting"] >= 200:
        ratio = r["waiting"] / max(r["onboard"], 1)
        p(f"- {r['name']}：候车 {r['waiting']} vs 车上 {r['onboard']}（{ratio:.1f} 倍），实载率 {(r['load'] or 0)*100:.0f}%，班次 {r['headway']/60:.1f} 分钟，平均等待 {(r.get('avg_wait') or 0):.0f}s")
p()
p("### 运力配置(rate)最高 vs 实载率，验证排名是否可用")
p(f"{'线路':<14}{'rate排名':>9}{'rate':>7}{'实载率':>8}{'车上':>6}{'候车':>7}")
rank = {r["id"]: i + 1 for i, r in enumerate(sorted(pax_lines, key=lambda x: -x["rate"]))}
for r in sorted(pax_lines, key=lambda x: -x["rate"])[:6]:
    p(f"{str(r['name'])[:13]:<14}{rank[r['id']]:>9}{r['rate']:>7}{(r['load'] or 0)*100:>7.0f}%{r['onboard']:>6}{r['waiting']:>7}")

text = "\n".join(out)
(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "reports/TPF2全线路客流实测_20260927.md").write_text(
    "# TPF2 全线路真实客流实测\n\n"
    "数据源：`/api/demand-live`（引擎 `simPersonSystem/simCargoSystem.getSimPersonsForLine`，地图服务原生采集，只读）\n"
    f"采样时刻：{live.get('sweep', {}).get('finished_at')}｜线路数：{len(rows)}\n\n"
    "> 说明：车上＝此刻在车内；候车＝此刻在站排队；实载率＝车上÷在册座位。快照性质，非累计量。\n\n"
    "```\n" + text + "\n```\n",
    encoding="utf-8")
print("\n报告已写出 reports/TPF2全线路客流实测_20260927.md")
