"""解析铁路车辆模型文件，查找车辆成本（价格/维护费）字段。只读。"""
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
rail_vehicles = [v for v in snap["vehicles"] if v.get("line_id") in rail_ids]

models = {}
for v in rail_vehicles:
    for part in v.get("consist_parts") or []:
        name = str(part.get("model_name") or "").replace("\\", "/")
        if name:
            models.setdefault(name, []).append(v)

roots = [GAME / "res" / "models" / "model"]
for base in (GAME / "mods", WORKSHOP):
    if base.is_dir():
        roots.extend(p / "res" / "models" / "model" for p in base.iterdir() if p.is_dir())
archive = GAME / "res" / "models" / "model.zip"

COST_KEYS = re.compile(r"(cost|price|maintenance|runningCost|operating)", re.I)


def scan(source: str):
    hits = {}
    for key in ("cost", "price", "maintenance"):
        for match in re.finditer(key + r"\s*=", source, re.I):
            snippet = source[max(0, match.start() - 60):match.start() + 160].replace("\n", " ")
            hits.setdefault(key, []).append(snippet)
    return hits


found = {}
for name in sorted(models):
    relative = Path(*name.split("/"))
    source = None
    location = None
    if archive.is_file():
        try:
            with zipfile.ZipFile(archive) as zf:
                source = zf.read("model/" + name)[:40000].decode("utf-8", errors="ignore")
                location = f"{archive}!/model/{name}"
        except (KeyError, OSError, zipfile.BadZipFile):
            pass
    if source is None:
        for root in roots:
            path = root / relative
            if path.is_file():
                try:
                    source = path.read_text(encoding="utf-8", errors="ignore")[:40000]
                except OSError:
                    continue
                location = str(path)
                break
    found[name] = (location, scan(source) if source else None)

print("=== 模型解析结果 ===")
for name in sorted(found):
    location, hits = found[name]
    status = "未找到" if location is None else ("有 cost 字段" if hits and hits.get("cost") else ("有二类字段" if hits else "无 cost 字段"))
    print(f"{name:<45} {status:<12} {location or ''}")

with_cost = [n for n, (_, h) in found.items() if h and h.get("cost")]
print()
print(f"共 {len(found)} 个模型；解析到文件的 {sum(1 for l, _ in found.values() if l)} 个；命中 cost 字段的 {len(with_cost)} 个")
for name in with_cost[:4]:
    print()
    print("---", name)
    for snippet in found[name][1]["cost"][:3]:
        print("   ", snippet[:220])

Path(r"E:\workbody\TPF2Mcp\vehicle_cost_probe.txt").write_text(
    "\n".join(f"{n}\t{found[n][0]}\t{json.dumps(found[n][1], ensure_ascii=False)}" for n in sorted(found)),
    encoding="utf-8",
)
