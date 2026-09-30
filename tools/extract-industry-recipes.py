#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从游戏本体的产业定义里抽出**配方**（原料 → 产品），生成 JSON 给地图前端用。

为什么要有这个
--------------
用户 2026-09-30 要求：「加工厂是一个或者两个原料生成一个产品，这个关系也要写出来」。
游戏地图上产业头顶就是一串图标加个箭头（`原料图标 > 产品图标`），前端要照着画，
就得先拿到这份关系表。

数据在哪
--------
游戏把建筑/产业定义打包在 `res/construction/construction.zip` 里，
产业是 `industry/<名字>.con`，共 16 个（另有 `industry/extension/` 是产业扩建件，不含配方）。
每个 `.con` 末尾的 `data()` 函数里有一段字面量配置：

    local stockListConfig = {
        stocks = { "PLASTIC", "STEEL", },                              -- 原料
        rule = { input = { {1,1} }, output = { GOODS = 1 }, capacity = 100 },   -- 产出
    }

- `stocks`   = 这个产业要**运进来**的货物（原料）。采集型产业这里是空的。
- `output`   = 它产出的货物（每种产业只有一种）。
- `capacity` = 库存上限。

⚠️ `.con` 文件本身很大（加工厂那份 388 KB，绝大部分是模型摆放矩阵），
   但这段配置是**字面量**、格式固定，用正则取就够了，不需要跑 Lua。

