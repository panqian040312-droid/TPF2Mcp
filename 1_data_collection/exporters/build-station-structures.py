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
    python 1_data_collection/exporters/build-station-structures.py
    python 1_data_collection/exporters/build-station-structures.py --bridge "<staging>\\bridge" --out "<项目>\\ui\\rail-map\\layers\\station-structures.json"
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
# 四类站都是"一个 .con 容器 + 若干 .module 格子"拼出来的（模块化设计）：站台、轨道、
# 顶棚、站房、楼梯各占一格。放在哪，要按 slotId 反解 —— 各站型的编码不同，公式抄自
# 各自的 .con（出处：construction.zip 里的 AddSlot / GetModuleAt）。
#
#   火车站：slotId = 基址 + 1000*i + 10*j          格 5 m × 40 m   ← **本次已接入**
#   码头：  slotId = 1000000*(c1+100) + 100*(c2+100) + c3   格 12.5 m × 12.5 m
#   汽车站：slotId = 200000*(c2+100) + 100*(c1+100) + c3    格 5 / 10 m（按模块类型）
#   机场：  slotId = 基址 + 一维序号（**不含坐标**，反解不出位置）
#
# 有了 (i, j) 乘上格尺寸就是**建筑局部坐标**，再套 construction.transf（4×4 矩阵，
# 行主序，第 13/14/15 个数是平移）就得到世界坐标 —— 这份矩阵在探针里是**有值**的。

# 站台类槽位：base → (画图分类, 局部 x 偏移, 局部 z 偏移)
RAIL_PLATFORM_BASES = {
    4400000: ("platform", 0.0, 0.0),      # 通用站台
    6400000: ("platform", 2.5, 0.0),      # 货运站台，偏移 platformWidth/2
    7400000: ("platform", 0.0, 0.0),      # 客运站台
    8400000: ("track", 0.0, 0.0),         # 轨道
    10400000: ("roof", 0.0, 2.0),         # 站台顶棚，抬高 2 m
    10800000: ("platform", 0.0, 2.0),     # 通道加装（楼梯口之类）
}
RAIL_BUILDING_BASE = 3400000   # 主建筑 / 侧楼，另走一套编码
RAIL_STAIRS_BASE = 9400000
RAIL_BASES = sorted(list(RAIL_PLATFORM_BASES) + [RAIL_BUILDING_BASE, RAIL_STAIRS_BASE])

RAIL_CELL_W = 5.0          # platformWidth：每列宽 5 m
RAIL_CELL_L = 40.0         # platformLength：每排长 40 m
RAIL_PLAT_HALF_L = 20.0    # 站台格子沿长边的半长（= platformLength/2）

# ── 站房真实占地（**槽位坐标系**里的矩形） ────────────────────────────────────
#
# 来源（两处互相印证，2026-10-02 逐个读出来的）：
#   · `construction.zip` → `station/rail/modular_station/{main,side}_building_*_era_*.module`
#     里的 `config.extend = { x+, x-, y0, y-, z+, z- }`（就是占地框）；
#   · `model.zip` → `model/station/rail/{era_c,cargo}/station_N[_main].mdl` 里的
#     `boundingInfo`（模型包围盒）。
#
# 摆放矩阵是 `transf.rotZTransl(math.rad(-90), vec3.new(7.5, 0, 0))`
# （出处：`main_building_*_era_*.module` 的 getModelsFn、以及 `res/scripts/modules/
#  trainstationutil.lua` 的 `MakeMainBuildingModule`）。
# 把 extend 框绕 z 转 -90° 再平移 (7.5, 0)，得到下面这四个数：
#   x 是**横向**（垂直于站台长边，即"跨几条股道"），y 是**沿站台方向**。
#
#   o=0 主楼 size1  extend 22×17 → x[-9.5, 7.5]   y[-11, 11]
#   o=1 主楼 size2  extend 22×23 → x[-15.5, 7.5]  y[-11, 11]   ← 主力，最常见
#   o=5 侧楼 size1  extend 12×17 → x[-9.5, 7.5]   y[-6, 6]
#   o=6 侧楼 size2  extend 22×23 → x[-15.5, 7.5]  y[-11, 11]
#   o=7 侧楼 size3  extend 42×38 → x[-30.5, 7.5]  y[-21, 21]
#
# 🔴 所以站房是 **23 × 22 米这种近正方形**，不是细长条 —— 用户 2026-10-02 指出的
#    "站房应该接近正方形"是对的，之前拿 20×20 猜、又拿固定像素折线画，都不对。
# ⚠️ 不能按 slotId 的 `o` 来选尺寸：`main_building_2` 与 `main_building_3_cargo`
#    的 slotIdOffset 都是 1、`main_building_1` 与 `main_building_2` 都是 0 —— 会撞车。
#    **按模块名查**才是唯一的（模块名里就写着是第几种尺寸）。
BUILDING_BOX_BY_MODULE = {
    "main_building_1": (-9.5, 7.5, -11.0, 11.0),     # 22×17 → 转后 17 × 22
    "main_building_2": (-15.5, 7.5, -11.0, 11.0),    # 22×23 → 23 × 22
    "main_building_3": (-30.5, 7.5, -21.0, 21.0),    # 42×38 → 38 × 42
    "side_building_1": (-9.5, 7.5, -6.0, 6.0),       # 12×17 → 17 × 12
    "side_building_2": (-15.5, 7.5, -11.0, 11.0),    # 22×23 → 23 × 22
    "side_building_3": (-30.5, 7.5, -21.0, 21.0),    # 42×38 → 38 × 42
}
BUILDING_BOX_DEFAULT = (-15.5, 7.5, -11.0, 11.0)     # 认不出就按 size2


def building_box_of(module_name):
    """站房模块名 → 它在槽位坐标系里的占地矩形 (x0, x1, y0, y1)。"""
    text = (module_name or "").lower()
    for key, box in BUILDING_BOX_BY_MODULE.items():
        if key in text:
            return box
    return BUILDING_BOX_DEFAULT


def load_preview(preview_dir, station_ref):
    """读作者那层的 `station-previews/<实体id>.json`。

    里面有两样别人给不了的东西：
      · `scope` —— 引擎给的**站场坐标系**（origin + direction/normal + along/across 范围）；
      · `platforms[].platform_centerline` —— 站台的**真实中心线**（世界坐标）。

    🔴 为什么非要用它：本站按 slotId 网格推出来的站台纵向长度是 360 m，
       而引擎给的站台线只有 209 m —— 网格推算在纵向会偏长，站房跟着它排就会"长出去"。
       所以站房**沿站场方向**的落点要用站台线的实际范围来定。
    """
    if station_ref is None:
        return None
    path = os.path.join(preview_dir, "station-%s.json" % station_ref)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def is_cargo_module(module_name):
    """模块名里带 `_cargo` 的就是货运站房（客运那批是 `..._era_c.module`）。

    出处：`station/rail/modular_station/` 下同时有 `main_building_2_era_c.module` 与
    `main_building_2_cargo.module` 两套 —— 名字里只有这一处差别。
    """
    return "_cargo" in (module_name or "").lower()


RAIL_BUILDING_FRONT_OFFSET = 200000   # 主建筑"前侧"（throughFrontTag）在 slotId 上的偏移


def rail_base_of(slot):
    """按"离哪个基址最近"判槽位种类。窗口 ±20000 远小于相邻基址间距（最小 400000）。

    ⚠️ 但**主建筑要单独放宽**：它的"前侧"版本（`throughFrontTag`）在 slotId 上带
    **+200000** 偏移 —— 实测广州北站 104701 的 `main_building_3*` 就是 3633111 / 3633151 /
    3633201（差 233xxx），原来 ±20000 的窗口直接把它们当"未识别"丢了，症状就是
    "游戏里明明有两个站房群、图上只画了一个"（用户 2026-10-02 指出）。
    """
    for base in RAIL_BASES:
        low, high = -20000, 20000
        if base == RAIL_BUILDING_BASE:
            # 前侧 = 200000 + 3000*i + …，i 是站台列号（大站能到二三十列），
            # 所以上限给到 +300000（= i 到 33）——仍远小于到下一个基址 4400000 的 700000 距离。
            high = RAIL_BUILDING_FRONT_OFFSET + 100000
        if low <= slot - base <= high:
            return base
    return None


