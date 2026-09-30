#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 TPF2 自带的 UI 纹理包里提取**原版产业图标**，TGA → PNG。

为什么要有这个脚本
------------------
地图前端要在地图上给每个产业标一个能一眼认出类型的图标。自造图标（比如用汉字）
既不对味、也和游戏里看到的不一致，所以直接抽游戏原版的那套。

图标在哪
--------
游戏本体的 UI 纹理打包在 `res/textures/ui/ui.zip` 里。产业图标在
`construction/industry/` 之下，一套 16 种，每种给两张：

    120x75  普通版
    240x150 `@2x` 高清版   ← 本脚本取这张

文件名（去掉 .tga）就是**游戏内部认的产业类型名**，例如 `coal_mine` / `farm` /
`oil_refinery`。前端靠这个名字跟产业名里推断出的类型做映射。

为什么要手写解码
----------------
本机没有 Pillow，也没有 ImageMagick（`C:\\WINDOWS\\system32\\convert` 是 Windows
自带的磁盘转换工具，不是图片转换）。好在这批 TGA 格式极简单，用标准库足够：
    type = 2   未压缩真彩色
    bpp  = 32  BGRA 顺序（不是 RGBA！）
    desc = 0x08  第 5 位为 0 ⇒ **原点在左下角**，读出来必须逐行上下翻转，
                 否则图标全是倒的（这个坑不翻一下看不出来，因为大多数图标上下近似对称）
图像数据紧跟在 18 字节头之后，长度 = 宽 × 高 × 4。

用法
----
    python tools/extract-industry-icons.py

