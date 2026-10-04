"""只读 dump 游戏进程指定地址的内存，并按多种类型解释，便于逆向结构。

用法:
  python mem_dump.py --addr 0x20F0E52C434 --size 2048
  python mem_dump.py --addr 0x... --window 65536 --anchors 224503,243069,105581,1294,1076,879
"""
import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PQI, PVM_READ = 0x0400, 0x0010
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]


def find_pid(name="TransportFever2.exe"):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, encoding="gbk", errors="ignore").stdout
    for line in out.splitlines():
        p = [x.strip('"') for x in line.split('","')]
        if len(p) > 1 and p[1].isdigit():
            return int(p[1])
    return None


def read_mem(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return buf.raw[:got.value] if ok else None


def read_span(h, start, size, chunk=64 * 1024):
    """分块读，跳过不可读块（用 0xCC 填充），返回完整 buffer。"""
    out = bytearray()
    off = 0
    buf = ctypes.create_string_buffer(chunk)
    got = ctypes.c_size_t()
    while off < size:
        want = min(chunk, size - off)
        ok = k32.ReadProcessMemory(h, ctypes.c_void_p(start + off), buf, want, ctypes.byref(got))
        if ok and got.value:
            out += buf.raw[:got.value]
            off += got.value
        else:
            pad = ctypes.create_string_buffer(b"\xcc" * want)
            out += pad.raw
            off += want
    return bytes(out)


def main():
    args = sys.argv[1:]
    addr = int(args[args.index("--addr") + 1], 16) if "--addr" in args else 0
    size = int(args[args.index("--size") + 1]) if "--size" in args else 1024
    window = int(args[args.index("--window") + 1]) if "--window" in args else 0
    anchors = []
    if "--anchors" in args:
        anchors = [int(x) for x in args[args.index("--anchors") + 1].split(",") if x.strip()]
    fanchors = []
    if "--fanchors" in args:
        fanchors = [float(x) for x in args[args.index("--fanchors") + 1].split(",") if x.strip()]

    pid = find_pid()
    h = k32.OpenProcess(PQI | PVM_READ, False, pid)
    if not h:
        print("OpenProcess 失败")
        return

    if window:
        start = addr - window // 2
        data = read_span(h, start, window)
        print(f"窗口 0x{start:X} .. 0x{start+len(data):X}（{len(data)} 字节，0xCC = 不可读）")
        # 只为展示"锚点偏移"，把窗口按最近锚点地址换算
        print("\n=== 锚点在窗口内的原始偏移 ===")
        for a in anchors:
            found = []
            for fmt, tag, w in (("<i", "i32", 4), ("<q", "i64", 8), ("<f", "f32", 4), ("<d", "f64", 8)):
                pat = struct.pack(fmt, a)
                i = data.find(pat)
                while i != -1 and len(found) < 12:
                    found.append((i, tag))
                    i = data.find(pat, i + 1)
            if found:
                print(f"  {a}: " + "、".join(f"+0x{o:X}({t})" for o, t in found[:12]))
            else:
                print(f"  {a}: 窗口内无命中")
        for fa in fanchors:
            found = []
            for fmt, tag in (("<f", "f32"), ("<d", "f64")):
                pat = struct.pack(fmt, fa)
                i = data.find(pat)
                while i != -1 and len(found) < 12:
                    found.append((i, tag))
                    i = data.find(pat, i + 1)
            if found:
                print(f"  {fa}: " + "、".join(f"+0x{o:X}({t})" for o, t in found[:12]))
            else:
                print(f"  {fa}: 窗口内无命中")

    data = read_mem(h, addr, size)
    if data is None:
        print("读取失败（地址可能无效）")
        return
    print(f"\n=== 0x{addr:X} 起 {len(data)} 字节 ===")
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{addr+off:012X}  {hexs:<47}  {asc}")

    print("\n=== 解释为 int32 / int64 / float / double（非零且看起来像数据的会列出）===")
    print("offset   i32        u32        i64                  f32         f64")
    for off in range(0, len(data) - 8, 4):
        i32 = struct.unpack_from("<i", data, off)[0]
        u32 = struct.unpack_from("<I", data, off)[0]
        i64 = struct.unpack_from("<q", data, off)[0]
        f32 = struct.unpack_from("<f", data, off)[0]
        f64 = struct.unpack_from("<d", data, off)[0]
        interesting = (i32 != 0 and abs(i32) < 2_000_000_000) or (abs(f32) > 1e-6 and abs(f32) < 1e9)
        if interesting:
            f32s = f"{f32:.4g}" if abs(f32) < 1e9 else "-"
            f64s = f"{f64:.6g}" if abs(f64) < 1e12 else "-"
            print(f"+{off:<6} {i32:<10} {u32:<10} {i64:<20} {f32s:<11} {f64s}")
    k32.CloseHandle(h)


if __name__ == "__main__":
    main()