def decode_grid(diff):
    """base + 1000*i + 10*j → (i, j)，**处理负 j 的借位**。

    🔴 这是本项目最难缠的一处编码坑：j 为负时，`1000*i + 10*j` 会把借位写在
    mod 1000 那一段上（落在 900~999）。朴素的 `(diff % 1000) // 10` 于是把 j
    解成 98/99，同时 `diff // 1000` 把 i 也少算了 1 —— 症状就是"格子全挤在包围盒
    的一角、前端看不到站房"（用户 2026-10-01 反馈"没有任何变化"的根因）。
    判据：j ∈ [-10, 10]，所以解出 51..99 的一律减 100 折回负数。
    """
    raw = (diff % 1000) // 10
    j = raw - 100 if raw > 50 else raw
    i = (diff - 10 * j) // 1000
    return i, j


def decode_building(diff):
    """主建筑/侧楼的 slotId → (i, j, k, o, front)。

    `id = 3400000 + 3000*i + 40*j + 10*k + o`（回侧），
    **前侧**版本再 **+200000**（`throughFrontTag`，出处同 `modular_station.con`）。

    o ∈ {0,1} 是主楼本体，{5,6,7} 是侧楼；k 是这一排内的分段；i 是**站台列号**
    （不是直接的 x，主楼贴在那一列的外侧）。拆法：先剥 o（个位），再剥 k
    —— 300*i 与 4*j 都是 4 的倍数，所以 t = 300*i + 4*j + k 对 4 取模就是 k；
    剩下的 75*i + j 里 j 值域很小，模 75 再折到 [-37, 37] 即可。
    """
    front = diff >= RAIL_BUILDING_FRONT_OFFSET
    if front:
        diff -= RAIL_BUILDING_FRONT_OFFSET
    o = diff % 10
    t = (diff - o) // 10
    k = t % 4
    q = (t - k) // 4
    j = q % 75
    if j > 37:
        j -= 75
    i = (q - j) // 75
    # 合理性检查 —— 站房的 i 是站台列号（本站最多几十列）、j 是排号（实测范围 -2..5）。
    # 🔴 实测 slot `3699980` 在 Kaohsiung / Taipei / Istanbul 三个站里**数值完全相同**，
    #    解出来是 i=33、j=24 —— 明显不是"前侧主楼"的编码（那是别的槽位混进了建筑名单），
    #    按它画会跑到站点外几百米去。解不出合理位置的，直接丢掉。
    if not (-20 <= j <= 20) or not (0 <= i <= 60):
        return None
    return i, j, k, o, front


def apply_transf(matrix, lx, ly, lz=0.0):
    """4×4 矩阵 × 局部坐标 → 世界坐标。

    🔴 **列主序**（实测判定，不是猜的）：Hanoi 的 transf 是
      `[0.8422, -0.5391, 0, 0, 0.5391, 0.8422, 0, 0, …]`，按列主序读，局部 y 方向
      映射到世界 `(0.5391, 0.8422)`，跟引擎自己给的站场方向 `scope.direction`
      = `(0.5391, 0.8422)` **完全一致**；按行主序读得到 `(-0.5391, 0.8422)`，
      方向反了一半 —— 站场被镜像，格子整体落到站台的另一侧（用户 2026-10-02
      反馈"对不上"就是这个）。
      平移仍在第 13/14/15 个数（列主序的最后一列），两种读法一样。

    ⚠️ 之前几版一直按行主序算，而且因为引擎包围盒够大、两种读法都落得进去，
      残差自检**抓不出来** —— 是拿 `scope.direction` 校方向才揪出来的。
      以后判定这类矩阵，一定要找一个"方向已知"的量去对，别只看是否越界。
    """
    if not matrix or len(matrix) < 15:
        return None
    wx = matrix[0] * lx + matrix[4] * ly + matrix[8] * lz + matrix[12]
    wy = matrix[1] * lx + matrix[5] * ly + matrix[9] * lz + matrix[13]
    wz = matrix[2] * lx + matrix[6] * ly + matrix[10] * lz + matrix[14]
    return wx, wy, wz


def poly_rect(matrix, cx, cy, half_x, half_y, yaw_deg=0.0):
    """一个**自带朝向**的矩形 → 世界坐标四角。

    🔴 四角都过矩阵，不只转中心点 —— 矩形是刚体，跟着站场一起转才不会跟网格错开。
    朝向（yaw）是模块自己的：码头按 `facing` 转，机场第二跑道一侧的模块转 180°。
    """
    if yaw_deg:
        rad = math.radians(yaw_deg)
        cs, sn = math.cos(rad), math.sin(rad)
    else:
        cs, sn = 1.0, 0.0
    poly = []
    for lx, ly in ((-half_x, -half_y), (half_x, -half_y),
                   (half_x, half_y), (-half_x, half_y)):
        world = apply_transf(matrix, cx + lx * cs - ly * sn, cy + lx * sn + ly * cs)
        if world is None:
            return None
        poly.append([round(world[0], 2), round(world[1], 2)])
    return poly


# ════════════════════════════════════════════════════════════════════════════
#  汽车站 / 卡车货运站 —— slotId 与坐标
# ════════════════════════════════════════════════════════════════════════════
#
# 出处：`station/street/modular_terminal.con` 的 `MangleId` / `DemangleId`
#      与布局循环 `coordI2varaintAndPos`（公式见 reports/TPF2_四类站结构解析_20260930.md §二）。
#
#   slotId = 200000×(j+100) + 100×(i+100) + v        v = 变体号，决定"这格是什么"
#
# 🔴 **横向位置 x 是累积算出来的，单看一个 slotId 算不出**：站台列沿 x 排开，
#    每列的 x = 上一列 x ± (轨道 5 m + 前半宽 + 后半宽) ⇒ 必须复现那个循环，
#    而且**逐列判客运/货运**（判据：该列 j=0 处有没有 v=0 的客运站台）。
#    这是本类站唯一的难点，也是"只按 slotId 硬解会全错"的地方。
STREET_VAR = {"passenger_platform": 0, "cargo_platform": 1, "small_building": 2,
              "entrance_exit": 3, "entrance": 4, "exit": 5,
              "ver_entrance_exit": 6, "ver_entrance": 7, "ver_exit": 8,
              "large_building": 9}
STREET_CENTER = 20.0          # centerSize
STREET_TRACK = 5.0            # trackSize
STREET_PAX_HALF = 2.5         # 客运站台宽 5（passenger_platform 的 .mdl 实测 5×10）
STREET_CARGO_HALF = 5.0       # 货运站台宽 10
STREET_CELL_L = 10.0          # 纵向一格 10 m（platformLength）
STREET_ENTRANCE_I = 55        # 出入口的哨兵列号
STREET_ENTRANCE_OFF = 15.0    # 哨兵出入口离站台的纵向偏移

# 模块真实占地（宽 × 深，米）—— 量自 `model.zip` 里 `.mdl` 的 `boundingInfo`。
# 键是模块文件名去掉目录与扩展名。
STREET_MODULE = {
    "passenger_platform": dict(size=(5.0, 10.0),  kind="platform"),
    "cargo_platform":     dict(size=(10.0, 10.0), kind="platform", cargo=True),
    "entrance":           dict(size=(10.0, 10.0), kind="entrance"),
    "entrance_exit":      dict(size=(10.0, 10.0), kind="entrance"),
    "exit":               dict(size=(10.0, 10.0), kind="entrance"),
    "_building_10_10":    dict(size=(10.0, 10.0), kind="building"),   # era_a/b/c 侧房 size1
    "_building_20_20":    dict(size=(20.0, 20.0), kind="building"),   # era_a/b/c 侧房 size2
}


def street_demangle(sid):
    """slotId → (i, j, 变体号)。"""
    v = sid % 100
    t = (sid - v) // 100
    return (t % 2000) - 100, t // 2000 - 100, v


def street_mangle(i, j, v):
    return 200000 * (j + 100) + 100 * (i + 100) + v


