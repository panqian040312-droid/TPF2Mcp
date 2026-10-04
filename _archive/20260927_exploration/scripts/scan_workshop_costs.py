"""全工坊铁路车辆模型扫描：解析 cost/maintenance（含变量定义），找出零成本车型。只读。"""
import json
import re
from pathlib import Path

GAME = Path(r"E:\SteamLibrary\steamapps\common\Transport Fever 2")
WORKSHOP = GAME.parent.parent / "workshop" / "content" / "1066780"

COST = re.compile(r"cost\s*=\s*\{([^}]*)\}", re.I)
MAINT = re.compile(r"maintenance\s*=\s*\{([^}]*)\}", re.I)
PAIR = re.compile(r"([A-Za-z_]\w*)\s*=\s*(-?[0-9.]+(?:[eE][-+]?\d+)?)")
LOCAL = re.compile(r"(?:local\s+)?([A-Za-z_]\w*)\s*=\s*(-?[0-9.]+(?:[eE][-+]?\d+)?)")


def to_number(token: str, variables: dict):
    if token is None:
        return None
    try:
        return float(token)
    except ValueError:
        return variables.get(token)


def parse(source: str):
    variables = {name: float(value) for name, value in LOCAL.findall(source)}
    out = {}
    for key, pattern in (("cost", COST), ("maintenance", MAINT)):
        match = pattern.search(source)
        if not match:
            continue
        fields = {}
        for name, token in PAIR.findall(match.group(1)):
            fields[name] = to_number(token, variables)
        out[key] = fields
    return out, variables


results = []
mods = [p for p in WORKSHOP.iterdir() if p.is_dir()]
for mod in mods:
    root = mod / "res" / "models" / "model" / "vehicle"
    if not root.is_dir():
        continue
    for path in root.rglob("*.mdl"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if len(text) > 400000:
            text = text[:400000]
        blocks, variables = parse(text)
        cost = blocks.get("cost") or {}
        maint = blocks.get("maintenance") or {}
        price = cost.get("price")
        scale = cost.get("priceScale")
        run_costs = maint.get("runningCosts")
        run_scale = maint.get("runningCostScale")
        free_buy = (price == 0) or (scale == 0)
        free_run = (run_costs == 0) or (run_scale == 0)
        if free_buy or free_run or (run_scale is not None and 0 < run_scale < 1):
            results.append({
                "mod": mod.name,
                "model": str(path.relative_to(mod)).replace("\\", "/"),
                "price": price, "priceScale": scale,
                "runningCosts": run_costs, "runningCostScale": run_scale,
                "lifespan": maint.get("lifespan"),
                "free_buy": free_buy, "free_run": free_run,
            })

print(f"扫描了 {len(mods)} 个 Mod")
print(f"命中（免费或打折）的模型 {len(results)} 个")
print()
for row in sorted(results, key=lambda r: (r["mod"], r["model"])):
    print(f"mod {row['mod']:<12} price={str(row['price']):>12} pScale={str(row['priceScale']):>6} "
          f"runC={str(row['runningCosts']):>12} runScale={str(row['runningCostScale']):>6}  "
          f"{'免费运行' if row['free_run'] else ('免费购置' if row['free_buy'] else '打折')}  {row['model']}")

json.dump(results, open(r"E:\workbody\TPF2Mcp\workshop_free_vehicles.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print()
print("已写入 workshop_free_vehicles.json")
