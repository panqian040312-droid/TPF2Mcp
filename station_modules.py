"""提取 TPF2 车站模块目录：名称 / 样式 / 长度 / 承载人数 / 造价 / 起用年份。

承载人数机制（源码为证）
------------------------
`res/scripts/modulesutil.lua:19`：
    function modulesutil.getStationPoolCapacities(modules, result)
        local passCap, cargoCap = 0, 0
        for num, slot in pairs(result.slots) do
            local m = modules[slot.id]
            if m and m.metadata.moreCapacity then
                cargoCap = cargoCap + (m.metadata.moreCapacity.cargo or 0)
                passCap  = passCap  + (m.metadata.moreCapacity.passenger or 0)
            end
        end
        return passCap, cargoCap
    end

→ **车站承载人数 = 该站所有已放置模块的 `metadata.moreCapacity.passenger` 之和**（货运站取 cargo）。
   站台 / 雨棚 / 轨道等模块不提供容量，容量全部来自「主站房」「侧房」这类建筑模块。
   原版 `station/rail/modular_station/modular_station.con` 把它写进 `station.pool.moreCapacity`。

数据来源
--------
- 原版：`<游戏>\\res\\construction\\construction.zip` → `station/rail/modular_station/*.module`
- UST 地铁站（Yangon 用）：创意工坊 mod 2928021669 → `res/construction/station/rail/ust/**/*.module`
- MUS 站（Hanoi 用）：创意工坊 mod 1991928620 → `res/construction/station/rail/*`（**该 mod 未定义任何容量**）

用法：python station_modules.py [--json]
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

GAME = Path(r"E:\SteamLibrary\steamapps\common\Transport Fever 2")
ZIP = GAME / "res" / "construction" / "construction.zip"
WORKSHOP = Path(r"E:\SteamLibrary\steamapps\workshop\content\1066780")
OUT_JSON = Path(r"E:\workbody\TPF2Mcp\ui\rail-map\station-module-catalog.json")
VANILLA_PREFIX = "station/rail/modular_station/"


def strip_matrices(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not re.match(r"^\s*\{\s*-?[0-9.]", l))


def field_number(text: str, key: str) -> float | None:
    m = re.search(r"(?:local\s+)?" + key + r"\s*=\s*(-?[0-9.]+)", text)
    return float(m.group(1)) if m else None


def field_string(text: str, key: str) -> str | None:
    m = (re.search(key + r'\s*=\s*_\("([^"]*)"\)', text)
         or re.search(key + r'\s*=\s*"([^"]*)"', text))
    return m.group(1) if m else None


def more_capacity(text: str) -> tuple[float, float]:
    """返回 (passenger, cargo)。值可能是字面数字，也可能是局部变量（如 passengerCapacity）。"""
    def resolve(token: str) -> float:
        token = token.strip()
        if re.fullmatch(r"-?[0-9.]+", token):
            return float(token)
        m = re.search(r"local\s+" + re.escape(token) + r"\s*=\s*(-?[0-9.]+)", text)
        return float(m.group(1)) if m else 0.0

    m = re.search(r"moreCapacity\s*=\s*\{([^}]*)\}", text, re.S)
    if not m:
        return 0.0, 0.0
    body = m.group(1)
    pax = re.search(r"passenger\s*=\s*([A-Za-z_0-9.]+)", body)
    car = re.search(r"cargo\s*=\s*([A-Za-z_0-9.]+)", body)
    return (resolve(pax.group(1)) if pax else 0.0, resolve(car.group(1)) if car else 0.0)


def parse_module(name: str, raw: str, source: str) -> dict:
    text = strip_matrices(raw)
    half = re.search(r"halfExtents\s*=\s*\{\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)", text)
    pax, cargo = more_capacity(text)
    em = re.search(r"era_([abc])", name)
    return {
        "module": name.split("/")[-1].replace(".module", ""),
        "path": name,
        "source": source,
        "name": field_string(text, "name"),
        "description": field_string(text, "description"),
        "type": field_string(text, "type"),
        "era": {"a": "A", "b": "B", "c": "C"}.get(em.group(1)) if em else None,
        "passenger_capacity": pax,
        "cargo_capacity": cargo,
        "price": field_number(text, "price"),
        "year_from": field_number(text, "yearFrom"),
        "length_m": float(half.group(2)) * 2 if half else None,
        "width_m": float(half.group(1)) * 2 if half else None,
    }


STATION_TYPES = {
    "station/rail/": "火车站",
    "station/air/": "机场",
    "station/street/": "汽车站",
    "station/water/": "码头",
}


def station_type_of(name: str) -> str:
    for prefix, cn in STATION_TYPES.items():
        if name.startswith(prefix):
            return cn
    return "?"


def collect() -> tuple[list[dict], float, float]:
    """四类站的模块（铁路/机场/汽车站/码头）—— 容量机制四类通用（见模块头注释）。"""
    out: list[dict] = []
    z = zipfile.ZipFile(ZIP)
    con = z.read(VANILLA_PREFIX + "modular_station.con").decode("utf-8", errors="ignore")
    grid_len = field_number(con, "platformLength") or 0.0
    grid_wid = field_number(con, "platformWidth") or 0.0
    for name in z.namelist():
        if name.endswith(".module") and station_type_of(name) != "?":
            e = parse_module(name, z.read(name).decode("utf-8", errors="ignore"),
                             f"原版·{station_type_of(name)}")
            e["station_type"] = station_type_of(name)
            out.append(e)

    ust = WORKSHOP / "2928021669" / "res" / "construction" / "station" / "rail" / "ust"
    if ust.exists():
        for path in sorted(ust.rglob("*.module")):
            rel = path.relative_to(WORKSHOP / "2928021669").as_posix()
            e = parse_module(rel, path.read_text(encoding="utf-8", errors="ignore"), "mod·地下站 UST")
            e["station_type"] = "火车站"
            out.append(e)

    mus = WORKSHOP / "1991928620" / "res" / "construction" / "station" / "rail"
    if mus.exists():
        for path in sorted(mus.glob("*.module")):
            rel = path.relative_to(WORKSHOP / "1991928620").as_posix()
            e = parse_module(rel, path.read_text(encoding="utf-8", errors="ignore"), "mod·MUS 站")
            e["station_type"] = "火车站"
            out.append(e)
    return out, grid_len, grid_wid


def main() -> None:
    catalog, grid_len, grid_wid = collect()
    print("=" * 104)
    print("TPF2 车站模块目录（承载人数 = 各模块 metadata.moreCapacity 之和）")
    print("=" * 104)
    print(f"站台网格：platformLength = {grid_len:.0f} 米/模块，platformWidth = {grid_wid:.0f} 米")
    print()

    sources = []
    for x in catalog:
        if x["source"] not in sources:
            sources.append(x["source"])
    for source in sources:
        items = [x for x in catalog if x["source"] == source]
        if not items:
            continue
        with_cap = [x for x in items if x["passenger_capacity"] or x["cargo_capacity"]]
        print(f"── {source}：{len(items)} 个模块，其中 {len(with_cap)} 个提供容量")
        if not with_cap:
            print("     （该车站系统不定义任何容量 —— 放到这类站上的建筑模块才提供容量）")
            print()
            continue
        print(f"{'模块':<34}{'类型':<28}{'样式':>4}{'客容量':>8}{'货容量':>8}{'造价':>8}{'起始年':>7}")
        print("-" * 104)
        for e in sorted(with_cap, key=lambda x: -(x["passenger_capacity"] or 0)):
            print(f"{e['module']:<34}{(e['type'] or '—')[:27]:<28}{e['era'] or '—':>4}"
                  f"{e['passenger_capacity']:>8.0f}{e['cargo_capacity']:>8.0f}"
                  f"{(e['price'] or 0):>8.0f}{(e['year_from'] or 0):>7.0f}")
        print()

    plat = [x for x in catalog if "platform" in (x["type"] or "") and (x["length_m"] or 0) > 0]
    print("── 站台模块（不提供容量，只提供长度）")
    for e in sorted({x["module"]: x for x in plat}.values(), key=lambda x: x["module"]):
        print(f"   {e['module']:<44} 长 {e['length_m']:.0f} m × 宽 {e['width_m']:.0f} m"
              f" | 造价 {e['price'] or 0:.0f} | 样式 {e['era'] or '—'}")

    if "--json" in sys.argv:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps({
            "source": "construction.zip + workshop mods 2928021669 / 1991928620",
            "aggregation": "车站承载人数 = Σ 模块 metadata.moreCapacity.passenger（modulesutil.lua:19）",
            "platform_grid": {"length_m": grid_len, "width_m": grid_wid},
            "modules": catalog,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print()
        print(f"已写出 {OUT_JSON}")


if __name__ == "__main__":
    main()
