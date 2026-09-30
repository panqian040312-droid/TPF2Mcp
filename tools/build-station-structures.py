#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 bridge 里的车站结构探针整理成前端能直接读的一份数据。

数据来源是 bridge 里的两份产物：

  station-struct-probe.json —— 每个站的**占地包围盒**和**站台坐标**，是游戏自己量出来的，
                               权威。只含四类有站房建筑的站（火车 78 / 汽车 195 / 港口 46 / 机场 14）。
  layer-stations.json       —— 565 座站的名字、客货标志，前端本来就在用的那份。

🔴 两份**不能按 id 关联**：实测 333 个 station_id 一个都对不上 layer-stations 的 entity_id
   —— 引擎里"车站实体"和"站房建筑实体"是两套 id。所以这里按**坐标就近**匹配。
   匹配半径也不是固定值：机场占地能到 800×460 米，框心离站心上百米是正常的，
   所以半径取 max(150 米, 包围盒半对角线)。

用法：
    python tools/build-station-structures.py
    python tools/build-station-structures.py --bridge "<staging>\\bridge" --out "<项目>\\ui\\rail-map\\layers\\station-structures.json"
"""

import argparse
import json
import math
import os
import sys
import time

DEFAULT_BRIDGE = (r"C:\Program Files (x86)\Steam\userdata\1070536217"
                  r"\1066780\local\staging_area\tpf2mcp_1\bridge")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "ui", "rail-map", "layers", "station-structures.json")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── 模块格子：把 slotId 反解成网格坐标，再算成世界坐标 ──────────────────────
#
# 四类站都是"一个 .con 容器 + 若干 .module 格子"拼出来的。每格放的是站台、站房、
# 轨道、楼梯还是栈桥，看模块文件名；放在哪，要按 slotId 反解 —— 各站型的编码不同，
# 公式抄自各自的 .con（出处：construction.zip 里的 AddSlot / GetModuleAt）。
#
#   火车站：slotId = 基址 + 1000*i + 10*j        格 5 m × 40 m
#   码头：  slotId = 1000000*(c1+100) + 100*(c2+100) + c3   格 12.5 m × 12.5 m
#   汽车站：slotId = 200000*(c2+100) + 100*(c1+100) + c3    格 5 / 10 m（按模块类型）
#   机场：  slotId = 基址 + 一维序号（**不含坐标**，反解不出位置）
#
# 有了 (i, j) 乘上格尺寸就是**建筑局部坐标**，再套 construction.transf（4×4 矩阵，
# 行主序，第 13/14/15 个数是平移）就得到世界坐标。

RAIL_BASES = {
    3400000: "main_building",
    4400000: "platform",
    6400000: "cargo_platform",
    7400000: "passenger_platform",
    8400000: "track",
    9400000: "stairs",
    10400000: "platform_roof",
    10800000: "platform_addon",
}
RAIL_CELL_W = 5.0        # 每格宽（modular_station.con: platformWidth = 5）
RAIL_CELL_H = 40.0       # 每格长（platformLength = 40）


def cell_kind(name):
    """模块文件名 → 画图用的分类（前端 CELL_COLOR 认这几个键）。"""
    text = (name or "").lower()
    if "roof" in text:
        return "other"
    if "platform" in text or "dock" in text:
        return "platform"
    if "building" in text:
        return "building"
    if "track" in text:
        return "track"
    if "stair" in text:
        return "stairs"
    if "pier" in text:
        return "pier"
    if "entrance" in text or "exit" in text:
        return "entrance"
    if "terminal" in text or "hangar" in text or "runway" in text:
        return "terminal"
    return "other"


def rail_slot_to_ij(slot):
    """火车站的 slotId → (i, j, variant, 槽位种类)。认不出返回 None。"""
    for base, slot_kind in RAIL_BASES.items():
        diff = slot - base
        # 1000*i + 10*j，实测 i / j 都在 ±14 附近 —— 超出这个范围说明认错了基址
        if -20000 < diff < 20000:
            # Python 的 // 和 % 对负数都是向下取整语义，正好跟 Lua 的编码对得上
            i = diff // 1000
            j = (diff % 1000) // 10
            variant = diff % 10
            if -20 <= i <= 20 and 0 <= j <= 99:
                return i, j, variant, slot_kind
    return None


def apply_transf(matrix, lx, ly, lz=0.0):
    """4×4 矩阵（行主序的 16 个数）× 局部坐标 → 世界坐标。

    游戏给的是 `transf.one_based`，第 13/14/15 个数就是平移（实测建筑原点）。
    """
    if not matrix or len(matrix) < 15:
        return None
    wx = matrix[0] * lx + matrix[1] * ly + matrix[2] * lz + matrix[12]
    wy = matrix[4] * lx + matrix[5] * ly + matrix[6] * lz + matrix[13]
    wz = matrix[8] * lx + matrix[9] * ly + matrix[10] * lz + matrix[14]
    return wx, wy, wz


def build_cells(entry):
    """把一格的清单变成前端能直接画的多边形。

    没采到格子（探针还没重跑）时返回空表 —— 上层会退化成"只画外围大框"。
    """
    grid = (entry.get("construction") or {}).get("module_grid") or {}
    cells_in = grid.get("cells")
    if not cells_in:
        return [], None

    matrix = ((entry.get("construction") or {}).get("transf") or {}).get("one_based")
    kind = entry.get("kind")
    out = []
    if kind == "rail":
        for cell in cells_in:
            slot = cell.get("slot")
            if not isinstance(slot, int):
                continue
            decoded = rail_slot_to_ij(slot)
            if decoded is None:
                continue
            i, j, _variant, _slot_kind = decoded
            lx, ly = i * RAIL_CELL_W, j * RAIL_CELL_H
            # 四角（建筑局部坐标）→ 世界坐标
            corners = []
            ok = True
            for cx, cy in ((lx, ly), (lx + RAIL_CELL_W, ly),
                           (lx + RAIL_CELL_W, ly + RAIL_CELL_H), (lx, ly + RAIL_CELL_H)):
                world = apply_transf(matrix, cx, cy)
                if world is None:
                    ok = False
                    break
                corners.append([round(world[0], 2), round(world[1], 2)])
            if not ok:
                return out, "transf 缺失，格子算不出世界坐标"
            out.append({
                "k": cell_kind(cell.get("name")),
                "m": cell.get("name"),
                "ij": [i, j],
                "poly": corners,
            })
        return out, None
    # 另外三类：编码公式有，但格尺寸/基准还差一轮实测校验 —— 先不动，留给外围框
    return out, "kind=%s 的 slotId 反解尚未接入" % kind


def box_of(entry):
    """从探针条目里取出占地包围盒，返回 (minx, miny, w, h, height) 或 None。"""
    bv = entry.get("bounding_volume") or {}
    mn, mx = bv.get("min"), bv.get("max")
    if not mn or not mx:
        return None
    w = mx["x"] - mn["x"]
    h = mx["y"] - mn["y"]
    dz = mx.get("z", 0) - mn.get("z", 0)
    return mn["x"], mn["y"], w, h, dz


def terminals_of(entry):
    """站台坐标。

    ⚠️ 只有火车站能读出来，水运/道路/航空的 position 全是 (0,0,0)（引擎 getter 取不到，
    跟车站自己所在的坐标差着几千公里，明显是空值）。所以按"是否落在本站框附近"筛一道，
    免得在原点附近糊一堆假站台。
    """
    out = []
    box = box_of(entry)
    for term in entry.get("terminals") or []:
        pos = term.get("position") or {}
        x, y, z = pos.get("x"), pos.get("y"), pos.get("z")
        if x is None or y is None:
            continue
        if abs(x) < 1e-6 and abs(y) < 1e-6:
            continue
        if box is not None:
            minx, miny, w, h, _ = box
            # 放宽 60 米，允许站台压在框边上
            if not (minx - 60 <= x <= minx + w + 60 and miny - 60 <= y <= miny + h + 60):
                continue
        out.append({"x": round(x, 2), "y": round(y, 2), "z": round(z or 0, 2),
                    "index": term.get("index")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", default=os.environ.get("TPF2_BRIDGE_DIR", DEFAULT_BRIDGE))
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    probe_path = os.path.join(args.bridge, "station-struct-probe.json")
    stations_path = os.path.join(args.bridge, "layer-stations.json")
    for path in (probe_path, stations_path):
        if not os.path.exists(path):
            print("找不到：%s" % path, file=sys.stderr)
            return 1

    probe = load_json(probe_path)
    stations = load_json(stations_path).get("stations") or []
    if not stations:
        print("layer-stations.json 里没有 stations", file=sys.stderr)
        return 1

    kinds = probe.get("kinds") or {}
    printed = {"probe_mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                           time.localtime(os.path.getmtime(probe_path))),
               "stations_mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                               time.localtime(os.path.getmtime(stations_path)))}

    out_stations = []
    counts = {}
    unmatched = []
    cell_total = 0          # 反解成功的模块格子总数
    cell_skipped = {}       # 没能反解的站：kind → 个数（附原因）

    for kind in ("rail", "street", "water", "air"):
        for entry in kinds.get(kind) or []:
            box = box_of(entry)
            counts[kind] = counts.get(kind, 0) + 1
            if box is None:
                continue
            minx, miny, w, h, dz = box
            cx, cy = minx + w / 2.0, miny + h / 2.0

            # 就近匹配：半径随占地放大（机场 800×460 很常见）
            limit = max(150.0, math.hypot(w, h) / 2.0)
            best, best_d = None, None
            for station in stations:
                pos = station.get("position") or {}
                if pos.get("x") is None:
                    continue
                d = math.hypot(pos["x"] - cx, pos["y"] - cy)
                if best_d is None or d < best_d:
                    best, best_d = station, d

            name = None
            station_ref = None
            if best is not None and best_d is not None and best_d <= limit:
                name = best.get("name")
                station_ref = best.get("entity_id")
            else:
                unmatched.append({"kind": kind, "station_id": entry.get("station_id"),
                                  "nearest_dist": round(best_d) if best_d is not None else None})

            cells, cells_note = build_cells(entry)
            if cells:
                cell_total += len(cells)
            elif cells_note:
                cell_skipped[kind] = cell_skipped.get(kind, 0) + 1

            out_stations.append({
                "id": entry.get("station_id"),
                "station_ref": station_ref,      # 匹配到的 layer-stations 实体 id（对不上就是 null）
                "name": name,
                "kind": kind,
                "cargo": bool(entry.get("cargo")),
                "group_id": entry.get("group_id"),
                "file": entry.get("construction_file"),
                "box": {"x": round(minx, 2), "y": round(miny, 2),
                        "w": round(w, 2), "h": round(h, 2)},
                "height": round(dz, 2),
                "terminals": terminals_of(entry),
                # 模块格子：真正的站场结构（站台/站房/轨道各一格）。采不到就是空表，
                # 前端会退化成"只画外围大框"。
                "cells": cells,
            })

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": printed,
        "note": "占地框是游戏给出的轴对齐包围盒（世界坐标，单位米）；不含朝向，所以画出来是正的矩形。",
        "counts": counts,
        "matched": sum(1 for s in out_stations if s["station_ref"] is not None),
        "stations": out_stations,
    }

    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    print("写出：%s" % args.out)
    print("  探针源文件时间：%s" % printed["probe_mtime"])
    print("  站台数据时间：%s" % printed["stations_mtime"])
    print("  结构框 %d 个（火车 %d / 汽车 %d / 港口 %d / 机场 %d）"
          % (len(out_stations), counts.get("rail", 0), counts.get("street", 0),
             counts.get("water", 0), counts.get("air", 0)))
    print("  配到站名的：%d / %d" % (payload["matched"], len(out_stations)))
    with_term = sum(1 for s in out_stations if s["terminals"])
    print("  带站台坐标的：%d 个（只有火车站读得出来，其余引擎不给）" % with_term)
    rooms = sum(1 for s in out_stations if s["cells"])
    print("  模块格子：%d 座站共 %d 格（%s）"
          % (rooms, cell_total,
             "探针还没重跑，没采到格子" if not cell_total
             else "、".join(sorted({c["k"] for s in out_stations for c in s["cells"]}))))
    if cell_skipped:
        print("  没接反解的：%s" % cell_skipped)
    if unmatched:
        print("  ⚠️ 没配到站名的 %d 个：%s" % (len(unmatched), unmatched[:6]))
    print("⚠️ 这份是生成数据，已由 .gitignore 忽略，勿提交。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