def street_layout(keys):
    """复现 `coordI2varaintAndPos`：返回 (每列 x 字典, rightLen, leftLen, minPos, maxPos)。

    逐列判客运/货运用的判据与 `.con` 一致：该列 j=0 处是不是 v=0。
    """
    mods = set(keys)
    cols = {}
    for i, j, _v in (street_demangle(k) for k in keys):
        cols.setdefault(i, []).append(j)
    if not cols:
        return {}, -1, 0, 0, 0
    min_col, max_col = min(cols), max(cols)
    min_j = {c: min(v) for c, v in cols.items()}
    max_j = {c: max(v) for c, v in cols.items()}

    def has(c, j):
        return (street_mangle(c, j, STREET_VAR["passenger_platform"]) in mods
                or street_mangle(c, j, STREET_VAR["cargo_platform"]) in mods)

    range0, range1 = {}, {}
    for c in range(min_col - 1, max_col + 2):
        r0 = 1
        for j in range(0, min_j.get(c, 0) - 1, -1):
            if has(c, j):
                r0 = j
            else:
                break
        range0[c] = r0
        r1 = -1
        for j in range(0, max_j.get(c, 0) + 1):
            if has(c, j):
                r1 = j
            else:
                break
        range1[c] = r1

    left_len = 0
    if range0.get(-1, 1) != 1 or range1.get(-1, -1) != -1:
        left_len = -1
    for c in range(-1, min_col - 1, -1):
        if ((range0.get(c - 1, 1) != 1 or range1.get(c - 1, -1) != -1)
                and range0[c] <= range1.get(c - 1, -1)
                and range1[c] >= range0.get(c - 1, 1)):
            left_len -= 1
        else:
            break
    right_len = -1
    if range0.get(0, 1) != 1 or range1.get(0, -1) != -1:
        right_len = 0
    for c in range(0, max_col + 1):
        if ((range0.get(c + 1, 1) != 1 or range1.get(c + 1, -1) != -1)
                and range0[c] <= range1.get(c + 1, -1)
                and range1[c] >= range0.get(c + 1, 1)):
            right_len += 1
        else:
            break

    def half_of(c):
        return (STREET_PAX_HALF
                if street_mangle(c, 0, STREET_VAR["passenger_platform"]) in mods
                else STREET_CARGO_HALF)

    pos = {}
    loc, last = STREET_CENTER * 0.5, -STREET_TRACK
    for c in range(0, right_len + 1):
        loc += STREET_TRACK + last
        last = half_of(c)
        loc += last
        pos[c] = loc
    loc, last = -STREET_CENTER * 0.5, -STREET_TRACK
    for c in range(-1, left_len - 1, -1):
        loc -= STREET_TRACK + last
        last = half_of(c)
        loc -= last
        pos[c] = loc

    min_pos = min(min(range0.get(-1, 1), range0.get(0, 1)),
                  min(range0.get(-2, 1) if left_len < 0 else 0,
                      range0.get(1, 1) if right_len > 0 else 0))
    max_pos = max(max(range1.get(-1, -1), range1.get(0, -1)),
                  max(range1.get(-2, -1) if left_len < 0 else 0,
                      range1.get(1, -1) if right_len > 0 else 0))
    return pos, right_len, left_len, min_pos, max_pos


def _module_info(name, table):
    """模块文件名 → 尺寸/种类。表里既有精确键也有 `_building_20_20` 这种后缀键。"""
    stem = (name or "").split("/")[-1]
    if stem.endswith(".module"):
        stem = stem[:-len(".module")]
    if stem in table:
        return stem, table[stem]
    for key, info in table.items():
        if key.startswith("_") and stem.endswith(key):
            return stem, info
    return stem, None


def _street_cells(matrix, cells_in):
    grid_keys = [c["slot"] for c in cells_in if isinstance(c.get("slot"), int)]
    pos, _rl, _ll, min_pos, max_pos = street_layout(grid_keys)
    out = []
    unknown = 0
    for cell in cells_in:
        slot = cell.get("slot")
        if not isinstance(slot, int):
            unknown += 1
            continue
        i, j, v = street_demangle(slot)
        stem, info = _module_info(cell.get("name"), STREET_MODULE)
        if info is None:
            unknown += 1
            continue
        hx, hy = info["size"][0] / 2.0, info["size"][1] / 2.0
        # 沿站场方向：j × 10 m；站台还在自己那一列上
        cx, cy = pos.get(i), j * STREET_CELL_L
        at_min_end = (j == 0)      # 出入口都落在站场两端：j=0 是"下侧"，其余是"上侧"
        if v in (STREET_VAR["passenger_platform"], STREET_VAR["cargo_platform"]):
            if cx is None:
                unknown += 1
                continue
        elif i == STREET_ENTRANCE_I:
            # 哨兵列：横跨站场两端
            cx = 0.0
            cy = (min_pos * STREET_CELL_L - STREET_ENTRANCE_OFF if at_min_end
                  else max_pos * STREET_CELL_L + STREET_ENTRANCE_OFF)
        else:
            if cx is None:
                unknown += 1
                continue
            offs = (STREET_PAX_HALF if v == STREET_VAR["passenger_platform"]
                    else STREET_CARGO_HALF) * (1 if i >= 0 else -1)
            cx += offs
            cy = (min_pos * STREET_CELL_L - STREET_ENTRANCE_OFF if at_min_end
                  else max_pos * STREET_CELL_L + STREET_ENTRANCE_OFF)
        poly = poly_rect(matrix, cx, cy, hx, hy)
        if poly is None:
            continue
        item = {"k": info["kind"], "m": cell.get("name"), "ij": [i, j], "poly": poly}
        if info.get("cargo"):
            item["cargo"] = True
        if info["kind"] == "entrance":
            # 出入口要带**方向**（用户 2026-10-02：用道路交通箭头把"进/出/双向"画出来）。
            # `dir` 取自模块文件名；箭头朝向由几何定 —— 出入口在站场端头，
            # 外侧就是站场外面：下侧端（j=0）朝 −y，上侧端朝 +y。
            d = entrance_dir(stem)
            if d:
                outward = apply_transf_dir(matrix, 0.0, -1.0 if at_min_end else 1.0)
                item["dir"] = d
                if d == "in":
                    item["arrow"] = [-outward[0], -outward[1]]      # 从外往里
                else:
                    item["arrow"] = outward                          # 出 / 双向都按"朝外"画轴
        out.append(item)
    note = "真实世界坐标（%d 格；x 由累积布局算出，格长 10 m）" % len(out)
    if unknown:
        note += "，另有 %d 格未识别" % unknown
    return out, note


# ════════════════════════════════════════════════════════════════════════════
#  码头 —— slotId 与坐标
# ════════════════════════════════════════════════════════════════════════════
#
# 出处：`station/water/harbor_modular.con` 的 `MangleId` / `DemangleId` + `slotDef` 表。
#
#   slotId = 1000000×(i+100) + 100×(j+100) + facing
#
# 🔴 **`offset` / `shift` 是「带正负号的四元素数组」，不是一个标量**：
#    四个朝向各一个值，写成标量会让坐标整体偏一个网格（12.5 m）。
#    实测踩过 —— 而且偏得不够大时"残差仍为负"，**只看是否越界抓不住**。
WATER_GRID = 12.5


def _water_sym(k):
    return [k * WATER_GRID, -k * WATER_GRID, -k * WATER_GRID, k * WATER_GRID]


def _water_shift():
    return [-0.5 * WATER_GRID] * 4


WATER_SLOTDEF = {
    "50_12":        dict(f=[0, 1, 2, 3],     off=_water_sym(0.8), ang=[90, 180, 270, 0], shf=[0.0] * 4),
    "50_12_flip":   dict(f=[4, 5, 6, 7],     off=_water_sym(0.3), ang=[180, 270, 0, 90], shf=_water_shift()),
    "100_25":       dict(f=[8, 9, 10, 11],   off=_water_sym(0.8), ang=[90, 180, 270, 0], shf=_water_shift()),
    "100_25_flip":  dict(f=[12, 13, 14, 15], off=_water_sym(0.3), ang=[180, 270, 0, 90], shf=_water_shift()),
    "100_50":       dict(f=[16, 17, 18, 19], off=_water_sym(0.8), ang=[90, 180, 270, 0], shf=_water_shift()),
    "100_50_flip":  dict(f=[20, 21, 22, 23], off=_water_sym(0.3), ang=[180, 270, 0, 90], shf=_water_shift()),
    "50_50":        dict(f=[24, 25, 26, 27], off=_water_sym(0.8), ang=[90, 180, 270, 0], shf=_water_shift()),
    "50_50_flip":   dict(f=[28, 29, 30, 31], off=_water_sym(0.3), ang=[180, 270, 0, 90], shf=_water_shift()),
    "50_12_pier":   dict(f=[36, 37, 38, 39], off=_water_sym(0.3), ang=[180, 270, 0, 90], shf=_water_shift()),
    "100_12_pier":  dict(f=[44, 45, 46, 47], off=_water_sym(0.3), ang=[180, 270, 0, 90], shf=_water_shift()),
    "12_12":        dict(f=[48, 49, 50, 51], off=_water_sym(0.8), ang=[90, 180, 270, 0], shf=[0.0] * 4),
}
# facing 32~35 / 40~43 = 未翻转的栈桥，`.con` 里被注释掉 ⇒ 这些槽位根本不存在
WATER_NO_SLOT = set(range(32, 36)) | set(range(40, 44))

