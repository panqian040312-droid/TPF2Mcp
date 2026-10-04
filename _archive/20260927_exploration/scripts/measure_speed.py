"""实测游戏速度倍率与采样粒度（用于评估改倍速后的影响）。只读。"""
import json
import time
import urllib.request

STATUS = "http://127.0.0.1:8765/api/status"
LIVE = "http://127.0.0.1:8765/api/live"

prev = None
print("=== 游戏速度 ===")
for i in range(6):
    t = time.time()
    try:
        d = json.loads(urllib.request.urlopen(STATUS, timeout=5).read())
    except Exception as e:  # noqa: BLE001
        print("读取失败", e)
        time.sleep(3)
        continue
    gc = d.get("game_clock") or {}
    sim = d.get("simulation") or {}
    cl = sim.get("clock") or {}
    dl = sim.get("deltas") or {}
    gt = cl.get("game_time")
    parts = [
        "rate=%s" % gc.get("rate"),
        "wall/game=%s" % gc.get("wall_seconds_per_game_second"),
        "mult=%s" % sim.get("speed_multiplier"),
        "game_time=%s" % gt,
        "tick=%s" % cl.get("update_count"),
        "deltas=%s" % dl,
    ]
    if prev:
        dt = t - prev[0]
        dg = (gt - prev[1]) / 1000.0
        parts.append("实测 %.1f 游戏秒 / %.2f 墙上秒 = %.2fx" % (dg, dt, dg / dt))
    prev = (t, gt)
    print("  " + " | ".join(parts))
    time.sleep(3)

print()
print("=== mod 侧采样粒度（live-rail-state 刷新）===")
stamps = []
for i in range(5):
    try:
        d = json.loads(urllib.request.urlopen(LIVE, timeout=5).read())
        stamps.append((time.time(), d.get("sampled_at")))
    except Exception as e:  # noqa: BLE001
        print("读取失败", e)
    time.sleep(2)
for i, (t, s) in enumerate(stamps):
    extra = ""
    if i:
        extra = "  间隔 %.2f 墙上秒" % (t - stamps[i - 1][0])
    print("  sampled_at=%.3f%s" % (s or -1, extra))
