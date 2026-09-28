"""把 mod 自驱推送的图层数据切块成前端可渲染的 manifest + tiles。

输入：bridge/layer-<name>.json —— 由 Lua 侧 collectors/layer_*.lua 自驱写出
      （见 layer_registry.lua；格式随 geometry_kind 走 EDGE_GRAPH 或 POINT）
输出：<output-directory>/<name>-manifest.json
      <output-directory>/<name>-tiles/tile-<ix>_<iy>.json

与本目录 export-rail-network-map.py 的分工：那个是铁路专用（站台模型、道岔、
岛式站台合并、线路物理寻路都只对铁路有意义）；本脚本只做"节点/边/点 + 切块"。
几何不做简化 —— 边的形状由前端用 Hermite 切线现画（与铁路 tile 同一套画法），
所以切块必须保留原始坐标和切线，不能抽稀。

🔴 全图层必须共用同一份全局 bounds 与 tile 网格原点，否则前端叠加时整体错位：
   前端投影完全由 manifest 的 bounds 决定，tile key 也按该原点切。所以本脚本
   默认从铁路 manifest 取 bounds（--bounds-manifest），保证与铁路图同框。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "mcp_server" / "src"))

from tpf2_mcp.config import bridge_dir  # noqa: E402


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def shared_bounds(manifest_path: Path) -> dict | None:
    """取全图层共用的全局 bounds（x/y 两轴）。取不到就返回 None，由调用方自行推算。"""
    data = read_json(manifest_path)
    bounds = data.get("bounds")
    if not isinstance(bounds, dict):
        return None
    minimum, maximum = bounds.get("min"), bounds.get("max")
    if not isinstance(minimum, dict) or not isinstance(maximum, dict):
        return None
    if "x" not in minimum or "y" not in minimum or "x" not in maximum or "y" not in maximum:
        return None
    return {"min": {"x": float(minimum["x"]), "y": float(minimum["y"])},
            "max": {"x": float(maximum["x"]), "y": float(maximum["y"])}}


def bounds_from_payload(payload: dict) -> dict | None:
    """兜底：从本层数据自己推一个范围（只在没有铁路 manifest 时用）。"""
    xs: list[float] = []
    ys: list[float] = []
    for node in payload.get("nodes") or []:
        position = node.get("position") or {}
        if isinstance(position.get("x"), (int, float)) and isinstance(position.get("y"), (int, float)):
            xs.append(float(position["x"]))
            ys.append(float(position["y"]))
    for point in payload.get("points") or []:
        position = point.get("position") or {}
        if isinstance(position.get("x"), (int, float)) and isinstance(position.get("y"), (int, float)):
            xs.append(float(position["x"]))
            ys.append(float(position["y"]))
    if not xs:
        return None
    return {"min": {"x": min(xs), "y": min(ys)}, "max": {"x": max(xs), "y": max(ys)}}


def tile_of(x: float, y: float, minimum: dict, tile_size: float) -> str:
    ix = math.floor((x - minimum["x"]) / tile_size)
    iy = math.floor((y - minimum["y"]) / tile_size)
    return f"{ix}_{iy}"


def grid_bounds(grid: dict) -> dict | None:
    """从网格参数推它自己的覆盖范围：origin + step × (cols-1)。"""
    try:
        origin = grid.get("origin") or {}
        origin_x, origin_y = float(origin["x"]), float(origin["y"])
        step_x, step_y = float(grid["step_x"]), float(grid["step_y"])
        cols, rows = int(grid["cols"]), int(grid["rows"])
    except (KeyError, TypeError, ValueError):
        return None
    if cols < 2 or rows < 2:
        return None
    return {"min": {"x": origin_x, "y": origin_y},
            "max": {"x": origin_x + step_x * (cols - 1), "y": origin_y + step_y * (rows - 1)}}


# 整层输出（不分块）的图层：几何形态决定了它们不能按 tile 切开。
#   ROUTE          一条线的停靠点散落在很多 tile 里，切开就得跨块接续
#   STATION_CLUSTER 站群的成员可能横跨好几个 tile，切开就断了"连成一片"这件事
#   GRID           等高线按 tile 切会在接缝处断掉
WHOLE_LAYER_FIELDS = {
    "ROUTE": ("lines", "by_carrier", "by_cargo"),
    "STATION_CLUSTER": ("clusters", "stations", "links", "by_cluster"),
}


def export_whole_layer(name: str, payload: dict, output_directory: Path) -> dict:
    """整层输出：一个数据文件 + 一个 manifest，不切块。"""
    kind = payload.get("geometry_kind")
    data = {
        "schema_version": 1,
        "layer": name,
        "geometry_kind": kind,
        "counts": payload.get("counts") or {},
    }
    for field in WHOLE_LAYER_FIELDS.get(kind, ()):
        if field in payload:
            data[field] = payload[field]

    (output_directory / f"{name}-data.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "layer": name,
        "geometry_kind": kind,
        "source_status": payload.get("source_status"),
        "generated_at": int(time.time()),
        "data_file": f"{name}-data.json",
        "counts": data["counts"],
        # 图层特有的摘要统计，前端做图例/按钮计数要用
        "by_carrier": data.get("by_carrier") or {},
        "by_cargo": data.get("by_cargo") or {},
        "by_cluster": data.get("by_cluster") or {},
        "diagnostics": payload.get("diagnostics"),
        "tiles": [],
        "tile_size_m": None,
        "detail_load_threshold_m": None,
    }
    (output_directory / f"{name}-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    summary = {"kind": kind, "counts": data["counts"]}
    for field in ("by_carrier", "by_cargo", "by_cluster"):
        if data.get(field):
            summary[field] = data[field]
    if isinstance(data.get("clusters"), list):
        summary["clusters"] = len(data["clusters"])
    if isinstance(data.get("lines"), list):
        summary["lines"] = len(data["lines"])
    return summary


def export_grid(name: str, payload: dict, output_directory: Path) -> dict:
    """网格图层（地形高度）：整层一个数据文件，**不分块**。

    为什么不分块：等高线必须连续。按 tile 切开的话，同一条等高线会在边上断掉，
    接缝处还得额外处理跨块连接 —— 而网格本身才几十 KB，整层加载的成本远低于
    维护一套跨块接续逻辑。地图（水体/地形）这类"底图"性质的数据都适合这条路径，
    与公路/产业/车辆那种"细节"性质的分块数据是两种东西。
    """
    grid = payload.get("grid") or {}
    heights = payload.get("heights") or []

    data = {
        "schema_version": 1,
        "layer": name,
        "geometry_kind": "GRID",
        "grid": grid,
        "counts": payload.get("counts") or {},
        "heights": heights,
    }
    (output_directory / f"{name}-data.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "layer": name,
        "geometry_kind": "GRID",
        "source_status": payload.get("source_status"),
        "generated_at": int(time.time()),
        "data_file": f"{name}-data.json",
        "grid": grid,
        "counts": payload.get("counts") or {},
        "diagnostics": payload.get("diagnostics"),
        # 网格层不分块，但保留空数组，让前端能走同一套 manifest 解析
        "tiles": [],
        "tile_size_m": None,
        "detail_load_threshold_m": None,
    }
    (output_directory / f"{name}-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    return {"grid": f"{int(grid.get('cols', 0))}x{int(grid.get('rows', 0))}",
            "samples": len(heights),
            "counts": manifest["counts"]}


def tile_bounds(key: str, minimum: dict, tile_size: float) -> dict:
    ix, iy = (int(part) for part in key.split("_", 1))
    return {
        "min": {"x": minimum["x"] + ix * tile_size, "y": minimum["y"] + iy * tile_size},
        "max": {"x": minimum["x"] + (ix + 1) * tile_size, "y": minimum["y"] + (iy + 1) * tile_size},
    }


def split_edge_graph(payload: dict, minimum: dict, tile_size: float) -> tuple[dict, dict, int]:
    """边图层：按边的中点决定归属 tile，再把该边用到的节点带进同一个 tile。

    返回 (tiles, tile_edges, dropped)。dropped 是"端点缺失或坐标不全"被丢掉的边数 ——
    静默丢边会让地图缺线而没人知道，所以一定要报出来。
    """
    node_by_id = {}
    for node in payload.get("nodes") or []:
        entity_id = node.get("entity_id")
        if entity_id is None:
            continue
        node_by_id[str(entity_id)] = node

    dropped = 0
    tile_edges: dict[str, list] = defaultdict(list)
    for edge in payload.get("edges") or []:
        start = node_by_id.get(str(edge.get("node0")))
        end = node_by_id.get(str(edge.get("node1")))
        if start is None or end is None:
            dropped += 1
            continue
        a, b = start.get("position") or {}, end.get("position") or {}
        if not all(isinstance(value, (int, float)) for value in (a.get("x"), a.get("y"), b.get("x"), b.get("y"))):
            dropped += 1
            continue
        key = tile_of((float(a["x"]) + float(b["x"])) / 2.0, (float(a["y"]) + float(b["y"])) / 2.0,
                      minimum, tile_size)
        tile_edges[key].append(edge)

    tiles: dict[str, dict] = {}
    for key, edges in tile_edges.items():
        used: dict[str, dict] = {}
        for edge in edges:
            for node_key in ("node0", "node1"):
                node = node_by_id.get(str(edge.get(node_key)))
                if node is not None:
                    used[str(node["entity_id"])] = node
        tiles[key] = {"key": key, "nodes": list(used.values()), "edges": edges,
                      "counts": {"edges": len(edges), "nodes": len(used)}}
    return tiles, tile_edges, dropped


def split_points(payload: dict, minimum: dict, tile_size: float) -> tuple[dict, dict, int]:
    """点图层：按点自身坐标决定归属 tile。返回 (tiles, tile_points, dropped)。"""
    dropped = 0
    tile_points: dict[str, list] = defaultdict(list)
    for point in payload.get("points") or []:
        position = point.get("position") or {}
        if not isinstance(position.get("x"), (int, float)) or not isinstance(position.get("y"), (int, float)):
            dropped += 1
            continue
        key = tile_of(float(position["x"]), float(position["y"]), minimum, tile_size)
        tile_points[key].append(point)

    tiles: dict[str, dict] = {}
    for key, points in tile_points.items():
        tiles[key] = {"key": key, "points": points, "counts": {"points": len(points)}}
    return tiles, tile_points, dropped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-directory", type=Path, default=None)
    parser.add_argument("--output-directory", type=Path,
                        default=REPOSITORY / "ui" / "rail-map" / "layers")
    parser.add_argument("--bounds-manifest", type=Path,
                        default=REPOSITORY / "ui" / "rail-map" / "rail-network-manifest.json",
                        help="从中取全图层共用的全局 bounds（默认取铁路图那份）")
    parser.add_argument("--tile-size", type=float, default=2000.0)
    parser.add_argument("--detail-load-threshold-m", type=float, default=600.0)
    parser.add_argument("layers", nargs="*",
                        help="要导出的图层名（对应 bridge/layer-<name>.json）；省略则导出全部存在的")
    args = parser.parse_args()

    bridge = args.bridge_directory or bridge_dir()
    bounds = shared_bounds(args.bounds_manifest)
    args.output_directory.mkdir(parents=True, exist_ok=True)

    if args.layers:
        names = args.layers
    else:
        names = sorted(path.stem[len("layer-"):] for path in bridge.glob("layer-*.json"))

    summary = {}
    for name in names:
        payload = read_json(bridge / f"layer-{name}.json")
        if not payload:
            summary[name] = {"skipped": "no source file"}
            continue
        if payload.get("status") != "OK":
            summary[name] = {"skipped": f"source status {payload.get('status')}"}
            continue

        geometry_kind = payload.get("geometry_kind") or "EDGE_GRAPH"

        # 整层输出、不分块的两类：网格（地形高度）与线路（路径点序列）
        if geometry_kind == "GRID":
            summary[name] = export_grid(name, payload, args.output_directory)
            continue
        if geometry_kind in ("ROUTE", "STATION_CLUSTER"):
            summary[name] = export_whole_layer(name, payload, args.output_directory)
            continue

        layer_bounds = bounds or bounds_from_payload(payload)
        if layer_bounds is None:
            summary[name] = {"skipped": "no bounds available"}
            continue
        minimum = layer_bounds["min"]

        if geometry_kind == "POINT":
            tiles, grouped, dropped = split_points(payload, minimum, args.tile_size)
        else:
            tiles, grouped, dropped = split_edge_graph(payload, minimum, args.tile_size)

        tile_directory = args.output_directory / f"{name}-tiles"
        tile_directory.mkdir(parents=True, exist_ok=True)
        index = []
        for key in sorted(tiles, key=lambda value: (int(value.split("_", 1)[1]), int(value.split("_", 1)[0]))):
            tile = tiles[key]
            (tile_directory / f"tile-{key}.json").write_text(
                json.dumps(tile, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            entry = {"key": key, **tile_bounds(key, minimum, args.tile_size),
                     "edge_count": tile["counts"].get("edges", 0),
                     "node_count": tile["counts"].get("nodes", 0),
                     "point_count": tile["counts"].get("points", 0)}
            index.append(entry)

        manifest = {
            "schema_version": 1,
            "layer": name,
            "geometry_kind": geometry_kind,
            "source_status": payload.get("source_status"),
            "generated_at": int(time.time()),
            "bounds": layer_bounds,
            "tile_size_m": args.tile_size,
            "detail_load_threshold_m": args.detail_load_threshold_m,
            "counts": payload.get("counts") or {},
            "tiles": index,
        }
        # 图层特有的附加统计（道路类型分布等）原样带过去，前端可能要用
        for extra in ("street_types", "by_carrier"):
            if isinstance(payload.get(extra), dict):
                manifest[extra] = payload[extra]
        (args.output_directory / f"{name}-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

        # 概览层：最小缩放（总览）时显示的全局骨架，不分块。
        # 铁路的对应物是 manifest 里的 physical_overview_segments —— 没有它，用户在
        # 总览下只会看到空白，因为分块要放大到 detail_load_threshold_m 以下才加载。
        # 这里不追求几何精度（不采样曲线、只连端点），因为总览时线本来就重叠在一起；
        # 目的是让用户一眼看出"哪里有路/哪里有设施"。
        if geometry_kind == "POINT":
            summary_points = []
            for point in payload.get("points") or []:
                position = point.get("position") or {}
                if not isinstance(position.get("x"), (int, float)) or not isinstance(position.get("y"), (int, float)):
                    continue
                entry = [round(float(position["x"]), 1), round(float(position["y"]), 1)]
                if name == "vehicles":
                    # 必须把所属线路一起带上：前端要靠它查这条线是客运还是货运，
                    # 少了它总览下按职能筛选会一辆车都留不下（自检发现过这个问题）。
                    entry.append(point.get("carrier"))
                    entry.append(point.get("line"))
                elif name == "industry":
                    entry.append(point.get("level"))
                summary_points.append(entry)
            overview = {"layer": name, "geometry_kind": "POINT", "points": summary_points}
        else:
            summary_lines = []
            for tile in tiles.values():
                tile_nodes = {str(node["entity_id"]): node["position"] for node in tile["nodes"]}
                for edge in tile["edges"]:
                    start = tile_nodes.get(str(edge.get("node0")))
                    end = tile_nodes.get(str(edge.get("node1")))
                    if start is None or end is None:
                        continue
                    summary_lines.append([round(float(start["x"]), 1), round(float(start["y"]), 1),
                                          round(float(end["x"]), 1), round(float(end["y"]), 1)])
            overview = {"layer": name, "geometry_kind": "EDGE", "lines": summary_lines}
        (args.output_directory / f"{name}-overview.json").write_text(
            json.dumps(overview, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

        summary[name] = {"tiles": len(index), "counts": manifest["counts"],
                         "dropped": dropped,
                         "overview": len(overview.get("lines") or overview.get("points") or []),
                         "bounds_from": "rail-manifest" if bounds else "self"}

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