# 模块真实占地（宽 × 深，米）—— 量自 `model.zip` 里 `.mdl` 的 `boundingInfo`。
WATER_MODULE = {
    "passenger_dock_50_12":    dict(size=(48.0, 9.8),   kind="platform"),
    "cargo_dock_50_12":        dict(size=(47.6, 10.1),  kind="platform", cargo=True),
    "passenger_dock_100_25":   dict(size=(97.6, 22.6),  kind="platform"),
    "cargo_dock_100_25":       dict(size=(97.6, 22.6),  kind="platform", cargo=True),
    "passenger_dock_50_50":    dict(size=(50.0, 50.0),  kind="platform"),
    "cargo_dock_50_50":        dict(size=(50.0, 50.0),  kind="platform", cargo=True),
    "passenger_dock_50_50_2":  dict(size=(50.0, 50.0),  kind="platform"),
    "cargo_dock_50_50_2":      dict(size=(50.0, 50.0),  kind="platform", cargo=True),
    "passenger_dock_100_50":   dict(size=(100.0, 50.0), kind="platform"),
    "cargo_dock_100_50":       dict(size=(100.0, 50.0), kind="platform", cargo=True),
    "passenger_dock_100_50_2": dict(size=(100.0, 50.0), kind="platform"),
    "cargo_dock_100_50_2":     dict(size=(100.0, 50.0), kind="platform", cargo=True),
    "medium_pier":             dict(size=(100.0, 12.5), kind="pier"),
    "small_pier":              dict(size=(50.0, 12.5),  kind="pier"),
    # ⚠️ 行人出入口的模型是**贴地 decal**（实测包围盒 1×1 m，没有真实占地）。
    #    这里按**一格网格（12.5 m）**画，纯粹是为了在地图上看得见 —— 不代表真实占地。
    "pedestrian_entrance":     dict(size=(WATER_GRID, WATER_GRID), kind="entrance", decal=True),
}


def water_demangle(sid):
    facing = sid % 100
    t = (sid - facing) // 100
    return t // 10000 - 100, t % 10000 - 100, facing


def water_local(sid):
    """码头槽位 → (局部 x, 局部 y, 朝向°)。认不出返回 None。"""
    ci, cj, facing = water_demangle(sid)
    if facing in WATER_NO_SLOT:
        return None
    for d in WATER_SLOTDEF.values():
        if facing in d["f"]:
            t = facing % 4 + 1          # 段内第几个朝向（1..4）
            ofs, shf, rot = d["off"][t - 1], d["shf"][t - 1], d["ang"][t - 1]
            if t in (1, 3):
                x = (ci + 0.5) * WATER_GRID + shf
                y = (cj + 0.5) * WATER_GRID + ofs * 0.5
            else:
                x = (ci + 0.5) * WATER_GRID + ofs * 0.5
                y = (cj + 0.5) * WATER_GRID + shf
            return x, y, float(rot)
    return None


def _water_cells(matrix, cells_in):
    out = []
    unknown = 0
    for cell in cells_in:
        slot = cell.get("slot")
        if not isinstance(slot, int):
            unknown += 1
            continue
        loc = water_local(slot)
        stem, info = _module_info(cell.get("name"), WATER_MODULE)
        if loc is None or info is None:
            unknown += 1
            continue
        hx, hy = info["size"][0] / 2.0, info["size"][1] / 2.0
        poly = poly_rect(matrix, loc[0], loc[1], hx, hy, loc[2])
        if poly is None:
            continue
        ci, cj, facing = water_demangle(slot)
        item = {"k": info["kind"], "m": cell.get("name"), "ij": [ci, cj], "poly": poly}
        if info.get("cargo"):
            item["cargo"] = True
        if info["kind"] == "entrance":
            # 码头的行人出入口**没有进/出之分**（整个 mod 只有 `pedestrian_entrance`
            # 这一个模块，没有对应的 exit）⇒ 标双向；箭头轴取模块自己的朝向。
            d = entrance_dir(stem)
            rad = math.radians(loc[2])
            item["dir"] = d or "both"
            item["arrow"] = apply_transf_dir(matrix, math.cos(rad), math.sin(rad))
        out.append(item)
    note = "真实世界坐标（%d 格；格 12.5 m，朝向取自 .con 的 slotDef 表）" % len(out)
    if unknown:
        note += "，另有 %d 格未识别" % unknown
    return out, note


# ════════════════════════════════════════════════════════════════════════════
#  机场 —— slotId 与坐标
# ════════════════════════════════════════════════════════════════════════════
#
# 出处：`station/air/airport.con`（大机场）与 `station/air/airfield.con`（小机场）的
#      `updateFn` —— 两者**显式构造 `result.slots`，坐标是写死的常数公式**。
#
#   slotId = 按模块类型分段的基址 + 连续序号 k
#
# 🔴 **两套 `.con` 的编号空间完全不同**（小机场带 10000000 偏移），
#    所以必须先看建筑用的是哪个 `.con`（探针的 `construction.file_name` 里有）。
# 🔴 **不能用 `createTemplateFn` 推布局**：模板给首个站台 `terminal1SlotId + 6`，
#    实测是 `+16/+19/+22`（玩家后来改过）⇒ **只认实际 slotId**。
AIR_AP = dict(taxiwayStartX=-250.0, taxiwayEndX=250.0, offset=40.0, slotDistance=20.0,
              numSlots=25, taxiDistance=60.0, runway1YCoord=90.0, runway2YCoord=149.0,
              mainBuildingSize=(120.0, 110.0), hangarSize=(80.0, 110.0),
              terminalSize=(60.0, 110.0), slotHeight=110.0)
AIR_AP["limitStart"] = AIR_AP["taxiwayStartX"] - AIR_AP["offset"]     # −290
AIR_AP["limitEnd"] = AIR_AP["taxiwayEndX"] + AIR_AP["offset"]         # +290
# 交给 MakeAllSlots 的是 *_BackY；模块中心 = BackY ± 尺寸/2（y 符号踩过一次，见报告 §4.3）
AIR_AP["modules1BackY"] = (AIR_AP["runway1YCoord"] - AIR_AP["taxiDistance"] - 30.0
                           - AIR_AP["slotHeight"])                    # −110
AIR_AP["modules2BackY"] = (AIR_AP["runway2YCoord"] + AIR_AP["taxiDistance"] + 30.0
                           + AIR_AP["slotHeight"])                    # +349
AIR_AP["group1_y"] = AIR_AP["modules1BackY"] + AIR_AP["mainBuildingSize"][1] / 2.0   # −55
AIR_AP["group2_y"] = AIR_AP["modules2BackY"] - AIR_AP["mainBuildingSize"][1] / 2.0   # +294

