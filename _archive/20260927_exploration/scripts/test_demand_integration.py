"""离线自检：验证 serve-rail-map.py 新增的客流逻辑（不启动服务、不碰游戏）。"""
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"E:\workbody\TPF2Mcp")
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")

spec = importlib.util.spec_from_file_location("serve_rail_map", ROOT / "tools" / "serve-rail-map.py")
module = importlib.util.module_from_spec(spec)
sys.modules["serve_rail_map"] = module
spec.loader.exec_module(module)

app = module.RailMapState.__new__(module.RailMapState)   # 跳过 __init__，避免打开 sqlite
app.bridge = MOD / "bridge"
app.root = MOD / "ui" / "rail-map"
app.demand_cache = {}
app.demand_lock = threading.Lock()
app.demand_sweep = {"running": False, "done": 0, "total": 0, "errors": []}
app.demand_last_persist = 0.0

# 1) 容量表（读 state.json）
fleet = app._fleet_capacity()
sample = {k: v for k, v in fleet.items() if k in (224503, 98983, 90194)}
print("== _fleet_capacity 抽样 ==")
for line_id, cap in sample.items():
    print(f"  line {line_id}: 座位 {cap['seats']} / 货容 {cap['cargo']} / 车辆 {len(cap['vehicles'])}")

# 2) 铁路线清单
line_ids = app._rail_line_ids()
print(f"\n== _rail_line_ids: {len(line_ids)} 条 ==")

# 3) 压缩函数（用引擎真实返回结构做样本）
raw = {
    "line_id": 224503, "source_status": "ENGINE_COMPONENT_CLASSIFIED",
    "passengers": {"onboard": 326, "waiting": 1043, "total_for_line": 1505,
                   "average_waiting_seconds": 397.86, "journey_unknown": 136, "truncated": False,
                   "by_journey": [{"line_stop_0": 0, "line_stop_1": 1, "onboard": 0, "waiting": 294, "total": 294}],
                   "vehicles": {"159365": 326}},
    "cargo": {"onboard": 0, "waiting": 0, "total_for_line": 0, "by_cargo": []},
}
compact = app._compact_demand(raw, 224503)
print("\n== _compact_demand ==")
print(" ", json.dumps(compact, ensure_ascii=False)[:260])

app.demand_cache[224503] = compact
live = app.demand_live()
entry = live["lines"][224503]
print("\n== demand_live（面板读到的结构）==")
print("  线路:", entry["line_name"], "| 车上:", entry["pax"]["onboard"], "| 候车:", entry["pax"]["waiting"])
print("  座位:", entry["seats"], "| 实载率:", round((entry["load_factor"] or 0) * 100, 1), "%")
print("  单车:", json.dumps(entry["vehicle_load"], ensure_ascii=False))

# 4) 面板会读的字段是否齐全
needed = ["line_name", "pax", "cargo", "cargo_types", "vehicles", "by_journey", "seats",
          "load_factor", "wait_ratio", "vehicle_load", "cargo_capacity", "sampled_at"]
missing = [key for key in needed if key not in entry]
print("\n== 面板字段完整性 ==")
print("  缺失:", missing if missing else "无")

# 5) 预期数值校验
expect_onboard, expect_waiting, expect_seats = 326, 1043, 1294
ok = (entry["pax"]["onboard"] == expect_onboard and entry["pax"]["waiting"] == expect_waiting
      and entry["seats"] == expect_seats)
print("  数值断言(326/1043/1294):", "通过" if ok else "不通过 -> " + str((entry["pax"]["onboard"], entry["pax"]["waiting"], entry["seats"])))
print("  实载率断言(≈25%):", "通过" if abs((entry["load_factor"] or 0) - 326 / 1294) < 1e-9 else "不通过")

print("\n== _bridge_ready（游戏在跑应为 True）==")
print("  ", app._bridge_ready())
