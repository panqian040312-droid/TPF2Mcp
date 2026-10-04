"""验证「列车走哪条轨道由它停哪个车站决定」——对比客运线与货运线所停的站组。只读。"""
import json
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))
names = {l["entity_id"]: l["name"] for l in net["lines"]}
stn = {s["entity_id"]: s for s in net["stations"]}

# 车站名 -> 该名下的所有站组（客/货各一个）
byname = collections.defaultdict(list)
for s in net["stations"]:
    kind = "货运" if s["terminals"][0].get("cargo") else "客运"
    byname[s["name"]].append((s["entity_id"], kind, len(s["terminals"])))

print("=== 同名车站的站组（客/货）===")
for nm in ("Omsk", "Foshan", "Zhengzhou", "Kolkata"):
    print(f"  {nm}: {byname.get(nm)}")
print()

# 各线在 Omsk / Foshan 用的是哪个站组
print("=== 各铁路线在 Omsk 与 Foshan 停的站组 ===")
print(f"{'线路':<20}{'Omsk站组':<22}{'Foshan站组':<22}")
print("-" * 68)
for L in sorted(net["lines"], key=lambda x: x["name"]):
    used = {}
    for st in L["stops"]:
        s = stn.get(st["station_group_id"])
        if s and s["name"] in ("Omsk", "Foshan"):
            kind = "货运" if s["terminals"][0].get("cargo") else "客运"
            used.setdefault(s["name"], set()).add(f"{s['entity_id']}({kind})")
    o = ",".join(sorted(used.get("Omsk", []))) or "-"
    f = ",".join(sorted(used.get("Foshan", []))) or "-"
    print(f"{L['name']:<20}{o:<22}{f:<22}")
print()
print("说明：若『走客运轨的线』都停客运站组、『走货运轨的线』都停货运站组，")
print("      则证明【车站站组决定列车走哪条轨道】—— 这就是不用路径牌的引导手段。")