# 模块行：(组1 基址, 组2 基址, k 范围, x 起点, 尺寸, 跳过 k) —— 尺寸是 `.con` 里的槽位盒
AIR_GROUPS = {
    "main_building":  dict(base1=1000,  base2=1500,  kmin=0, kmax=25, x0=AIR_AP["taxiwayStartX"],
                           size=AIR_AP["mainBuildingSize"], kind="building"),
    "hangar":         dict(base1=2000,  base2=2500,  kmin=0, kmax=25, x0=AIR_AP["taxiwayStartX"],
                           size=AIR_AP["hangarSize"], kind="building", skip=(1, 24)),
    "terminal":       dict(base1=70000, base2=75000, kmin=2, kmax=22,
                           x0=AIR_AP["taxiwayStartX"] + AIR_AP["slotDistance"] / 2.0,
                           size=AIR_AP["terminalSize"], kind="building"),
    "terminal_cargo": dict(base1=80000, base2=85000, kmin=2, kmax=22,
                           x0=AIR_AP["taxiwayStartX"] + AIR_AP["slotDistance"] / 2.0,
                           size=AIR_AP["terminalSize"], kind="building", cargo=True),
}
# 单例槽位：(种类, x, y, 朝向°, 尺寸, kind)
# 🔴 第二跑道用**实测条带宽度 26 m**，不用 `.con` 的槽位盒（540×60）——
#    槽位盒是"这块地归谁"的范围，比看得见的跑道宽一倍多；
#    按槽位盒画会和旁边那条跑道贴到一起（2026-10-02 出图时一眼看出来）。
AIR_RUNWAY_W = 26.0        # 量自 `era_c_sm_runway.mdl`（552.5 × 26.1）
AIR_TAXIWAY_W = 20.0
AIR_SINGLES = {
    8000: ("2nd_runway", 0.0, AIR_AP["runway2YCoord"], 0.0, (540.0, AIR_RUNWAY_W), "runway"),
    8050: ("terminal_B", 0.0, AIR_AP["runway2YCoord"] + AIR_AP["taxiDistance"], 0.0,
           (500.0, 40.0), "apron"),
    9000: ("landing", AIR_AP["limitEnd"] - 5, AIR_AP["runway1YCoord"], 0.0, (80.0, 30.0), "other"),
    9001: ("landing", AIR_AP["limitStart"] + 5, AIR_AP["runway1YCoord"], 180.0, (80.0, 30.0), "other"),
    9002: ("landing", AIR_AP["limitStart"] + 5, AIR_AP["runway2YCoord"], 180.0, (80.0, 30.0), "other"),
    9003: ("landing", AIR_AP["limitEnd"] - 5, AIR_AP["runway2YCoord"], 0.0, (80.0, 30.0), "other"),
}
# 场地（`.con` 里的常数）：地面矩形 + 第一条跑道 + 两条滑行道。
# 第二条跑道不在这里 —— 它由 `8000` 那个槽位画，重复画会叠在一起。
AIR_SITE = [
    ("apron",   0.0, 119.5, (580.0, 239.0)),            # x∈[−290,290] y∈[0,239]（`.con` 的场地矩形）
    ("runway",  0.0, AIR_AP["runway1YCoord"], (560.0, AIR_RUNWAY_W)),   # x∈[−280,280]
    ("taxiway", 0.0, 30.0, (500.0, AIR_TAXIWAY_W)),     # x∈[−250,250]
    ("taxiway", 0.0, 209.0, (500.0, AIR_TAXIWAY_W)),
]
AIR_AF = dict(offset=10000000, defSpace=25.0, defNumSlots=10, slotStartXCoord=-125.0,
              slotsYCoord=-83.0)
AIR_AF_BASES = {AIR_AF["offset"] + 1000: ("main_building", "building"),
                AIR_AF["offset"] + 2000: ("hangar", "building"),
                AIR_AF["offset"] + 70000: ("terminal", "building")}


def air_local(con_file, slot_id):
    """机场槽位 → dict(kind, x, y, yaw, size, name)；认不出返回 None。"""
    name = (con_file or "").split("/")[-1]
    if name.endswith("airport.con"):
        if slot_id in AIR_SINGLES:
            kind_name, x, y, yaw, size, kind = AIR_SINGLES[slot_id]
            return dict(name=kind_name, x=x, y=y, yaw=yaw, size=size, kind=kind)
        for gname, g in AIR_GROUPS.items():
            for gid, base in ((1, g["base1"]), (2, g["base2"])):
                k = slot_id - base
                if not (g["kmin"] <= k <= g["kmax"]) or k in g.get("skip", ()):
                    continue
                y = AIR_AP["group1_y"] if gid == 1 else AIR_AP["group2_y"]
                return dict(name=gname, x=g["x0"] + AIR_AP["slotDistance"] * k, y=y,
                            yaw=(0.0 if gid == 1 else 180.0), size=g["size"],
                            kind=g["kind"], cargo=g.get("cargo"), group=gid, k=k)
        return None
    if name.endswith("airfield.con"):
        for base, (gname, kind) in AIR_AF_BASES.items():
            k = slot_id - base
            if 0 <= k <= AIR_AF["defNumSlots"]:
                return dict(name=gname, x=AIR_AF["defSpace"] * k + AIR_AF["slotStartXCoord"],
                            y=AIR_AF["slotsYCoord"], yaw=0.0,
                            size=(AIR_AF["defSpace"], AIR_AF["defSpace"]), kind=kind)
        return None
    return None


def _air_cells(matrix, cells_in, con_file):
    out = []
    unknown = 0
    has_b = any(c.get("slot") == 8050 for c in cells_in)
    # 场地先铺底（排序在最后统一做，这里只管生成）
    if "airport" in (con_file or ""):
        for kind, sx, sy, (size_x, size_y) in AIR_SITE:
            if kind in ("runway", "taxiway") and sy > 200 and not has_b:
                continue           # 没有第二跑道就没有第二条滑行道/跑道
            poly = poly_rect(matrix, sx, sy, size_x / 2.0, size_y / 2.0)
            if poly:
                out.append({"k": kind, "m": None, "ij": None, "poly": poly})
    for cell in cells_in:
        slot = cell.get("slot")
        if not isinstance(slot, int):
            unknown += 1
            continue
        loc = air_local(con_file, slot)
        if loc is None:
            unknown += 1
            continue
        poly = poly_rect(matrix, loc["x"], loc["y"], loc["size"][0] / 2.0,
                         loc["size"][1] / 2.0, loc["yaw"])
        if poly is None:
            continue
        item = {"k": loc["kind"], "m": cell.get("name"), "ij": None, "poly": poly,
                "slot_name": loc["name"]}
        if loc.get("cargo"):
            item["cargo"] = True
        out.append(item)
    note = ("真实世界坐标（%d 格；槽位盒取自 .con 常数公式，跑道/滑行道按 .mdl 实测条带宽度画）"
            % len(out))
    if not has_b:
        note += "；本场无第二跑道，场地矩形仍按 .con 的双跑道形态取值"
    if unknown:
        note += "，另有 %d 格未识别" % unknown
    return out, note


def apply_transf_dir(matrix, lx, ly):
    """只过矩阵的**线性部分**（不带平移），把一个**方向**从局部换到世界，返回单位向量。

    位置要带平移，方向不能带 —— 拿位置那把算法算方向，箭头会歪。
    """
    dx = matrix[0] * lx + matrix[4] * ly
    dy = matrix[1] * lx + matrix[5] * ly
    n = math.hypot(dx, dy)
    if n < 1e-9:
        return [0.0, 0.0]
    return [round(dx / n, 4), round(dy / n, 4)]


def entrance_dir(stem):
    """出入口模块名 → 行人往哪走：`in` 进 / `out` 出 / `both` 双向。

    依据是**模块文件名本身**（游戏里 `entrance.module` / `exit.module` /
    `entrance_exit.module` 是三个不同的文件，不是同一个的变体）——
    这比按变体号猜可靠。认不出返回 None。
    """
    s = (stem or "").lower()
    if "entrance_exit" in s:          # 必须先判它，否则会被下面的 entrance 抢先命中
        return "both"
    if "pedestrian_entrance" in s:
        return "both"                 # 码头只有这一个模块，没分出/入口 ⇒ 双向
    if "entrance" in s or "entry" in s:
        return "in"
    if "exit" in s:
        return "out"
    return None


