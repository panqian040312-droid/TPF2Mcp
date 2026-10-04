"""从解压后的存档里，把「车站 → 已装模块」归位，并按 moreCapacity 算出每个车站的承载人数。

思路：
1. 存档是属性树序列化，车站建造实体的模块以 `name = <路径>.module` 的形式出现；
2. 车站名（如「广州北站」）也在同一段里出现；
3. 用**空间邻近**把模块串归给最近的车站名（同一个建造实体在文件里是连续的一段）。

车站承载人数 = 该站模块 moreCapacity.passenger 之和（游戏源码 modulesutil.lua:19）。

用法：python save_station_modules.py [车站名 ...]
"""
from __future__ import annotations

import json
import mmap
import re
import sys
from bisect import bisect_left
from collections import Counter
from pathlib import Path

SAVE = Path(r"E:\workbody\TPF2Mcp\_save\2.sav.raw")
BRIDGE = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge")
WORKSPACE = Path(r"E:\workbody\TPF2Mcp")
WINDOW = 30_000        # 车站名 ±30KB 视为同一段落

# 模块容量表：来自 station_modules.py 的解析结果（原版 + UST mod）
CAPACITY = {
    "main_building_3_era_c": 200, "main_building_3_era_b": 150, "main_building_3_era_a": 100,
    "main_building_2_era_c": 50, "main_building_2_era_b": 45, "main_building_2_era_a": 40,
    "main_building_1_era_c": 30, "main_building_1_era_b": 25, "main_building_1_era_a": 20,
    "side_building_3_era_c": 150, "side_building_3_era_b": 100, "side_building_3_era_a": 80,
    "side_building_2_era_c": 40, "side_building_2_era_b": 35, "side_building_2_era_a": 30,
    "side_building_1_era_c": 20, "side_building_1_era_b": 15, "side_building_1_era_a": 10,
    # UST mod（地下站）：按文件名 + 尺寸
    "main_building_3": 200, "main_building_2": 50, "main_building_1": 30,
    "side_building_3": 150, "side_building_2": 40, "side_building_1": 20,
    "main_building_40": 150, "main_building_20": 40, "main_building_10": 20,
}


def module_capacity(path: str) -> int:
    stem = path.rsplit("/", 1)[-1].replace(".module", "")
    if stem in CAPACITY:
        return CAPACITY[stem]
    return 0


def main() -> None:
    if not SAVE.exists():
        print("存档未解压（_save/2.sav.raw 不存在）")
        return
    snap = json.loads((BRIDGE / "state.json").read_text(encoding="utf-8"))
    net = json.loads((BRIDGE / "rail-network.json").read_text(encoding="utf-8"))
    station_names = sorted({s["name"] for s in net["stations"] if s.get("name")}, key=len, reverse=True)
    wanted = set(sys.argv[1:])

    with open(SAVE, "rb") as handle:
        mm = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        # 1) 所有模块路径
        modules: list[tuple[int, str]] = []
        for m in re.finditer(rb"([\w/]*(?:main_building|side_building)[\w/]*\.module)", mm):
            modules.append((m.start(), m.group(1).decode("ascii", "ignore")))
        print(f"存档中出现的建筑模块条目：{len(modules)}")
        # 2) 所有车站名的位置
        name_positions: list[tuple[int, str]] = []
        for name in station_names:
            raw = name.encode("utf-8")
            start = mm.find(raw)
            while start != -1:
                name_positions.append((start, name))
                start = mm.find(raw, start + 1)
        name_positions.sort()
        print(f"车站名出现次数：{len(name_positions)}")
        mm.close()

    if not name_positions:
        print("没找到车站名，无法归位")
        return

    offsets = [p for p, _ in name_positions]
    per_station: dict[str, Counter] = {}
    for pos, path in modules:
        i = bisect_left(offsets, pos)
        best = None
        for cand in (i - 1, i):
            if 0 <= cand < len(offsets):
                delta = abs(offsets[cand] - pos)
                if delta <= WINDOW and (best is None or delta < best[0]):
                    best = (delta, name_positions[cand][1])
        if best:
            per_station.setdefault(best[1], Counter())[path] += 1

    rows = []
    for name, counter in per_station.items():
        capacity = sum(module_capacity(p) * n for p, n in counter.items())
        rows.append((capacity, name, counter))
    rows.sort(reverse=True)

    print()
    print(f"{'车站':<18}{'推算承载人数':>12}{'建筑模块明细'}")
    print("-" * 96)
    for capacity, name, counter in rows:
        if wanted and name not in wanted:
            continue
        detail = "、".join(f"{p.rsplit('/',1)[-1].replace('.module','')}×{n}" for p, n in counter.most_common(6))
        print(f"{name:<18}{capacity:>12}{detail}")

    print()
    print(f"共归位 {len(rows)} 个车站；其中承载人数 >0 的 {sum(1 for c, _, _ in rows if c > 0)} 个")
    top = rows[:10]
    print("承载人数最高的 10 个车站：")
    for capacity, name, _ in top:
        print(f"   {name:<18}{capacity:>6} 人")


if __name__ == "__main__":
    main()
