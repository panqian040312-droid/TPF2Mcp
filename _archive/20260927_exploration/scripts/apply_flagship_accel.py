"""给京广客运的"标杆车"列车41 单独加动力（只改它独占的两节车厢），带备份与回滚。

原理
----
TPF2 每节车厢的物理参数写在 .mdl 顶部：
    local trainEnginePower    = 0     -- kW
    local trainTractiveEffort = 0     -- kN
    local trainTopSpeed       = ...   -- m/s
    local trainWeight         = 53.475
整车按编组求和，加速度 = 总牵引力 / 总质量（低速段）与 总功率 / (质量×速度)（高速段）共同限制。

为什么能"只改京广"
------------------
列车41（京广，16 节）里 `TC/MP/04_T.mdl` 与 `TC/MP/05_T.mdl` 各 1 节，
全存档核验**只有列车41 使用**这两节，且它们当前 power=0 / tractiveEffort=0（纯拖车）。
其余车厢（MC/MP/02、MC/MP/07 等）是 JY客运 的列车12/14 也在用的通用动力车，不能动。

用法
----
    python apply_flagship_accel.py              # 应用（先备份）
    python apply_flagship_accel.py --restore    # 从备份回滚
    python apply_flagship_accel.py --dry-run    # 只预览，不落盘
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

MOD_ROOT = Path(r"E:\SteamLibrary\steamapps\workshop\content\1066780\3374213837")
PROJECT_BACKUP = Path(r"E:\workbody\TPF2Mcp\_backup")
REL_FILES = (
    "res/models/model/vehicle/train/CR400AF_0208/TC/MP/04_T.mdl",
    "res/models/model/vehicle/train/CR400AF_0208/TC/MP/05_T.mdl",
)

# 目标值：与同编组的标准动力车（MC/MP/02、MC/MP/07）完全一致，物理上说得通
TARGET_POWER = 2500        # kW
TARGET_TRACTION = 151      # kN


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def patch_text(text: str, power: float, traction: float) -> str:
    """只替换数字，不动换行与其它内容（保证行尾/编码字节级不变）。"""
    text = re.sub(r"(local trainEnginePower\s*=\s*)(-?[0-9.]+)", r"\g<1>%g" % power, text, count=1)
    text = re.sub(r"(local trainTractiveEffort\s*=\s*)(-?[0-9.]+)", r"\g<1>%g" % traction, text, count=1)
    return text


def current_values(text: str) -> tuple[str, str]:
    power = re.search(r"local trainEnginePower\s*=\s*([-0-9.]+)", text)
    traction = re.search(r"local trainTractiveEffort\s*=\s*([-0-9.]+)", text)
    return (power.group(1) if power else "?", traction.group(1) if traction else "?")


def backup_dir(stamp: str) -> Path:
    target = MOD_ROOT / "backup" / f"cre400af_mp_trailers_{stamp}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def restore() -> int:
    backups = sorted((MOD_ROOT / "backup").glob("cre400af_mp_trailers_*")) if (MOD_ROOT / "backup").exists() else []
    if not backups:
        print("找不到备份目录，无法回滚")
        return 1
    latest = backups[-1]
    for rel in REL_FILES:
        source = latest / Path(rel).name
        if not source.exists():
            print(f"缺备份文件：{source}")
            return 1
        shutil.copy2(source, MOD_ROOT / rel)
        print(f"已回滚 {rel} ← {source}")
    print(f"回滚完成（来源 {latest}）")
    return 0


def verify() -> int:
    """把当前文件里的动力值改回 0，与备份逐字节比对 —— 相同即证明只改了那两个数字。"""
    backups = sorted((MOD_ROOT / "backup").glob("cre400af_mp_trailers_*"))
    if not backups:
        print("找不到备份，无法校验")
        return 1
    latest = backups[-1]
    ok = True
    for rel in REL_FILES:
        patched = MOD_ROOT / rel
        original = latest / Path(rel).name
        reverted = patch_text(patched.read_text(encoding="utf-8"), 0, 0).encode("utf-8")
        same = reverted == original.read_bytes()
        ok = ok and same
        print(f"{'✓' if same else '✗'} {Path(rel).name}: "
              f"改后还原回原值 {'与备份逐字节一致' if same else '与备份不一致！'}"
              f"（当前 {current_values(patched.read_text(encoding='utf-8'))[0]} kW / "
              f"{current_values(patched.read_text(encoding='utf-8'))[1]} kN，"
              f"大小 {original.stat().st_size} → {patched.stat().st_size}）")
    print()
    print("结论：", "只改动了动力与牵引力两个数字，其余字节未变" if ok else "存在非预期改动，请回滚")
    return 0 if ok else 1


def main() -> int:
    dry = "--dry-run" in sys.argv
    if "--restore" in sys.argv:
        return restore()
    if "--verify" in sys.argv:
        return verify()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir(stamp) if not dry else None
    project_backup = PROJECT_BACKUP / f"3374213837_{stamp}"
    if not dry:
        project_backup.mkdir(parents=True, exist_ok=True)

    print(f"{'[预览] ' if dry else ''}目标：给列车41 独占的 2 节车厢加动力 "
          f"→ power {TARGET_POWER} kW / traction {TARGET_TRACTION} kN")
    print()
    changed = 0
    for rel in REL_FILES:
        path = MOD_ROOT / rel
        text = path.read_text(encoding="utf-8")
        before = current_values(text)
        after_text = patch_text(text, TARGET_POWER, TARGET_TRACTION)
        after = current_values(after_text)
        print(f"{Path(rel).name}: {before[0]} kW/{before[1]} kN → {after[0]} kW/{after[1]} kN"
              f"  (sha256 {sha256(path)})")
        if dry:
            continue
        shutil.copy2(path, backup / Path(rel).name)              # 目标目录内备份（用户约定）
        shutil.copy2(path, project_backup / Path(rel).name)      # 项目内备份（防 Steam 覆盖）
        path.write_text(after_text, encoding="utf-8", newline="")  # newline='' = 不转换行尾
        changed += 1

    if dry:
        print("\n预览模式：未写入任何文件")
        return 0

    print(f"\n已修改 {changed} 个文件")
    print(f"备份（mod 目录内）: {backup}")
    print(f"备份（项目内）    : {project_backup}")
    print()
    verify()
    print("生效方式：完全退出游戏 → 重新启动 → 载入存档（.mdl 只在启动时读取）")
    print("回滚：python apply_flagship_accel.py --restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