产物：`ui/rail-map/icons/industry/*.png`（覆盖写入）。
⚠️ 这些 PNG 是**游戏版权资源**，只在本机自用，不要提交进 Git、不要对外分发。
"""
import os
import struct
import sys
import zipfile
import zlib

GAME_DIR = r"E:\SteamLibrary\steamapps\common\Transport Fever 2"
UI_ZIP = os.path.join(GAME_DIR, "res", "textures", "ui", "ui.zip")
ICON_PREFIX = "construction/industry/"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "ui", "rail-map", "icons", "industry")

# ── 第二批：**货物图标**（`hud/cargo_*@2x.tga`，50×50 方形）────────────────────
# 为什么还要这一批：上面那批「产业场景图」是 **240×150 的等轴测全景**，信息量大但在地图上
# 太小看不清、太大又糊满屏。地图标记真正该用的是**右下角那个小符号**的独立资源 ——
# 游戏把它单独放在 `hud/` 下当货物图标用（就是用户截图里那个橙色矿石多面体）。
# 这批是 50×50 的方形图标，直接能当地图标记。
#
# 只取下面这 16 个（产业名 → 它产出/代表的那类货物），不是全部货物：
# 地图上标的是「产业」，用"它产出的货物"当图标最直观。
CARGO_ICONS = [
    "cargo_iron_ore",                  # 铁矿
    "cargo_coal",                      # 煤矿
    "cargo_crude",                     # 油井（原油）
    "cargo_stone",                     # 采石场
    "cargo_grain",                     # 农田（谷物）
    "cargo_logs",                      # 森林（原木）
    "cargo_planks",                    # 锯木厂（木板）
    "cargo_oil",                       # 炼油厂（油）
    "cargo_fuel",                      # 燃料精炼厂
    "cargo_tools",                     # 工具厂
    "cargo_food",                      # 食品加工厂
    "cargo_plastic",                   # 化工厂
    "cargo_machines",                  # 机械厂
    "cargo_steel",                     # 钢铁厂
    "cargo_construction_materials",    # 建材厂
    "cargo_goods",                     # 工厂（兜底：成品货物）
]
CARGO_PREFIX = "hud/"
CARGO_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "ui", "rail-map", "icons", "cargo")


def decode_tga(data: bytes):
    """未压缩 32 位 TGA → (宽, 高, 每行 RGBA 字节)。原点在左下角时自动翻正。"""
    id_len, color_map, image_type = data[0], data[1], data[2]
    width, height = struct.unpack("<HH", data[12:16])
    bits_per_pixel, descriptor = data[16], data[17]

    if image_type != 2:
        raise ValueError("只支持未压缩真彩色（type=2），实际 type=%d" % image_type)
    if bits_per_pixel != 32:
        raise ValueError("只支持 32 位，实际 bpp=%d" % bits_per_pixel)

    offset = 18 + id_len
    pixels = data[offset:offset + width * height * 4]
    if len(pixels) != width * height * 4:
        raise ValueError("像素数据不足：期望 %d，实得 %d" % (width * height * 4, len(pixels)))

    # 描述符第 5 位（0x20）：0 = 原点左下（自下而上），1 = 原点左上。
    bottom_up = (descriptor & 0x20) == 0

    rows = []
    for y in range(height):
        source_y = (height - 1 - y) if bottom_up else y
        base = source_y * width * 4
        row = bytearray()
        for x in range(width):
            b, g, r, a = pixels[base + x * 4: base + x * 4 + 4]
            row += bytes((r, g, b, a))     # TGA 存的是 BGRA，PNG 要 RGBA
        rows.append(bytes(row))
    return width, height, rows


def png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def write_png(path: str, width: int, height: int, rows) -> None:
    """最小 PNG 编码器：8 位 RGBA（颜色类型 6），不带调色板、不加隔行。"""
    raw = b"".join(b"\x00" + row for row in rows)      # 每行前面补一个滤波类型 0（None）
    blob = b"\x89PNG\r\n\x1a\n"
    blob += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    blob += png_chunk(b"IDAT", zlib.compress(raw, 9))
    blob += png_chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(blob)


def main() -> int:
    if not os.path.exists(UI_ZIP):
        print("找不到游戏 UI 纹理包：%s" % UI_ZIP)
        return 1

    out_dir = os.path.normpath(OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    archive = zipfile.ZipFile(UI_ZIP)
    # 只取 @2x 高清版（240x150）。普通版是它的整数缩小，没必要存两份。
    wanted = sorted(
        name for name in archive.namelist()
        if name.startswith(ICON_PREFIX) and name.endswith("@2x.tga")
    )
    if not wanted:
        print("在 %s 下没找到 @2x 图标" % ICON_PREFIX)
        return 1

    print("从 %s 提取 %d 个产业图标：" % (UI_ZIP, len(wanted)))
    for name in wanted:
        stem = os.path.basename(name).replace("@2x.tga", "")
        width, height, rows = decode_tga(archive.read(name))
        target = os.path.join(out_dir, stem + ".png")
        write_png(target, width, height, rows)
        print("   %-26s → %s  (%dx%d, %d B)"
              % (stem, os.path.basename(target), width, height, os.path.getsize(target)))

    print("\n输出目录：%s" % out_dir)
    print("⚠️ 游戏版权资源，仅本机自用，勿提交 Git、勿对外分发。")

    # ── 第二批：货物图标（地图标记实际要用的那套）────────────────────────────
    cargo_dir = os.path.normpath(CARGO_OUT_DIR)
    os.makedirs(cargo_dir, exist_ok=True)
    print()
    print("从同一纹理包提取 %d 个货物图标：" % len(CARGO_ICONS))
    for stem in CARGO_ICONS:
        member = "%s%s@2x.tga" % (CARGO_PREFIX, stem)
        if member not in archive.namelist():
            print("   %-34s ★ 缺席（包内没有 %s）" % (stem, member))
            continue
        width, height, rows = decode_tga(archive.read(member))
        target = os.path.join(cargo_dir, stem + ".png")
        write_png(target, width, height, rows)
        print("   %-34s → %-34s (%dx%d)" % (stem, os.path.basename(target), width, height))

    print("\n输出目录：%s" % cargo_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
