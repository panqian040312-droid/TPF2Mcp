"""走廊运行策略仿真：在不改游戏的前提下，用修改过的快照副本重跑运行图规划，比较冲突数。"""
import copy
import json
import subprocess
import sys
from pathlib import Path

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")
REPO = Path(r"E:\workbody\TPF2Mcp")
GAME = r"E:\SteamLibrary\steamapps\common\Transport Fever 2"
PY = r"C:\Users\RaiG\.workbuddy\binaries\python\versions\3.13.12\python.exe"

snapshot = json.loads((MOD / "bridge" / "state.json").read_text(encoding="utf-8"))
manifest = MOD / "bridge" / "rail-network.json"

CORRIDOR = {"京广客运": None, "JY客运": None, "JI线路": None}
for line in snapshot["lines"]:
    if line["name"] in CORRIDOR:
        CORRIDOR[line["name"]] = int(line["entity_id"])
jingguang = CORRIDOR["京广客运"]

variants = {}

# V0 现状
variants["V0_现状"] = copy.deepcopy(snapshot)

# V1 京广客运 16 节 → 两列 8 节（车数不变，只拆编组）
v1 = copy.deepcopy(snapshot)
vehicles = v1["vehicles"]
target = next(v for v in vehicles if v.get("line_id") == jingguang)
parts = target.get("consist_parts") or []
if len(parts) >= 8:
    half = len(parts) // 2
    first = copy.deepcopy(target)
    second = copy.deepcopy(target)
    first["consist_parts"] = parts[:half]
    second["consist_parts"] = parts[half:]
    second["entity_id"] = 900000001
    second["name"] = target["name"] + "-B"
    first["entity_id"] = 900000002
    first["name"] = target["name"] + "-A"
    cap_total = target.get("capacity_total") or 0
    first["capacity_total"] = cap_total // 2
    second["capacity_total"] = cap_total - cap_total // 2
    idx = vehicles.index(target)
    vehicles[idx:idx + 1] = [first, second]
variants["V1_京广拆两列8节"] = v1

# V2 在 V1 基础上 JY客运 减少一列车（4 → 3）
v2 = copy.deepcopy(v1)
jy = CORRIDOR["JY客运"]
jy_vehicles = [v for v in v2["vehicles"] if v.get("line_id") == jy]
if len(jy_vehicles) > 3:
    drop = jy_vehicles[-1]
    v2["vehicles"] = [v for v in v2["vehicles"] if v.get("entity_id") != drop.get("entity_id")]
variants["V2_拆编组+JY减一列"] = v2

results = {}
for label, snap in variants.items():
    path = REPO / f"sim_snapshot_{label.split('_')[0]}.json"
    path.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    out = REPO / f"sim_plan_{label.split('_')[0]}.json"
    command = [
        sys.executable, str(REPO / "tools" / "build-line-timetable-plan.py"),
        "--snapshot", str(path),
        "--manifest", str(manifest),
        "--work-log-database", str(REPO / "_nope.sqlite3"),
        "--demand-database", str(REPO / "_nope2.sqlite3"),
        "--game-directory", GAME,
        "--output", str(out),
    ]
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if not out.is_file():
        print(label, "规划失败:", (proc.stderr or proc.stdout or "")[-300:])
        continue
    result = json.loads(out.read_text(encoding="utf-8"))
    corridor_lines = {}
    for item in result["lines"]:
        if item["line_name"] in CORRIDOR:
            corridor_lines[item["line_name"]] = {
                "车数": item["vehicle_count"],
                "班次s": round(item["headway_seconds"], 1),
                "周期s": round(item["cycle_seconds"], 1),
                "相位": [round(x, 1) for x in item["phase_offsets_seconds"]],
                "平移": item["global_phase_shift_seconds"],
                "冲突前": item["station_conflicts_before_shift"],
                "冲突后": item["station_conflicts_after_shift"],
                "编组长m": (item["stops"][0].get("platform_fit") or {}).get("train_length_m"),
            }
    results[label] = {
        "全局冲突": result["global_conflict_plan"],
        "走廊线路": corridor_lines,
    }

print("=== 仿真对比（跑修改后的快照副本，未改动游戏）===")
for label, data in results.items():
    g = data["全局冲突"]
    print()
    print(f"【{label}】全局冲突：相位优化前 {g['conflicts_before_shift']} → 后 {g['conflicts_after_shift']}"
          f"（消除 {g['conflicts_removed']}，视窗 {g['horizon_seconds']}s）")
    for name, info in data["走廊线路"].items():
        print(f"   {name:<8} {info['车数']} 车 ｜ 班次 {info['班次s']:>7.1f}s ｜ 周期 {info['周期s']:>7.1f}s ｜ "
              f"平移 {info['平移']:>5.0f}s ｜ 冲突 {info['冲突前']} → {info['冲突后']} ｜ 编组 {info['编组长m']} m")

Path(REPO / "corridor_simulation.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("已写入 corridor_simulation.json")