def build_cells(entry, preview=None):
    """四类站的模块格子 → 前端能直接画的多边形（**真实世界坐标**）。

    没采到格子时返回空表 —— 上层退化成"只画外围大框"。
    `preview` 是作者那层的 station-previews 数据，只对**火车站**的站房纵向落点有用
    （见下面 along_scale 的说明）。
    """
    construction = entry.get("construction") or {}
    grid = construction.get("module_grid") or {}
    cells_in = grid.get("cells")
    if not cells_in:
        return [], "探针没采到模块清单"

    # 🔴 局部坐标 → 世界坐标靠这份矩阵，**它是有值的**：早先注释里写"探针没导出 transf
    #    （是 null）"是误判 —— bridge/station-struct-probe.json 里 construction.transf.
    #    one_based 就是完整的 4×4 **列主序**矩阵（用引擎自己的 scope.direction 反证过）。
    matrix = (construction.get("transf") or {}).get("one_based")
    if not matrix or len(matrix) < 15:
        return [], "没有 construction.transf，格子换不出世界坐标"

    # 三类站各走各的反解（公式来源见上面各自的段落）
    kind = entry.get("kind")
    if kind == "water":
        return _water_cells(matrix, cells_in)
    if kind == "street":
        return _street_cells(matrix, cells_in)
    if kind == "air":
        return _air_cells(matrix, cells_in, construction.get("file_name")
                          or entry.get("construction_file"))
    if kind != "rail":
        return [], "kind=%s 的格子反解尚未接入" % kind

    platforms = []   # (kind, i, j, 局部 x 偏移, 模块名)
    buildings = []   # (diff, 模块名)
    stairs = []      # (diff, 模块名)
    unknown = 0
    for cell in cells_in:
        slot = cell.get("slot")
        if not isinstance(slot, int):
            unknown += 1
            continue
        base = rail_base_of(slot)
        if base is None:
            unknown += 1
            continue
        diff = slot - base
        name = cell.get("name")
        if base == RAIL_BUILDING_BASE:
            buildings.append((diff, name))
        elif base == RAIL_STAIRS_BASE:
            stairs.append((diff, name))
        else:
            kind, ox, _oz = RAIL_PLATFORM_BASES[base]
            i, j = decode_grid(diff)
            platforms.append((kind, i, j, ox, name))
    if not platforms and not buildings:
        return [], "没有能反解的格子"

    # 站台列号 i 的范围 —— 主建筑与楼梯要贴在**整个站场**的最外侧一列之外。
    # 🔴 用全局范围而不是"按排 j"：按排取的话，某排恰好没有靠边的轨道时，
    #    站房就会往站场里缩、压到别排的轨道上（2026-10-02 实测就是"把轨道盖住了"）。
    all_i = [i for _kind, i, _j, _ox, _name in platforms]
    col_min_all = min(all_i) if all_i else 0
    col_max_all = max(all_i) if all_i else 0

    # ── 站房沿站场方向的收放 ────────────────────────────────────────────────
    # 🔴 按 slotId 网格推出来的站台纵向长度会**偏长**：广州北站推出来是 320 m
    #    （j ∈ [−1, 7] 共 8 个间隔 × 40 m），而引擎给的站台中心线只有 **209 m**
    #    （`station-previews` 里量出来的，那才是权威）。站房要是顺着网格排，
    #    就会伸出站台两端、看着"跑到轨道前面去"（用户 2026-10-02 三次反馈）。
    #    ⇒ 拿"真实站台长度 / 网格长度"当比例，把站房沿站场方向一起收一下。
    along_scale = 1.0
    base_j = 0.0
    plat_j = [j for _kind, _i, j, _ox, _name in platforms]
    if plat_j:
        base_j = min(plat_j) * RAIL_CELL_L
    if preview and plat_j:
        scope = preview.get("scope") or {}
        org, direc = scope.get("origin"), scope.get("direction")
        lines = [pt for pf in (preview.get("platforms") or [])
                 for pt in (pf.get("platform_centerline") or [])]
        if org and direc and len(lines) >= 2:
            vals = [(x - org["x"]) * direc["x"] + (y - org["y"]) * direc["y"]
                    for x, y in lines]
            real_len = max(vals) - min(vals)
            grid_len = (max(plat_j) - min(plat_j)) * RAIL_CELL_L
            if real_len > 1.0 and grid_len > 1.0:
                # **只缩不放**：网格推算只会偏长；万一某个站反着偏，放大就会把
                # 站房推出引擎占地框（实测有 3 座站这样越界）。
                along_scale = min(1.0, real_len / grid_len)

    out = []

    def emit(kind, module, lx, ly, half_x, half_y, ij=None):
        # 🔴 **四个角都要过一遍矩阵**，不能只转中心点、再拼一个"正的"矩形：
        #    站点朝向不一定是 0/90/180/270（实测 Hanoi 那站整个是斜的），只转中心点的话
        #    格子自己还是方正、跟站场网格错开 —— 画出来就是"一堆歪七扭八的方块对不上"
        #    （用户 2026-10-02 指出）。矩形是刚性变换，四角一过矩阵就自然贴合站场方向。
        poly = []
        for cx, cy in ((lx - half_x, ly - half_y), (lx + half_x, ly - half_y),
                       (lx + half_x, ly + half_y), (lx - half_x, ly + half_y)):
            world = apply_transf(matrix, cx, cy)
            if world is None:
                return
            poly.append([round(world[0], 2), round(world[1], 2)])
        # ij 是网格坐标 —— 前端画"站房带"时靠它把同一排的格子按顺序连起来，
        # 不然得自己去猜点与点之间的先后（站场可能是斜的，按 x 排序会乱）。
        out.append({"k": kind, "m": module,
                    "ij": list(ij) if ij else None,
                    "poly": poly})

    for kind, i, j, ox, name in platforms:
        # 局部坐标 = (5·i + 偏移, 40·j)：5 m = platformWidth，40 m = platformLength
        emit(kind, name, RAIL_CELL_W * i + ox, RAIL_CELL_L * j,
             RAIL_CELL_W / 2, RAIL_PLAT_HALF_L, (i, j))

    def emit_box(kind, module, x0, x1, y0, y1, ij=None, cargo=None):
        """按"槽位坐标系里的角点范围"画矩形 —— 四角都过矩阵，矩形跟着站场转。"""
        poly = []
        for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            world = apply_transf(matrix, cx, cy)
            if world is None:
                return
            poly.append([round(world[0], 2), round(world[1], 2)])
        cell = {"k": kind, "m": module,
                "ij": list(ij) if ij else None,
                "poly": poly}
        if cargo is not None:
            cell["cargo"] = cargo     # 前端按它给客运/货运站房上不同颜色
        out.append(cell)

    # 每排平台的列范围 —— 楼梯要用（楼梯的槽位 ID 只编码了 j，没编码列号）
    row_min, row_max = {}, {}
    for _k2, i2, j2, _ox2, _nm2 in platforms:
        row_min[j2] = min(row_min.get(j2, i2), i2)
        row_max[j2] = max(row_max.get(j2, i2), i2)

    for diff, name in buildings:
        decoded = decode_building(diff)
        if decoded is None:
            continue      # 位置解不出合理值的槽位（见 decode_building 里的说明）
        i, j, k, o, front = decoded
        bx0, bx1, by0, by1 = building_box_of(name)
        # 沿站场方向的落点：`j×40 + k×10`（从属楼再多 5 m，见下），
        # 再绕"站台格起点"按真实站台长度收一下（along_scale，见上面那段说明）。
        # 🔴 **从属楼（o=5，side_building_size1）走的是 `tf1`，y 比主楼高 5 m**
        #    —— `.con` 第 698/732 行给 tf1 的是 `j*platformLength + k*10 + 5`，tf2 才是 `+0`。
        #    以前统一按 +0 画，从属楼会比实际低 5 m。
        bump = 5.0 if o == 5 else 0.0
        base_y = base_j + (RAIL_CELL_L * j + 10.0 * k + bump - base_j) * along_scale
        # 🔴 **站房的槽位原点 x，照抄 `.con` 的 `pos`**（`modular_station.con:688-733`）：
        #      回侧：`minDist = -minS[j]*platformWidth`；`pos = mainBuildingPosition - (minDist,0,0)`
        #            ⇒ `pos.x = minS[j]*5 − 10`
        #      前侧：`maxDist = -maxS[j]*platformWidth`；`pos = mainBuildingPosition - (maxDist−20,0,0)`
        #            ⇒ `pos.x = maxS[j]*5 + 10`
        #    而 **`minS[j]` / `maxS[j]` 就是槽位 ID 里编码的那个 `i`** —— `.con` 调的是
        #    `GetId(mainBuildingTag, throughBackTag, minS[j], j, k)`，所以直接用它，
        #    **不需要再去站场里找"最外一列"**。
        #
        #    ⚠️ 之前那版（`-10 - col_min_all*5 - bx1`）错在两处，2026-10-02 对着 `.con` 改掉：
        #      ① `−10` 本来就是 `mainBuildingPosition`，房子自身的 `bx1`（≈7.5）已经吃掉一截，
        #         把它当"外移距离"再用一次 ⇒ 整栋又多挪了 7.5 m；
        #      ② 用了**全局**列范围，而 `.con` 用的是**按排**的 `minS[j]` / `maxS[j]` ——
        #         某排的站台列不从 0 开始时，站房会整片挪错（列号越大偏得越多）。
        #    前侧在 `.con` 里还有 `rotZTransl(180)`，效果是把房子的 x 区间镜像成
        #    `[-bx1, -bx0]`，所以这里写成 `pos_x − bx1 … pos_x − bx0`。
        if front:
            pos_x = i * RAIL_CELL_W + 10.0
            x0, x1 = pos_x - bx1, pos_x - bx0
        else:
            pos_x = i * RAIL_CELL_W - 10.0
            x0, x1 = pos_x + bx0, pos_x + bx1
        emit_box("building", name, x0, x1,
                 base_y + by0, base_y + by1, (i, j),
                 cargo=is_cargo_module(name))

    for diff, name in stairs:
        # 楼梯：`id = 9400000 + 10*j + {0,1}`；`.con` 给的是
        #   o=1 → `(maxS[j]*5 + 2.5, j*40)`；o=0 → `(minS[j]*5 − 2.5, j*40)`
        # ⇒ 同样要用**按排**的列范围，不能拿全局的凑。
        j, o = decode_grid(diff)[1], diff % 10
        col = (row_max.get(j, col_max_all) if o == 1 else row_min.get(j, col_min_all))
        lx = RAIL_CELL_W * col + (2.5 if o == 1 else -2.5)
        emit("stairs", name, lx, RAIL_CELL_L * j, RAIL_CELL_W / 2, RAIL_PLAT_HALF_L, (0, j))

    # 🔴 输出前按"先铺底、后盖顶"排序。前端按数组顺序画，后画的压先画的。
    #    顶棚垫最下（它跟站台同格，只用来勾出站台范围），站房压最上。
    # 🔴 输出前**按"先铺底、后盖顶"排序** —— 前端（和核对报告）都按数组顺序画，
    #    后画的压先画的。机场的场地/跑道必须垫底，站房必须盖在最上面。
    layer_order = {"apron": 0, "runway": 1, "taxiway": 2, "roof": 3, "track": 4,
                   "pier": 5, "platform": 6, "stairs": 7, "entrance": 7,
                   "other": 8, "building": 9}
    out.sort(key=lambda item: layer_order.get(item["k"], 6))
    note = "真实世界坐标（%d 格，用 construction.transf 换算）" % len(out)
    if unknown:
        note += "，另有 %d 格未识别" % unknown
    return out, note


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


