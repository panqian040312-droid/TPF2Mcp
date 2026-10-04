"""生成线路成本档案（基于已解析的模型成本，含显式定价与变量解析结果）。"""
import json
from collections import defaultdict
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
snap = json.loads((MOD / "bridge" / "state.json").read_text(encoding="utf-8"))
net = json.loads((MOD / "bridge" / "rail-network.json").read_text(encoding="utf-8"))
resolved = json.loads(Path(r"E:\workbody\TPF2Mcp\vehicle_cost_resolved.json").read_text(encoding="utf-8"))

rail_ids = {int(l["entity_id"]) for l in net["lines"]}
names = {int(l["entity_id"]): l["name"] for l in snap["lines"] if int(l["entity_id"]) in rail_ids}
vehicles = [v for v in snap["vehicles"] if v.get("line_id") in rail_ids]

GAME_UNIT_NOTE = "游戏内 1 单位 = 0.5 美元（复兴号 mod 说明自述），数值已按文件值给出"


def classify(model: str) -> dict:
    info = resolved.get(model) or {}
    cost = info.get("cost") or {}
    maint = info.get("maintenance") or {}
    price = cost.get("price")
    scale = cost.get("priceScale")
    run_costs = maint.get("runningCosts")
    run_scale = maint.get("runningCostScale")
    free_buy = price == 0 or scale == 0
    free_run = run_costs == 0 or run_scale == 0
    cheap_run = (isinstance(run_scale, (int, float)) and 0 < run_scale < 1)
    explicit_price = isinstance(price, (int, float)) and price > 0
    explicit_run = isinstance(run_costs, (int, float)) and run_costs > 0
    if free_buy:
        kind = "free_purchase"
    elif cheap_run:
        kind = "cheap_running"
    elif explicit_price or explicit_run:
        kind = "explicit"
    else:
        kind = "auto"
    return {"kind": kind, "price": price if isinstance(price, (int, float)) else None,
            "running_costs": run_costs if isinstance(run_costs, (int, float)) else None,
            "run_scale": run_scale if isinstance(run_scale, (int, float)) else None}


lines = defaultdict(lambda: {"vehicles": 0, "free_purchase": 0, "cheap_running": 0,
                             "explicit": 0, "auto": 0, "price_per_car_max": None,
                             "running_per_car_max": None, "models": []})
for v in vehicles:
    row = lines[str(v["line_id"])]
    row["vehicles"] += 1
    kinds = []
    for part in v.get("consist_parts") or []:
        info = classify(str(part.get("model_name") or ""))
        kinds.append(info)
        if info["price"]:
            row["price_per_car_max"] = max(row["price_per_car_max"] or 0, info["price"])
        if info["running_costs"]:
            row["running_per_car_max"] = max(row["running_per_car_max"] or 0, info["running_costs"])
    if kinds:
        if all(k["kind"] == "free_purchase" for k in kinds):
            row["free_purchase"] += 1
        elif any(k["kind"] == "cheap_running" for k in kinds):
            row["cheap_running"] += 1
        elif any(k["kind"] == "explicit" for k in kinds):
            row["explicit"] += 1
        else:
            row["auto"] += 1
    row["models"] = list({str(p.get("model_name")) for p in (v.get("consist_parts") or [])})[:3]

payload = {
    "generated_at": int(__import__("time").time()),
    "source": "车辆 .mdl 的 cost.price / maintenance.runningCosts / runningCostScale（已解析 Lua 变量）",
    "note": GAME_UNIT_NOTE + "；price=-1 或 runningCosts=-1 表示游戏自动定价，文件内无具体金额。"
            "「显式定价」= mod 作者写了具体数值。",
    "lines": {k: {**v, "name": names.get(int(k))} for k, v in lines.items()},
}
out = Path(r"E:\workbody\TPF2Mcp\ui\rail-map\line-cost-profile.json")
out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
print("已生成", out)
print(f"{'线路':<16}{'车':>3}{'零购置':>7}{'运行打折':>9}{'显式定价':>9}{'自动定价':>9}{'每节价':>12}")
for k, v in sorted(lines.items(), key=lambda kv: names.get(int(kv[0])) or ""):
    print(f"{str(names.get(int(k)))[:15]:<16}{v['vehicles']:>3}{v['free_purchase']:>7}{v['cheap_running']:>9}"
          f"{v['explicit']:>9}{v['auto']:>9}{str(v['price_per_car_max'] or '—'):>12}")
