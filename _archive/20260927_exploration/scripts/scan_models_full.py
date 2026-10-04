"""全量扫描铁路车辆模型的成本定义（不截断文件），重点看复兴号/和谐号。只读。"""
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
vehicles = [v for v in snap["vehicles"] if v.get("line_id") in rail_ids]
line_names = {int(l["entity_id"]): l["name"] for l in snap["lines"] if int(l["entity_id"]) in rail_ids}

roots = [GAME / "res" / "models" / "model"]
for base in (GAME / "mods", WORKSHOP):
    if base.is_dir():
        roots.extend(p / "res" / "models" / "model" for p in base.iterdir() if p.is_dir())
archive = GAME / "res" / "models" / "model.zip"

BLOCK = {
    "cost": re.compile(r"cost\s*=\s*\{([^}]*)\}", re.I),
    "maintenance": re.compile(r"maintenance\s*=\s*\{([^}]*)\}", re.I),
    "emission": re.compile(r"emission\s*=\s*\{([^}]*)\}", re.I),
}
NUMBER = re.compile(r"([A-Za-z]+)\s*=\s*(-?[0-9.]+)")


def read_full(name: str):
    relative = Path(*name.split("/"))
    if archive.is_file():
        try:
            with zipfile.ZipFile(archive) as zf:
                return zf.read("model/" + name).decode("utf-8", errors="ignore"), str(archive)
        except (KeyError, OSError, zipfile.BadZipFile):
            pass
    for root in roots:
        path = root / relative
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="ignore"), str(path)
            except OSError:
                continue
    return None, None


def blocks(source: str) -> dict:
    out = {}
    for key, pattern in BLOCK.items():
        match = pattern.search(source)
        if not match:
            continue
        values = {}
        for field, value in NUMBER.findall(match.group(1)):
            values[field] = float(value)
        if values:
            out[key] = values
    return out


names = sorted({str(p.get("model_name") or "") for v in vehicles
                for p in (v.get("consist_parts") or []) if p.get("model_name")})

detail = {}
for name in names:
    source, location = read_full(name)
    detail[name] = {"location": location, "blocks": blocks(source) if source else None,
                    "size": len(source) if source else 0}

print("=== 全部铁路模型：成本相关块（完整文件扫描）===")
for name in names:
    info = detail[name]
    b = info["blocks"] or {}
    cost = b.get("cost", {})
    maint = b.get("maintenance", {})
    print(f"{name[:52]:<53} size={info['size']:>7}  price={cost.get('price', '—')} "
          f"pScale={cost.get('priceScale', '—')} runC={maint.get('runningCosts', '—')} "
          f"runScale={maint.get('runningCostScale', '—')} 寿命={maint.get('lifespan', '—')}")

print()
print("=== 分类型汇总 ===")
buckets = {}
for name in names:
    b = detail[name]["blocks"] or {}
    cost = b.get("cost", {})
    maint = b.get("maintenance", {})
    price = cost.get("price")
    scale = cost.get("priceScale")
    run_cost = maint.get("runningCosts")
    run_scale = maint.get("runningCostScale")
    if price is None and run_cost is None:
        key = "无 cost 与 maintenance 块"
    elif (price == 0 or scale == 0) and (run_cost == 0 or run_scale == 0):
        key = "购置与运行均免费"
    elif price == 0 or scale == 0:
        key = "仅购置免费"
    elif run_cost == 0 or run_scale == 0:
        key = "仅运行免费"
    elif run_scale is not None and 0 < run_scale < 1:
        key = f"运行成本打折({run_scale})"
    else:
        key = "自动定价（非免费）"
    buckets.setdefault(key, []).append(name)
for key, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    print(f"{key}: {len(items)}")
    if "免费" in key or "打折" in key:
        for n in items:
            print("   ", n)

json.dump(detail, open(r"E:\workbody\TPF2Mcp\vehicle_models_full.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print()
print("已写入 vehicle_models_full.json")