产物：`ui/rail-map/industry-recipes.json`。
"""
import json
import os
import re
import sys
import zipfile

GAME_DIR = r"E:\SteamLibrary\steamapps\common\Transport Fever 2"
CONSTRUCTION_ZIP = os.path.join(GAME_DIR, "res", "construction", "construction.zip")
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "ui", "rail-map", "industry-recipes.json")

# 只取顶层的 industry/*.con（这一层正则排除了 industry/extension/field.con）
INDUSTRY_PATH = re.compile(r"industry/[a-z_]+\.con$")


def parse_amounts(fragment: str):
    """把 `1,1` / `2` / 空 这种内层数组解成 [1,1] / [2] / []。

    `.con` 里 `input = { { 1,1 } }` 的**内层**数组就是一次生产要消耗的量，
    按位置对应 `stocks` 里的原料 —— `stocks = {"IRON_ORE","COAL"}` + `{{2,2}}`
    就是「2 铁矿石 + 2 煤」。
    """
    out = []
    for piece in fragment.split(","):
        piece = piece.strip()
        if piece:
            try:
                out.append(int(piece))
            except ValueError:
                pass
    return out


def parse_recipe(text: str):
    """从一份 .con 里取 (原料, 原料用量, 产品, 产品用量, 容量)。取不到返回 None。"""
    block = re.search(r"local stockListConfig\s*=\s*\{(.+?)\n\s*\}", text, re.S)
    if not block:
        return None
    body = block.group(1)

    stocks_match = re.search(r"stocks\s*=\s*\{([^}]*)\}", body)
    # 内外两层花括号：外层的每个元素是一次配方（实测都只有 1 个），内层是用量表
    input_match = re.search(r"input\s*=\s*\{\s*\{([^{}]*)\}\s*\}", body)
    output_match = re.search(r"output\s*=\s*\{([^}]*)\}", body)
    capacity_match = re.search(r"capacity\s*=\s*(\d+)", body)

    def names(fragment):
        # 片段形如 `"PLASTIC", "STEEL",` 或 `GOODS = 1,`，两种都要能吃
        out = []
        for piece in fragment.split(","):
            piece = piece.split("=")[0].strip().strip('"').strip()
            if piece:
                out.append(piece)
        return out

    stocks = names(stocks_match.group(1)) if stocks_match else []
    raw_amounts = parse_amounts(input_match.group(1)) if input_match else []

    # 用量与原料**按位置对应**；长度不齐时缺的按 1 算（宁可报小，也不漏报一种原料）
    input_amounts = [raw_amounts[i] if i < len(raw_amounts) else 1 for i in range(len(stocks))]

    # 产出那边是 `GOODS = 1` 的键值形式，名字和数量一起取
    outputs, output_amounts = [], []
    if output_match:
        for name, amount in re.findall(r"([A-Z_]+)\s*=\s*(\d+)", output_match.group(1)):
            outputs.append(name)
            output_amounts.append(int(amount))

    return (
        stocks,
        input_amounts,
        outputs,
        output_amounts,
        int(capacity_match.group(1)) if capacity_match else None,
    )


def main() -> int:
    if not os.path.exists(CONSTRUCTION_ZIP):
        print("找不到游戏建筑定义包：%s" % CONSTRUCTION_ZIP)
        return 1

    archive = zipfile.ZipFile(CONSTRUCTION_ZIP)
    targets = sorted(n for n in archive.namelist() if INDUSTRY_PATH.match(n))

    recipes = {}
    for member in targets:
        key = os.path.basename(member)[:-4]        # goods_factory.con → goods_factory
        parsed = parse_recipe(archive.read(member).decode("utf-8", errors="replace"))
        if parsed is None:
            print("  ⚠️ %-24s 没解析出 stockListConfig，跳过" % key)
            continue
        inputs, input_amounts, outputs, output_amounts, capacity = parsed
        recipes[key] = {
            "inputs": inputs,
            "input_amounts": input_amounts,      # 与 inputs 一一对应的消耗量
            "outputs": outputs,
            "output_amounts": output_amounts,    # 与 outputs 一一对应的产出量
            "capacity": capacity,
        }

    # ── 自检：数量表必须跟名字表等长，且几个已知配方要对得上 ──────────────────
    problems = []
    for key, item in recipes.items():
        if len(item["inputs"]) != len(item["input_amounts"]):
            problems.append("%s 的原料用量表长度不齐" % key)
        if len(item["outputs"]) != len(item["output_amounts"]):
            problems.append("%s 的产品用量表长度不齐" % key)
    known = {
        # 出处：construction.zip 里的 .con 原文，手抄校对用
        "steel_mill": ([2, 2], [1]),       # 2 铁矿石 + 2 煤 → 1 钢
        "oil_refinery": ([2], [1]),        # 2 原油 → 1 精炼油
        "goods_factory": ([1, 1], [1]),    # 1 塑料 + 1 钢 → 1 货物
        "coal_mine": ([], [1]),            # 无原料 → 1 煤
    }
    for key, (want_in, want_out) in known.items():
        item = recipes.get(key)
        if item is None:
            problems.append("缺了 %s" % key)
            continue
        if item["input_amounts"] != want_in:
            problems.append("%s 原料用量 %s ≠ 应为 %s" % (key, item["input_amounts"], want_in))
        if item["output_amounts"] != want_out:
            problems.append("%s 产品用量 %s ≠ 应为 %s" % (key, item["output_amounts"], want_out))
    if problems:
        print("★ 自检没过：")
        for line in problems:
            print("   -", line)
        return 1

    payload = {
        "note": "产业配方（原料 → 产品）。从游戏 res/construction/construction.zip 的 "
                "industry/*.con 里 stockListConfig 抽出，可由 tools/extract-industry-recipes.py 重跑。",
        "source": "res/construction/construction.zip :: industry/*.con :: stockListConfig",
        "count": len(recipes),
        "industries": recipes,
    }

    target = os.path.normpath(OUT_FILE)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)

    print("解析出 %d 个产业的配方：\n" % len(recipes))

    def side(names_list, amounts):
        if not names_list:
            return "（直接采集）"
        return " + ".join("%d %s" % (amounts[i], names_list[i]) for i in range(len(names_list)))

    for key in sorted(recipes):
        item = recipes[key]
        print("   %-24s %-32s → %-20s 容量 %s"
              % (key, side(item["inputs"], item["input_amounts"]),
                 side(item["outputs"], item["output_amounts"]), item["capacity"]))
    print("\n输出：%s" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
