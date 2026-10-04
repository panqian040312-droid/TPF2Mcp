"""测「京广客运是否被地铁（JI线路）挡住」：
每 4 秒记录 列车41 的速度/所在闭塞区间，以及同区间内的其他车辆与它们所属线路。
若 列车41 速度掉到 ~50-60 km/h 且同区间/相邻区间有 JI线路 车 → 判为被慢车压着。
"""
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

OUT = Path(r"E:\workbody\TPF2Mcp\_corridor_conflict.csv")
TARGET = 159365          # 列车41（京广客运）
SECONDS = 180
INTERVAL = 4

JI_LINE = 90194
JY_LINE = 98983
KG_LINE = 224503
NAMES = {JI_LINE: "JI(地铁)", JY_LINE: "JY客运", KG_LINE: "京广客运"}

rows = []
handle = OUT.open("w", encoding="utf-8")
handle.write("t,speed,block,n_others,others_in_block\n")
handle.flush()
t0 = time.time()
while time.time() - t0 < SECONDS:
    try:
        data = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/live", timeout=10).read().decode())
        vehicles = data.get("vehicles", [])
        me = next((v for v in vehicles if v.get("entity_id") == TARGET), None)
        if me:
            my_block = me.get("block_id")
            same = [v for v in vehicles if v.get("block_id") == my_block and v.get("entity_id") != TARGET]
            same_desc = ";".join(f"{NAMES.get(v.get('line_id'), v.get('line_id'))}:{v.get('name')}@{v.get('speed_kmh'):.0f}" for v in same)
            row = {
                "t": round(time.time() - t0, 1),
                "speed": me.get("speed_kmh"),
                "block": my_block,
                "others_in_block": same_desc,
                "n_others": len(same),
            }
            rows.append(row)
            handle.write(f"{row['t']},{row['speed']},{row['block']},{row['n_others']},{row['others_in_block']}\n")
            handle.flush()   # 逐帧落盘，进程被杀也保留
    except Exception as exc:  # noqa: BLE001
        print("skip", exc, flush=True)
    time.sleep(INTERVAL)
handle.close()

speeds = [float(r["speed"]) for r in rows if r["speed"] is not None]
print(f"\n样本 {len(rows)} 帧 / {SECONDS} 秒")
if speeds:
    print("速度 平均 %.1f / 最小 %.0f / 最大 %.0f km/h" % (sum(speeds) / len(speeds), min(speeds), max(speeds)))
    slow = [r for r in rows if r["speed"] is not None and float(r["speed"]) < 70]
    print("低速帧(<70km/h): %d / %d" % (len(slow), len(rows)))
    with_others = [r for r in rows if r["n_others"] > 0]
    print("同区间有其它车的帧: %d" % len(with_others))
    print("\n低速且同区间有车（最可疑的组合）:")
    for r in slow:
        if r["n_others"] > 0:
            print("   t=%5.0fs 速度 %5.1f 区间 %s ← %s" % (r["t"], float(r["speed"]), r["block"], r["others_in_block"]))
    print("\n低速但独占区间:")
    for r in slow:
        if r["n_others"] == 0:
            print("   t=%5.0fs 速度 %5.1f 区间 %s" % (r["t"], float(r["speed"]), r["block"]))
    print("\n同区间车辆统计:", Counter(r["others_in_block"] for r in rows if r["n_others"] > 0).most_common(6))
print("写入", OUT)