# ── 结构核对报告（--report） ────────────────────────────────────────────────
#
# 把每座火车站的模块格子**按世界坐标**画成一张小平面图。用途有两个：
#   · 不打开游戏/地图也能一眼看出"站房在哪、站台几股、轨道怎么排"；
#   · 数据出问题时先看它 —— 形状拧了就是 slotId 解错，形状对但地图上没有就是前端的事。
#
# 这张图跟前端图层用的是**同一份 cells 数据**，所以它能当"前端渲染是否可信"的旁证。

REPORT_CELL_COLOR = {
    "platform": "#7fd4ff",
    "building": "#ffcf7a",
    "track": "#8fa3b8",
    "roof": "#8b7fd4",
    "stairs": "#c9a0ff",
    "pier": "#6fc3a8",
    "entrance": "#7fe3a0",
    "apron": "#48565f",
    "runway": "#39454e",
    "taxiway": "#5a6871",
    "other": "#9fb0bf",
}
REPORT_CELL_LABEL = {
    "platform": "站台 / 泊位", "building": "站房 / 航站楼", "track": "轨道",
    "roof": "顶棚", "stairs": "楼梯", "pier": "栈桥", "entrance": "出入口",
    "apron": "停机坪 / 场坪", "runway": "跑道", "taxiway": "滑行道", "other": "其它",
}
REPORT_ORDER = {"apron": 0, "runway": 1, "taxiway": 2, "roof": 3, "track": 4,
                "pier": 5, "platform": 6, "stairs": 7, "entrance": 7,
                "other": 8, "building": 9}

REPORT_HEAD = """<!doctype html><meta charset="utf-8"><title>TPF2 车站结构核对</title>
<style>
body{margin:0;background:#eef2f6;font-family:"Segoe UI","Microsoft YaHei",sans-serif;color:#1b1f24}
.wrap{max-width:1240px;margin:0 auto;padding:18px}
h1{font-size:20px;margin:10px 4px 4px}
p.lead{color:#5b6673;font-size:13px;margin:4px 8px 14px;line-height:1.7}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:0 8px 16px;font-size:13px;color:#3c4653}
.legend i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(370px,1fr));gap:14px}
.card{background:#fff;border:1px solid #d8dee6;border-radius:10px;padding:10px 10px 6px}
.card h2{font-size:14px;margin:0 0 2px;font-weight:600}
.card .sub{font-size:11px;color:#5b6673;margin:0 0 6px}
.card svg{width:100%;height:auto;display:block;background:#0d1117;border-radius:6px}
.card .foot{font-size:11px;color:#5b6673;margin:6px 0 0}
</style>
<div class="wrap">
<h1>TPF2 车站结构核对（模块格子 → 真实世界坐标）</h1>
<p class="lead">每格就是一个 <code>.module</code>。位置由各站型自己的 <code>.con</code> 反解出网格坐标，
乘格尺寸得局部坐标，再套探针里的 <code>construction.transf</code>（<b>列主序</b>）换到世界坐标：
<b>火车站</b> <code>基址 + 1000·i + 10·j</code>（格 5×40 m）；<b>汽车站</b>
<code>200000·(j+100) + 100·(i+100) + 变体</code>（x 由累积布局算，格长 10 m）；
<b>码头</b> <code>1000000·(i+100) + 100·(j+100) + 朝向</code>（格 12.5 m，朝向表给偏移）；
<b>机场</b> <code>按类型分段的基址 + 序号</code>（坐标是 <code>.con</code> 里的常数公式）。
<b>与地图图层用的是同一份数据。</b></p>
<div class="legend">__LEGEND__</div>
<div class="grid">"""

REPORT_TAIL = """</div></div>"""


def report_legend():
    order = ["platform", "pier", "track", "roof", "stairs", "apron", "runway", "taxiway", "building"]
    html = "".join('<span><i style="background:%s"></i>%s</span>'
                   % (REPORT_CELL_COLOR[k], REPORT_CELL_LABEL[k]) for k in order)
    # 出入口单独列（它按进/出/双向分色，还会叠方向箭头）
    html += ('<span><i style="background:%s"></i>出入口·进</span>'
             '<span><i style="background:%s"></i>出入口·出</span>'
             '<span><i style="background:%s"></i>出入口·双向（箭头＝行人方向）</span>'
             % (ENTRANCE_COLOR["in"], ENTRANCE_COLOR["out"], ENTRANCE_COLOR["both"]))
    return html


