"""采样实时数据，统计每辆车的轨道边/闭塞区间占用，用于评估干线车流与拥堵。只读。"""
import json
import time
import urllib.request
from collections import defaultdict

OUT = r"E:\workbody\TPF2Mcp\traffic_samples.json"
DURATION = 150
INTERVAL = 3

edge_lines = defaultdict(set)      # edge_id -> {line_id}
edge_samples = defaultdict(int)    # edge_id -> 被车占用的采样次数
block_samples = defaultdict(int)   # block_id -> 占用采样次数
block_lines = defaultdict(set)     # block_id -> {line_id}
line_vehicles = defaultdict(set)
samples = 0
sim = None
counts = None

start = time.time()
while time.time() - start < DURATION:
    try:
        raw = urllib.request.urlopen("http://127.0.0.1:8765/api/live", timeout=15).read()
        data = json.loads(raw)
    except Exception as error:
        print("采样失败:", error)
        time.sleep(INTERVAL)
        continue
    samples += 1
    sim = data.get("simulation")
    counts = data.get("counts")
    for vehicle in data.get("vehicles") or []:
        line_id = vehicle.get("line_id")
        edge_id = vehicle.get("edge_id")
        block_id = vehicle.get("block_id")
        line_vehicles[line_id].add(vehicle.get("entity_id"))
        if edge_id is not None:
            edge_lines[edge_id].add(line_id)
            edge_samples[edge_id] += 1
        if block_id is not None:
            block_lines[block_id].add(line_id)
            block_samples[block_id] += 1
    print(f"样本 {samples}: 车辆 {len(data.get('vehicles') or [])}, 边 {len(edge_lines)}, 区间 {len(block_lines)}")
    time.sleep(INTERVAL)

payload = {
    "samples": samples,
    "duration_seconds": round(time.time() - start, 1),
    "interval_seconds": INTERVAL,
    "counts": counts,
    "simulation_status": (sim or {}).get("status"),
    "edge_lines": {str(k): sorted(x for x in v if x is not None) for k, v in edge_lines.items()},
    "edge_samples": {str(k): v for k, v in edge_samples.items()},
    "block_lines": {str(k): sorted(x for x in v if x is not None) for k, v in block_lines.items()},
    "block_samples": {str(k): v for k, v in block_samples.items()},
    "line_vehicles": {str(k): len(v) for k, v in line_vehicles.items()},
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False)
print("已写入", OUT, "| 采样", samples, "次 |", payload["duration_seconds"], "秒")
print("覆盖轨道边", len(edge_lines), "| 覆盖闭塞区间", len(block_lines), "| 涉及线路", len(line_vehicles))
