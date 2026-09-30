#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 layer-road.json 生成**静态**道路几何，供「道路拥堵」图层画色带用。

为什么要单独一份几何：
  路况指标每 5 分钟刷一次，而路的形状基本不变。如果每次刷指标都重新搬一遍
  9,943 条边的坐标（约 800 KB），既慢又没意义。所以拆成两份：
    · 本工具产出的 `layers/road-edge-geometry.json`  ← 静态，修路后才需要重跑
    · mod 自动产出的 `layers/road-traffic-data.json` ← 动态，每 5 分钟一份
  前端把两者按 edge_id 一 join 就能画。

几何算法与底图道路完全一致（`network-app.js` 的 edgePath）：
  三次贝塞尔，控制点 = 端点 ± 切线/3。这里把控制点直接算成**世界坐标**写出来，
  前端只做 P() 映射，因此不会和底图的曲线画法产生偏差。

顺带做一次体检：如果 `layer-road-traffic.json` 在，就把最堵的几段打出来
（离线看数据用，不参与前端渲染）。

用法：
  python tools/build-road-geometry.py
  python tools/build-road-geometry.py --bridge "<bridge 目录>"
"""

import argparse
import json
import os
import sys
import time

DEFAULT_BRIDGE = (r"C:\Program Files (x86)\Steam\userdata\1070536217"
                  r"\1066780\local\staging_area\tpf2mcp_1\bridge")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def node_positions(road):
    """layer-road.json 的 nodes → {entity_id: (x, y)}。两种形状都吃。"""
    nodes = road.get("nodes") or []
    out = {}
    if isinstance(nodes, dict):
        for key, value in nodes.items():
            pos = (value or {}).get("position") or {}
            if "x" in pos and "y" in pos:
                out[int(key)] = (float(pos["x"]), float(pos["y"]))
    else:
        for item in nodes:
            pos = (item or {}).get("position") or {}
            if "x" in pos and "y" in pos:
                out[int(item.get("entity_id"))] = (float(pos["x"]), float(pos["y"]))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", default=DEFAULT_BRIDGE)
    parser.add_argument("--project",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    args = parser.parse_args()

    bridge = args.bridge
    out_directory = os.path.join(os.path.abspath(args.project), "ui", "rail-map", "layers")
    os.makedirs(out_directory, exist_ok=True)
    out_path = os.path.join(out_directory, "road-edge-geometry.json")

    road_path = os.path.join(bridge, "layer-road.json")
    road = load_json(road_path)
    positions = node_positions(road)

    ids, shapes, missing = [], [], 0
    for edge in road.get("edges") or []:
        edge_id = edge.get("entity_id")
        if edge_id is None:
            continue
        p0 = positions.get(int(edge.get("node0") or -1))
        p1 = positions.get(int(edge.get("node1") or -1))
        if not (p0 and p1):
            missing += 1
            continue
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        t0 = edge.get("tangent0") or {"x": dx, "y": dy}
        t1 = edge.get("tangent1") or {"x": dx, "y": dy}
        ids.append(int(edge_id))
        shapes.append([
            round(p0[0], 2), round(p0[1], 2),
            round(p0[0] + float(t0.get("x", dx)) / 3.0, 2), round(p0[1] + float(t0.get("y", dy)) / 3.0),
            round(p1[0] - float(t1.get("x", dx)) / 3.0, 2), round(p1[1] - float(t1.get("y", dy)) / 3.0),
            round(p1[0], 2), round(p1[1], 2),
        ])

    payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": {
            "file": "layer-road.json",
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                   time.localtime(os.path.getmtime(road_path))),
        },
        "count": len(ids),
        "note": "每条边 8 个数：[起点x,起点y, 控制点1x,控制点1y, 控制点2x,控制点2y, 终点x,终点y]，世界坐标",
        "ids": ids,
        "shapes": shapes,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(out_path) / 1024.0
    print("道路几何：%d 条边（另有 %d 条缺端点坐标，已跳过）→ %.0f KB" % (len(ids), missing, size_kb))
    print("输出 → %s" % out_path)

    # 顺带体检：读一次路况层，把最堵的几段打出来（离线看，不参与渲染）
    traffic_path = os.path.join(bridge, "layer-road-traffic.json")
    if not os.path.exists(traffic_path):
        print("（还没有 layer-road-traffic.json —— 游戏跑起来后 mod 会自己按 5 分钟节奏产出）")
        return 0
    traffic = load_json(traffic_path)
    if traffic.get("status") != "OK":
        print("路况层状态 %s：%s" % (traffic.get("status"), traffic.get("error")))
        return 0
    summary = traffic.get("summary") or {}
    print()
    print("路况：车 %s 辆（定位到路段 %s / 失败 %s），有车路段 %s（严重 %s / 拥挤 %s）"
          % (summary.get("road_vehicles"), summary.get("located"), summary.get("unlocated"),
             summary.get("segments_with_traffic"), summary.get("alarm"), summary.get("warn")))
    vehicles = traffic.get("vehicles") or {}
    if vehicles.get("fail_reasons"):
        print("定位失败原因：%s" % json.dumps(vehicles["fail_reasons"], ensure_ascii=False))
    if vehicles.get("move_mode"):
        print("出行方式分布（lastMoveMode，枚举含义待实测）：%s"
              % json.dumps(vehicles["move_mode"], ensure_ascii=False))
    items = (traffic.get("segments") or {}).get("items") or []
    worst = [row for row in items if row.get("level") in ("ALARM", "WARN")][:10]
    if worst:
        print("最堵的 %d 段：" % len(worst))
        for row in worst:
            print("   路段 %-9s %-4s  车 %-4s 平均 %-6s km/h（畅通 %-6s）公交 %s"
                  % (row.get("edge_id"), row.get("level"), row.get("n"),
                     row.get("avg_kmh") and round(row["avg_kmh"], 1),
                     row.get("ff_kmh") and round(row["ff_kmh"], 1),
                     "有" if row.get("has_bus") else "无"))
    else:
        print("没有达到拥挤阈值的路段（阈值未标定，可能偏松）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