def report_svg(item, box_w=360.0, box_h=210.0, pad=10.0):
    cells = item.get("cells") or []
    if not cells:
        return ""
    xs = [p[0] for c in cells for p in c["poly"]]
    ys = [p[1] for c in cells for p in c["poly"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w = max(x1 - x0, 1.0)
    h = max(y1 - y0, 1.0)
    scale = min((box_w - 2 * pad) / w, (box_h - 2 * pad) / h)
    # y 轴翻转：世界坐标 y 向上，SVG 向下 —— 不翻就上下镜像
    off_x = pad + (box_w - 2 * pad - w * scale) / 2.0
    off_y = pad + (box_h - 2 * pad - h * scale) / 2.0

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f">'
             % (box_w, box_h)]
    for cell in sorted(cells, key=lambda c: REPORT_ORDER.get(c["k"], 2)):
        pts = []
        for px, py in cell["poly"]:
            sx = off_x + (px - x0) * scale
            sy = off_y + (y1 - py) * scale
            pts.append("%.1f,%.1f" % (sx, sy))
        fill = (ENTRANCE_COLOR.get(cell.get("dir"), REPORT_CELL_COLOR["entrance"])
                if cell["k"] == "entrance" else REPORT_CELL_COLOR.get(cell["k"], "#9fb0bf"))
        parts.append('<polygon points="%s" fill="%s" fill-opacity="0.85" '
                     'stroke="#04090e" stroke-width="0.5"/>'
                     % (" ".join(pts), fill))
        # 出入口：再叠一个方向箭头
        if cell["k"] == "entrance" and cell.get("arrow"):
            arrow = arrow_world(cell)
            if arrow:
                apts = []
                for px_, py_ in arrow:
                    apts.append("%.1f,%.1f" % (off_x + (px_ - x0) * scale,
                                               off_y + (y1 - py_) * scale))
                parts.append('<polygon points="%s" fill="%s" fill-opacity="0.9" '
                             'stroke="none"/>' % (" ".join(apts), ENTRANCE_ARROW))
    parts.append("</svg>")
    return "".join(parts)


KIND_LABEL = {"rail": "火车站", "street": "汽车站", "water": "码头", "air": "机场"}

# 出入口按「进 / 出 / 双向」分色 + 方向箭头 —— 与前端 station-struct.js 同一套判据与轮廓。
ENTRANCE_COLOR = {"in": "#5fd08a", "out": "#5fa8ff", "both": "#4fc9c0"}
ENTRANCE_ARROW = "#0b1117"
# 归一化箭头轮廓：横轴顺箭头方向，纵轴为垂直方向（±1 = 半长 / 半宽的极限）
ARROW_SINGLE = [(-1, -0.42), (0.42, -0.42), (0.42, -1.0), (1, 0),
                (0.42, 1.0), (0.42, 0.42), (-1, 0.42)]
ARROW_DOUBLE = [(-1, 0), (-0.42, -1.0), (-0.42, -0.42), (0.42, -0.42),
                (0.42, -1.0), (1, 0), (0.42, 1.0), (0.42, 0.42),
                (-0.42, 0.42), (-0.42, 1.0)]


def arrow_world(cell):
    """出入口格 → 箭头的世界坐标多边形（进/出单头、双向双头）。给核对报告用。"""
    d = cell.get("arrow")
    poly = cell.get("poly") or []
    if not d or len(poly) < 3:
        return None
    wx = [p[0] for p in poly]
    wy = [p[1] for p in poly]
    cx, cy = (min(wx) + max(wx)) / 2.0, (min(wy) + max(wy)) / 2.0
    half = min(max(wx) - min(wx), max(wy) - min(wy)) * 0.31
    if half <= 0.4:
        return None
    ux, uy = d[0], d[1]
    px, py = -uy, ux
    shape = ARROW_DOUBLE if cell.get("dir") == "both" else ARROW_SINGLE
    return [[cx + ux * (lx * half) + px * (ly * half * 0.62),
             cy + uy * (lx * half) + py * (ly * half * 0.62)] for lx, ly in shape]


def write_report(stations, path, per_kind=14):
    """每个站型各出前 `per_kind` 张图 —— 不然火车站的格子最多，会把其它三类挤没。"""
    rooms = [s for s in stations if s.get("cells")]
    cards = []
    for kind in ("rail", "street", "water", "air"):
        group = sorted([s for s in rooms if s.get("kind") == kind],
                       key=lambda s: -len(s["cells"]))
        for item in group[:per_kind]:
            kinds = {}
            for cell in item["cells"]:
                kinds[cell["k"]] = kinds.get(cell["k"], 0) + 1
            mix = " · ".join("%s %d" % (REPORT_CELL_LABEL.get(k, k), v)
                             for k, v in sorted(kinds.items(),
                                                key=lambda kv: REPORT_ORDER.get(kv[0], 9)))
            box = item["box"]
            cards.append(
                '<div class="card"><h2>%s</h2><p class="sub">%s ｜ 站 %s ｜ 占地 %.0f×%.0f m ｜ 共 %d 格</p>'
                '%s<p class="foot">%s</p></div>'
                % (item.get("name") or "（未配到站名）", KIND_LABEL.get(kind, kind),
                   item.get("id"), box["w"], box["h"], len(item["cells"]),
                   report_svg(item), mix))
    # 用 replace 而不是 % 格式化：CSS 里满是 `width:100%` 这类百分号，会跟格式化符打架
    html = REPORT_HEAD.replace("__LEGEND__", report_legend()) + "".join(cards) + REPORT_TAIL
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return len(cards)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", default=os.environ.get("TPF2_BRIDGE_DIR", DEFAULT_BRIDGE))
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--report", default=None,
                    help="另出一份结构核对 HTML（四类站各若干张平面图）；不填就不生成")
    args = ap.parse_args()

    probe_path = os.path.join(args.bridge, "station-struct-probe.json")
    stations_path = os.path.join(args.bridge, "layer-stations.json")
    for path in (probe_path, stations_path):
        if not os.path.exists(path):
            print("找不到：%s" % path, file=sys.stderr)
            return 1

    preview_dir = os.path.join(PROJECT_ROOT, "ui", "rail-map", "station-previews")
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
    skipped_files = {}      # 没能反解的站：construction_file → 个数（用来说明"不做的是哪几个站型"）

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

            # 作者那层的预览数据（站场坐标系 + 站台真实中心线），用来校正站房
            # 沿站场方向的落点；匹配不到站名时为 None，退回纯网格推算。
            preview_data = load_preview(preview_dir, station_ref)
            cells, cells_note = build_cells(entry, preview_data)
            if cells:
                cell_total += len(cells)
            elif cells_note:
                cell_skipped[kind] = cell_skipped.get(kind, 0) + 1
                key = entry.get("construction_file") or "（没有 construction_file）"
                skipped_files[key] = skipped_files.get(key, 0) + 1

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
    # 自检：格子的包围盒应当落在引擎占地框里（宽容 40 米 —— 格子按模块标称尺寸画，
    # 跟模型真实外轮廓差个几米到几十米都正常）。超太多说明 slotId 又解错了。
    over = []
    for item in out_stations:
        if not item["cells"]:
            continue
        xs = [p[0] for c in item["cells"] for p in c["poly"]]
        ys = [p[1] for c in item["cells"] for p in c["poly"]]
        bx, by = item["box"]["x"], item["box"]["y"]
        bw, bh = item["box"]["w"], item["box"]["h"]
        pad = 40.0
        if (min(xs) < bx - pad or max(xs) > bx + bw + pad
                or min(ys) < by - pad or max(ys) > by + bh + pad):
            over.append(item["id"])
    print("  自检：格子落在占地框内 %d / %d 座%s"
          % (len([s for s in out_stations if s["cells"]]) - len(over),
             len([s for s in out_stations if s["cells"]]),
             "" if not over else "，超出的是 %s" % over[:8]))
    if cell_skipped:
        # 反解只覆盖**游戏本体**的站型。剩下的是创意工坊站型（各作者自己写布局脚本、编码不同），
        # 按用户 2026-10-02 的决定分两类处理：
        #   🔚 **不做**：JQKA 货站 27、悬挂单轨 + skytrain 17（「结构太简单没有任何意义」）
        #   ⏳ **保留待做**：`ust`（Ultimate Station）2、`mus`（地下站）1
        #      —— 这两个是**原版模块化站的扩展**，结构并不简单，「以后可能要做结构」。
        print("  未反解（工坊站型）：%s" % cell_skipped)
        for f, n in sorted(skipped_files.items(), key=lambda kv: -kv[1]):
            tag = "保留待做" if ("ust.con" in f or "mus.con" in f) else "已决定不做"
            print("     %-56s %2d 座  %s" % (f, n, tag))
    if unmatched:
        print("  ⚠️ 没配到站名的 %d 个：%s" % (len(unmatched), unmatched[:6]))
    if args.report:
        count = write_report(out_stations, args.report)
        print("  核对报告：%s（%d 张平面图，四类站各若干）" % (args.report, count))
    print("⚠️ 这份是生成数据，已由 .gitignore 忽略，勿提交。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
