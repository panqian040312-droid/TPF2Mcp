"""读取复兴号模型文件的物理参数，评估"给京广独占的 04_T/05_T 车厢加动力"的加速收益。

背景：
- TPF2 的列车物理参数写在每个车厢 .mdl 顶部的 4 个 Lua 局部变量里：
  trainEnginePower(kW) / trainTractiveEffort(kN) / trainTopSpeed(m/s) / trainWeight(t)
- 整车按编组求和；加速度由 总牵引力/总质量（低速）与 总功率/(质量×速度)（高速）共同限制。
- 京广客运的列车41 是 16 节重联，其中 `TC/MP/04_T.mdl` 与 `TC/MP/05_T.mdl` 各 1 节，
  这两节**只有列车41 用**（全存档核验），且当前 power=0 / tractiveEffort=0（纯拖车）。

用法：python inspect_train_physics.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MOD = Path(r"E:\SteamLibrary\steamapps\workshop\content\1066780\3374213837\res\models\model\vehicle\train\CR400AF_0208")
BRIDGE = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\bridge")
LINE_ID = 224503          # 京广客运
VEHICLE_ID = 159365       # 列车41
LEG_METERS = 5000.0       # 典型站间距离（京广 14.6 km / 3 站）
TARGET_KMH = 200.0        # 统计"0→200 km/h"的加速时间（该线轨道限速 200 km/h 为主）


def physics(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")[:4000]

    def grab(key: str) -> float:
        match = re.search(r"local train" + key + r"\s*=\s*([0-9.eE+\-*/\s]+)", text)
        if not match:
            return 0.0
        expr = match.group(1).split("--")[0].strip()
        try:
            return float(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 - 只含数字与四则运算
        except (SyntaxError, TypeError, ZeroDivisionError):
            return 0.0

    return {
        "power": grab("EnginePower"),
        "traction": grab("TractiveEffort"),
        "top_speed": grab("TopSpeed"),
        "weight": grab("Weight"),
    }


def load_consist(vehicle_id: int) -> list[str]:
    snapshot = json.loads((BRIDGE / "state.json").read_text(encoding="utf-8"))
    for vehicle in snapshot.get("vehicles", []):
        if vehicle.get("entity_id") != vehicle_id:
            continue
        out = []
        for part in vehicle.get("consist_parts") or []:
            model = part.get("model_name") or ""
            if "CR400AF_0208/" in model:
                out.append(model.split("CR400AF_0208/", 1)[1])
        return out
    return []


def totals(consist: list[str], boost_cars: tuple[str, ...] = (), trailer_power: float = 0.0,
           trailer_traction: float = 0.0) -> dict:
    """按编组求和；只给 boost_cars 里列出的车厢加动力（避免误伤 JY 共用的拖车）。"""
    power = traction = weight = 0.0
    for rel in consist:
        data = physics(MOD / rel)
        if rel in boost_cars:
            power += trailer_power
            traction += trailer_traction
        else:
            power += data["power"]
            traction += data["traction"]
        weight += data["weight"]
    return {"power": power, "traction": traction, "weight": weight}


def accel_seconds(power_kw: float, traction_kn: float, mass_t: float, target_ms: float) -> float:
    """用 牵引力上限 / 功率上限 包络积分 0→target 的加速时间（忽略阻力）。"""
    mass_kg = mass_t * 1000.0
    force_kn = traction_kn
    power_w = power_kw * 1000.0
    steps = 2000
    dv = target_ms / steps
    total = 0.0
    for i in range(steps):
        v = dv * (i + 0.5)
        available = min(force_kn * 1000.0, power_w / max(v, 0.1))
        accel = available / mass_kg
        if accel <= 0:
            return float("inf")
        total += dv / accel
    return total


def main() -> None:
    consist = load_consist(VEHICLE_ID)
    if not consist:
        print("没读到列车41 的编组")
        return
    print(f"列车41 编组：{len(consist)} 节")
    print()
    print("各车厢物理参数：")
    print(f"{'车厢':<26}{'功率kW':>9}{'牵引kN':>9}{'顶速km/h':>11}{'质量t':>9}")
    for rel in dict.fromkeys(consist):
        data = physics(MOD / rel)
        print(f"{rel:<26}{data['power']:>9.0f}{data['traction']:>9.1f}"
              f"{data['top_speed'] * 3.6:>11.1f}{data['weight']:>9.2f}")

    trailer = [rel for rel in dict.fromkeys(consist)
               if physics(MOD / rel)["power"] == 0 and physics(MOD / rel)["traction"] == 0]
    print()
    print(f"零动力车厢（纯拖车）：{trailer}  数量 {sum(1 for r in consist if r in trailer)} 节")

    base = totals(consist)
    print()
    print(f"{'方案':<40}{'总功率kW':>10}{'总牵引kN':>10}{'总质量t':>9}{'推重比kW/t':>11}{'a0 m/s²':>9}{'0→200s':>9}")
    print("-" * 102)

    def line(label: str, boost: tuple[str, ...], power: float, traction: float) -> float:
        data = totals(consist, boost, power, traction) if boost else base
        mass = data["weight"]
        t200 = accel_seconds(data["power"], data["traction"], mass, TARGET_KMH / 3.6)
        print(f"{label:<40}{data['power']:>10.0f}{data['traction']:>10.1f}{mass:>9.1f}"
              f"{data['power'] / mass:>11.2f}{data['traction'] / mass:>9.3f}{t200:>9.1f}")
        return t200

    EXCLUSIVE = tuple(rel for rel in ("TC/MP/04_T.mdl", "TC/MP/05_T.mdl"))
    n_exclusive = sum(1 for rel in consist if rel in EXCLUSIVE)
    # 基线固定为"出厂状态"：那两节独占车动力=0，与文件当前是否已打补丁无关
    base = totals(consist, EXCLUSIVE, 0.0, 0.0)
    base_t = line("出厂基线（2 节独占车 0 动力）", EXCLUSIVE, 0.0, 0.0)
    results = {"出厂基线": base_t}
    for label, power, traction in (
        ("2 节独占车 = 半动力 (1250kW/75.5kN)", 1250, 75.5),
        ("2 节独占车 = 标准动力车 (2500kW/151kN) ★已应用", 2500, 151.0),
        ("2 节独占车 = 1.5 倍动力 (3750kW/226.5kN)", 3750, 226.5),
    ):
        results[label] = line(label, EXCLUSIVE, power, traction)

    print()
    print(f"★ 只改这 {n_exclusive} 节（京广独占，全存档仅列车41 使用）→ 其他线路（含 JY客运）完全不受影响")
    print()
    print("每停一站节省（0→200 km/h 段）：")
    for label, value in results.items():
        if label == "出厂基线":
            continue
        print(f"  {label:<38} 省 {base_t - value:>5.1f} 秒/次加速")
    std = results["2 节独占车 = 标准动力车 (2500kW/151kN) ★已应用"]
    print()
    print(f"京广客运每循环 3 个停站 → 约省 {(base_t - std) * 3:.0f} 游戏秒（标准动力方案）")
    print(f"（京广整圈实测约 1,005 游戏秒；站间 {LEG_METERS / 1000:.0f} km，轨道限速 200 km/h 为主）")


if __name__ == "__main__":
    main()
