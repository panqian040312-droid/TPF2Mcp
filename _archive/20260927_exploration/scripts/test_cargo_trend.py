"""校验 _cargo_trend：货运线判据必须是「队列持续增长 + 从不取货」，不能退化成实载率判据。

用法：python test_cargo_trend.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")


def load_module():
    spec = importlib.util.spec_from_file_location("srm", WORK / "tools" / "serve-rail-map.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["srm"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    mod = load_module()
    trend = mod.RailMapState._cargo_trend
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        checks.append((label, ok, f"得到 {got!r}，期望 {want!r}"))

    # 1) 空历史
    check("无观测 → observations=0", trend([]).get("observations"), 0)

    # 2) 队列稳定波动 + 车一直在取货 → 不算问题
    stable = [{"game_s": 100 * i, "waiting": w, "onboard": o} for i, (w, o) in enumerate(
        [(300, 120), (280, 0), (310, 0), (290, 140), (305, 0)])]
    t = trend(stable)
    check("稳定+在取货 → rising=False", t["rising"], False)
    check("稳定+在取货 → suspect_stuck=False", t["suspect_stuck"], False)
    check("稳定+在取货 → ever_onboard=True", t["ever_onboard"], True)

    # 3) 候运大幅上涨，但车确实在取货 → 仍不算「运不走」
    rising_but_served = [{"game_s": i * 100, "waiting": 100 + 200 * i, "onboard": (150 if i == 2 else 0)}
                         for i in range(5)]
    t = trend(rising_but_served)
    check("上涨但在取货 → rising=True", t["rising"], True)
    check("上涨但在取货 → suspect_stuck=False", t["suspect_stuck"], False)

    # 4) 队列暴涨且从未取货，样本 ≥3 → 判为可疑
    stuck = [{"game_s": i * 100, "waiting": 100 + 150 * i, "onboard": 0} for i in range(4)]
    t = trend(stuck)
    check("暴涨+从不取货 → rising=True", t["rising"], True)
    check("暴涨+从不取货 → suspect_stuck=True", t["suspect_stuck"], True)

    # 5) 只有 2 次观测，即使暴涨也不下结论（样本不足）
    few = [{"game_s": 0, "waiting": 100, "onboard": 0}, {"game_s": 100, "waiting": 400, "onboard": 0}]
    check("仅 2 次观测 → 不下结论", trend(few)["suspect_stuck"], False)

    # 6) 小幅上升（<20% 且 <20 件）→ 不报
    mild = [{"game_s": i * 100, "waiting": 200 + 3 * i, "onboard": 0} for i in range(5)]
    check("小幅波动 → rising=False", trend(mild)["rising"], False)

    # 7) 真实样本：用户指出的 6 条货运线，用两轮实测值喂进去，都不该判为「运不走」
    real = {}
    try:
        first = json.loads((WORK / "_dl.json").read_text(encoding="utf-8"))["lines"]
        second = json.loads((WORK / "_dl2.json").read_text(encoding="utf-8"))["lines"]
        for key, entry in second.items():
            name = entry.get("line_name")
            if name in ("广钢原料", "咸阳塑料铁路", "天津燃料", "咸阳矿物空中轨道", "咸阳煤炭空中轨道", "线路 9"):
                w1 = (first.get(key, {}).get("cargo") or {}).get("waiting") or 0
                o1 = (first.get(key, {}).get("cargo") or {}).get("onboard") or 0
                w2 = (entry.get("cargo") or {}).get("waiting") or 0
                o2 = (entry.get("cargo") or {}).get("onboard") or 0
                real[name] = trend([{"game_s": 0, "waiting": w1, "onboard": o1},
                                    {"game_s": 1000, "waiting": w2, "onboard": o2}])
    except (OSError, ValueError, KeyError) as exc:
        checks.append(("真实样本可读", False, f"读取失败：{exc}"))
    for name, t in real.items():
        check(f"真实样本 {name} 不判「运不走」", t["suspect_stuck"], False)

    width = max(len(label) for label, _, _ in checks)
    failed = 0
    print("=" * (width + 34))
    print("货运判据自检（_cargo_trend）")
    print("=" * (width + 34))
    for label, ok, detail in checks:
        mark = "✓" if ok else "✗"
        print(f"{mark} {label:<{width}}  {'' if ok else detail}")
        failed += 0 if ok else 1
    print()
    print(f"真实样本覆盖：{len(real)} 条货运线（{('、'.join(real)) or '无'}）")
    print(f"结论：{'全部通过' if not failed else f'{failed} 项不符'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
