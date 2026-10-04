"""为「新建 1 条货运轨 + 路径牌方向分离」方案，算出每条货运线各段的走向与路径牌插入位置。

走廊链：Omsk(0) → Zhengzhou(3.07) → Kolkata(5.64) → Foshan(7.91)，单位 km。
规则：里程增大的段 = 朝 Foshan 方向 → 走 A 轨；里程减小的段 = 朝 Omsk 方向 → 走新轨 C。
只读。
"""
import json
import collections

S = r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge"
net = json.load(open(S + r"\rail-network.json", encoding="utf-8"))

MILEAGE = {"Omsk": 0.0, "Zhengzhou": 3.07, "Kolkata": 5.64, "Foshan": 7.91}
stn = {s["entity_id"]: s for s in net["stations"]}

print("走廊链（沿里程）：Omsk 0.00 → Zhengzhou 3.07 → Kolkata 5.64 → Foshan 7.91 km")
print("规则：里程增大的段 → A 轨（现有货运轨，改作全东行）；里程减小的段 → C 轨（新建，全西行）")
print()

total_marks = 0
skipped_passenger = []
for L in sorted(net["lines"], key=lambda x: x["name"]):
    groups = [stn.get(st["station_group_id"]) for st in L["stops"]]
    seq = [s["name"] if s else "?" for s in groups]
    # 判断客/货运线：多数站点是货运站组 -> 货运线
    kinds = [("货运" if s["terminals"][0].get("cargo") else "客运") for s in groups if s]
    if not kinds:
        continue
    if kinds.count("货运") < kinds.count("客运"):
        skipped_passenger.append(L["name"])
        continue
    # 只保留走廊内的段
    segs = []
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        if a in MILEAGE and b in MILEAGE and a != b:
            d = MILEAGE[b] - MILEAGE[a]
            segs.append((i, a, b, d))
    if not segs:
        continue
    print(f"=== {L['name']} （站序：{' → '.join(seq)}）===")
    marks = 0
    for i, a, b, d in segs:
        if d > 0:
            track, tag = "A 轨（东行）", "朝 Foshan"
        else:
            track, tag = "C 轨（西行，新建）", "朝 Omsk"
        print(f"  第{i+1}段  {a} → {b}  ({tag}, {abs(d):.2f} km)  → 在【{track}】上放路径牌")
        marks += 1
    total_marks += marks
    print(f"  小计：{marks} 个路径牌")
    print()
print(f"合计需要路径牌：约 {total_marks} 个（每条线 1–3 个）")
print()
print("（客运线另行处理，本次跳过：%s）" % "、".join(skipped_passenger))
print("提示：路径牌要放在该段的轨道上、且位于两端车站之间；放一个即可锁定整段走向。")
print("     若发现线路仍走错轨道，说明那个路径牌离岔口太近、最短路绕过了它 —— 从岔口往目标轨道再补一个。")
