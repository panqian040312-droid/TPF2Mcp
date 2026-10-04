"""一次性小工具：不依赖 PIL，手写 PNG 解码后统计几个标记色的像素量。
用途：确认用户截图里"那条青线"到底是不是 freight-flow 画的上游色（#4fd1ff）。
用法：python _audit/png-probe.py <png 路径>
"""
import struct
import sys
import zlib


def load_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    pos, idat = 8, bytearray()
    w = h = bd = ct = None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", body[:10])
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    return w, h, bd, ct, zlib.decompress(bytes(idat))


def unfilter(w, h, bpp, raw):
    stride = w * bpp
    out = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


TARGETS = (
    ("cyan   #4fd1ff 上游", 79, 209, 255, 45),
    ("amber  #e0a33a 只进不出", 224, 163, 58, 28),
    ("gray   #9aa0a6 未启用", 154, 160, 166, 22),
    ("orange #ffb347 下游", 255, 179, 71, 30),
)

path = sys.argv[1]
w, h, bd, ct, raw = load_png(path)
bpp = {0: 1, 2: 3, 4: 2, 6: 4}.get(ct)
print("size=%dx%d bitdepth=%s colortype=%s" % (w, h, bd, ct))
if bpp is None or bd != 8:
    print("unsupported format")
    sys.exit()

px = unfilter(w, h, bpp, raw)
hits = [0] * len(TARGETS)
total = 0
for y in range(0, h, 3):
    base = y * w * bpp
    for x in range(0, w, 3):
        i = base + x * bpp
        r, g, b = px[i], px[i + 1], px[i + 2]
        total += 1
        for k, (_n, tr, tg, tb, tol) in enumerate(TARGETS):
            if abs(r - tr) <= tol and abs(g - tg) <= tol and abs(b - tb) <= tol:
                hits[k] += 1
for k, (name, _r, _g, _b, _t) in enumerate(TARGETS):
    print("  %-24s %6d  (%.4f%%)" % (name, hits[k], 100.0 * hits[k] / max(1, total)))
