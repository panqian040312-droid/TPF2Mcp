"""解析本存档铁路车辆的模型成本（支持 Lua 变量），并对复兴号/和谐号逐型号核对。只读。"""
import json
import re
from pathlib import Path

GAME = Path(r"E:\SteamLibrary\steamapps\common\Transport Fever 2")
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
WORKSHOP = GAME.parent.parent / "workshop" / "content" / "1066780"

snap = json.loads((MOD / "bridge" / "state.json").read_text(encoding="utf-8"))
net = json.loads((MOD / "bridge" / "rail-network.json").read_text(encoding="utf-8"))
rail_ids = {int(l["entity_id"]) for l in net["lines"]}
line_names = {int(l["entity_id"]): l["name"] for l in snap["lines"] if int(l["entity_id"]) in rail_ids}
vehicles = [v for v in snap["vehicles"] if v.get("line_id") in rail_ids]

roots = [GAME / "res" / "models" / "model"]
for base in (GAME / "mods", WORKSHOP):
    if base.is_dir():
        roots.extend(p / "res" / "models" / "model" for p in base.iterdir() if p.is_dir())

NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
COST = re.compile(r"cost\s*=\s*\{([^}]*)\}", re.I)
MAINT = re.compile(r"maintenance\s*=\s*\{([^}]*)\}", re.I)
FIELD = re.compile(r"([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*|" + NUMBER + r")")
ASSIGN = re.compile(r"([A-Za-z_]\w*)\s*=\s*(" + NUMBER + r")")


def locate(name: str):
    relative = Path(*name.split("/"))
    for root in roots:
        path = root / relative
        if path.is_file():
            return path
    return None


def parse(path: Path):
    source = path.read_text(encoding="utf-8", errors="ignore")
    variables = {}
    for key, value in ASSIGN.findall(source):
        try:
            variables[key] = float(value)
        except ValueError:
            pass
    out = {"variables": variables}
    for key, pattern in (("cost", COST), ("maintenance", MAINT)):
        match = pattern.search(source)
        if not match:
            continue
        fields = {}
        for field, token in FIELD.findall(match.group(1)):
            try:
                fields[field] = float(token)
            except ValueError:
                fields[field] = variables.get(token, f"<{token}?>")
        out[key] = fields
    return out


model_lines = {}
for v in vehicles:
    for part in v.get("consist_parts") or []:
        model_lines.setdefault(str(part.get("model_name") or ""), set()).add(line_names[v["line_id"]])

names = sorted(model_lines)
parsed = {}
for name in names:
    path = locate(name)
    parsed[name] = parse(path) if path else {"missing": True}

print("=== 抽检（校验解析正确性）===")
for probe in ("vehicle/train/l3/Bw.mdl", "vehicle/train/CR400BFC/01.mdl",
              "vehicle/train/CR400AF_0208/MC/MP/02.mdl", "vehicle/train/CR200JDL.mdl"):
    info = parsed.get(probe)
    if info:
        print(f"  {probe}: cost={info.get('cost')} maintenance={info.get('maintenance')}")

print()
print("=== 复兴号 / 和谐号 / 机车：逐型号成本 ===")
print(f"{'模型':<46}{'price':>15}{'runCosts':>14}  线路")
for name in names:
    if not re.search(r"CR400|CR200|CRH|HXD|SS\d|ss9g", name):
        continue
    info = parsed[name]
    cost = (info.get("cost") or {})
    maint = (info.get("maintenance") or {})
    lines = "、".join(sorted(line_names for line_names in model_lines[name] if line_names))
    print(f"{name[:45]:<46}{str(cost.get('price')):>15}{str(maint.get('runningCosts')):>14}  {lines}")

print()
print("=== 全部模型成本分类 ===")
buckets = {}
for name in names:
    info = parsed[name]
    cost = (info.get("cost") or {})
    maint = (info.get("maintenance") or {})
    price, scale = cost.get("price"), cost.get("priceScale")
    run_costs, run_scale = maint.get("runningCosts"), maint.get("runningCostScale")
    if isinstance(price, str) or isinstance(run_costs, str):
        key = f"变量未解析: {price if isinstance(price, str) else run_costs}"
    else:
        free_buy = price == 0 or scale == 0
        free_run = run_costs == 0 or run_scale == 0
        if free_buy and free_run:
            key = "购置+运行均免费"
        elif free_buy:
            key = "零购置成本"
        elif free_run:
            key = "零运行成本"
        elif run_scale is not None and 0 < run_scale < 1:
            key = f"运行成本打折({run_scale})"
        elif price is None and run_costs is None:
            key = "无成本字段（继承默认）"
        else:
            key = "正常计费（字面值）"
    buckets.setdefault(key, []).append(name)
for key, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    print(f"  {key}: {len(items)} 个模型")
    if "免费" in key or "打折" in key or "未解析" in key:
        for name in items:
            print("     ", name)

json.dump({n: parsed[n] for n in names}, open(
    r"E:\workbody\TPF2Mcp\vehicle_cost_resolved.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print()
print("已写入 vehicle_cost_resolved.json")
