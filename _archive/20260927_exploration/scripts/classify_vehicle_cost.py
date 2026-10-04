"""判定铁路车辆的成本属性：购置价、运行成本倍率。基于 .mdl metadata，权威定义。只读。"""
import json
import re
import zipfile
from pathlib import Path

GAME = Path(r"E:\SteamLibrary\steamapps\common\Transport Fever 2")
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
WORKSHOP = GAME.parent.parent / "workshop" / "content" / "1066780"

snap = json.loads((MOD / "bridge" / "state.json").read_text(encoding="utf-8"))
net = json.loads((MOD / "bridge" / "rail-network.json").read_text(encoding="utf-8"))
rail_ids = {int(l["entity_id"]) for l in net["lines"]}
lines = {int(l["entity_id"]): l for l in snap["lines"] if int(l["entity_id"]) in rail_ids}
vehicles = [v for v in snap["vehicles"] if v.get("line_id") in rail_ids]

roots = [GAME / "res" / "models" / "model"]
for base in (GAME / "mods", WORKSHOP):
    if base.is_dir():
        roots.extend(p / "res" / "models" / "model" for p in base.iterdir() if p.is_dir())
archive = GAME / "res" / "models" / "model.zip"

COST_BLOCK = re.compile(r"cost\s*=\s*\{([^}]*)\}", re.I)
MAINT_BLOCK = re.compile(r"maintenance\s*=\s*\{([^}]*)\}", re.I)
NUMBER = re.compile(r"([A-Za-z]+)\s*=\s*(-?[0-9.]+)")
cache: dict[str, dict] = {}


def read_source(name: str):
    relative = Path(*name.split("/"))
    if archive.is_file():
        try:
            with zipfile.ZipFile(archive) as zf:
                return zf.read("model/" + name)[:40000].decode("utf-8", errors="ignore"), str(archive)
        except (KeyError, OSError, zipfile.BadZipFile):
            pass
    for root in roots:
        path = root / relative
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="ignore")[:40000], str(path)
            except OSError:
                continue
    return None, None


def parse(name: str) -> dict:
    if name in cache:
        return cache[name]
    source, location = read_source(name)
    result = {"model": name, "path": location, "price": None, "priceScale": None,
              "runningCosts": None, "runningCostScale": None, "lifespan": None, "verdict": "unknown"}
    if source is None:
        cache[name] = result
        return result
    cost = COST_BLOCK.search(source)
    if cost:
        for key, value in NUMBER.findall(cost.group(1)):
            if key.lower() == "price":
                result["price"] = float(value)
            elif key.lower() == "pricescale":
                result["priceScale"] = float(value)
    maint = MAINT_BLOCK.search(source)
    if maint:
        for key, value in NUMBER.findall(maint.group(1)):
            key_lower = key.lower()
            if key_lower == "runningcosts":
                result["runningCosts"] = float(value)
            elif key_lower == "runningcostscale":
                result["runningCostScale"] = float(value)
            elif key_lower == "lifespan":
                result["lifespan"] = float(value)
    free_purchase = (result["price"] == 0) or (result["priceScale"] == 0)
    free_running = (result["runningCosts"] == 0) or (result["runningCostScale"] == 0)
    if free_purchase and free_running:
        result["verdict"] = "fully_free"
    elif free_running:
        result["verdict"] = "zero_running_cost"
    elif free_purchase:
        result["verdict"] = "free_purchase"
    else:
        result["verdict"] = "costly"
    cache[name] = result
    return result


model_names = sorted({str(p.get("model_name") or "") for v in vehicles
                      for p in (v.get("consist_parts") or []) if p.get("model_name")})
for name in model_names:
    parse(name)

print("=== 模型成本属性（.mdl metadata 权威定义）===")
print(f"{'模型':<44}{'price':>9}{'scale':>7}{'runC':>8}{'runScale':>9}  判定")
for name in model_names:
    r = parse(name)
    def show(x):
        return "—" if x is None else (str(int(x)) if float(x).is_integer() else str(x))
    print(f"{name[:43]:<44}{show(r['price']):>9}{show(r['priceScale']):>7}{show(r['runningCosts']):>8}{show(r['runningCostScale']):>9}  {r['verdict']}")

summary = {}
for name in model_names:
    v = parse(name)["verdict"]
    summary[v] = summary.get(v, 0) + 1
print()
print("模型判定汇总:", summary)

per_vehicle = {}
for v in vehicles:
    verdicts = [parse(str(p.get("model_name") or ""))["verdict"] for p in (v.get("consist_parts") or [])]
    if verdicts and all(x in ("fully_free", "zero_running_cost") for x in verdicts):
        per_vehicle[v["entity_id"]] = "free_running"
    elif any(x in ("fully_free", "zero_running_cost") for x in verdicts):
        per_vehicle[v["entity_id"]] = "mixed"
    else:
        per_vehicle[v["entity_id"]] = "costly"

print()
print("=== 按线路汇总 ===")
print(f"{'线路':<16}{'车':>3}{'零运行成本':>10}{'混合':>5}{'正常计费':>8}")
rows = []
for lid, line in lines.items():
    vs = [v for v in vehicles if v.get("line_id") == lid]
    kinds = [per_vehicle.get(v["entity_id"], "unknown") for v in vs]
    row = {"line_id": lid, "name": line.get("name"), "vehicles": len(vs),
           "free": kinds.count("free_running"), "mixed": kinds.count("mixed"), "costly": kinds.count("costly")}
    rows.append(row)
rows.sort(key=lambda r: (-r["free"], r["name"] or ""))
for r in rows:
    print(f"{str(r['name'])[:15]:<16}{r['vehicles']:>3}{r['free']:>10}{r['mixed']:>5}{r['costly']:>8}")

free_lines = [r for r in rows if r["free"] == r["vehicles"] and r["vehicles"]]
print()
print(f"全部车辆零运行成本的线路 {len(free_lines)} 条：{[r['name'] for r in free_lines]}")
print(f"含零运行成本车辆的线路 {len([r for r in rows if r['free']])} 条：{[r['name'] for r in rows if r['free']]}")

json.dump({"models": {n: parse(n) for n in model_names}, "per_vehicle": per_vehicle, "lines": rows},
          open(r"E:\workbody\TPF2Mcp\vehicle_cost.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("已写入 vehicle_cost.json")
