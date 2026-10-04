"""按列车（编组）汇总成本：整列购置价与整列年运行费。只读。"""
import json
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
snap = json.loads((MOD / "bridge" / "state.json").read_text(encoding="utf-8"))
net = json.loads((MOD / "bridge" / "rail-network.json").read_text(encoding="utf-8"))
resolved = json.loads(Path(r"E:\workbody\TPF2Mcp\vehicle_cost_resolved.json").read_text(encoding="utf-8"))

rail_ids = {int(l["entity_id"]) for l in net["lines"]}
line_names = {int(l["entity_id"]): l["name"] for l in snap["lines"] if int(l["entity_id"]) in rail_ids}
DEFAULT_UNIT_TO_DOLLAR = 0.5   # mod 自述：1 单位 = 0.5 美元


def model_cost(model: str):
    info = resolved.get(model) or {}
    cost = info.get("cost") or {}
    maint = info.get("maintenance") or {}
    price = cost.get("price")
    run = maint.get("runningCosts")
    scale = maint.get("runningCostScale")
    return (price if isinstance(price, (int, float)) and price > 0 else None,
            run if isinstance(run, (int, float)) and run > 0 else None,
            scale if isinstance(scale, (int, float)) else None)


rows = []
for v in snap["vehicles"]:
    if v.get("line_id") not in rail_ids:
        continue
    parts = v.get("consist_parts") or []
    price_sum = 0.0
    run_sum = 0.0
    unknown_price = unknown_run = 0
    scales = set()
    for part in parts:
        price, run, scale = model_cost(str(part.get("model_name") or ""))
        if price:
            price_sum += price
        else:
            unknown_price += 1
        if run:
            run_sum += run
        else:
            unknown_run += 1
        if scale is not None:
            scales.add(scale)
    rows.append({
        "name": v["name"], "line": line_names[v["line_id"]], "cars": len(parts),
        "price_file": price_sum, "price_usd": price_sum * DEFAULT_UNIT_TO_DOLLAR,
        "run_file": run_sum, "run_usd": run_sum * DEFAULT_UNIT_TO_DOLLAR,
        "unknown_price": unknown_price, "unknown_run": unknown_run,
        "scale": min(scales) if scales else None,
    })

print("=== 按列车汇总成本（文件值；美元列按 1 单位 = 0.5 美元折算）===")
print(f"{'列车':<8}{'线路':<14}{'节':>3}{'整列购置(文件)':>16}{'≈美元':>14}{'整列运行/期(文件)':>18}{'≈美元':>10}  说明")
for r in sorted(rows, key=lambda r: -r["price_file"]):
    note = []
    if r["unknown_price"]:
        note.append(f"{r['unknown_price']} 节自动定价")
    if r["unknown_run"]:
        note.append(f"{r['unknown_run']} 节运行费未定义")
    if r["scale"] and r["scale"] < 1:
        note.append(f"运行费 {r['scale']}×")
    print(f"{str(r['name'])[:7]:<8}{str(r['line'])[:12]:<14}{r['cars']:>3}{r['price_file']:>16,.0f}"
          f"{r['price_usd']:>14,.0f}{r['run_file']:>18,.0f}{r['run_usd']:>10,.0f}  {'、'.join(note)}")

print()
print("=== 单列成本最高的车型 ===")
by_line = {}
for r in rows:
    key = r["line"]
    by_line.setdefault(key, []).append(r)
for line, items in sorted(by_line.items(), key=lambda kv: -max(x["price_file"] for x in kv[1])):
    top = max(items, key=lambda x: x["price_file"])
    if top["price_file"] > 0:
        print(f"  {line:<16} {top['name']:<8} {top['cars']:>2} 节  整列购置 {top['price_file']:>14,.0f}（≈${top['price_usd']:>12,.0f}）"
              f"  运行 {top['run_file']:>10,.0f}/期（≈${top['run_usd']:>9,.0f}）")

Path(r"E:\workbody\TPF2Mcp\vehicle_costs_per_train.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("已写入 vehicle_costs_per_train.json")
