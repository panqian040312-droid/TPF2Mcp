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

        layer_bounds = bounds or bounds_from_payload(payload)
        if layer_bounds is None:
            summary[name] = {"skipped": "no bounds available"}
            continue
        minimum = layer_bounds["min"]

        geometry_kind = payload.get("geometry_kind") or "EDGE_GRAPH"
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
        summary[name] = {"tiles": len(index), "counts": manifest["counts"],
                         "dropped": dropped,
                         "bounds_from": "rail-manifest" if bounds else "self"}

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
