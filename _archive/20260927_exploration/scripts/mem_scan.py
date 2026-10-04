"""只读扫描 TPF2 进程内存，寻找已知数值与字符串，验证能否直接读实时数据。

安全：只申请 PROCESS_QUERY_INFORMATION | PROCESS_VM_READ，绝不写内存、不改游戏。

用法：
  python mem_scan.py <pid> [--balance N] [--lines id,id] [--names 名1,名2]
"""
import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]


def find_pid(name="TransportFever2.exe"):
    import subprocess
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, encoding="gbk", errors="ignore").stdout
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1])
    return None


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else find_pid()
    if not pid:
        print("找不到 TransportFever2.exe 进程")
        return
    print(f"目标进程 PID = {pid}")

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print("OpenProcess 失败 err =", ctypes.get_last_error())
        return
    print("OpenProcess OK（只读权限）")

    needles = {}
    for i, a in enumerate(sys.argv):
        if a == "--balance" and i + 1 < len(sys.argv):
            v = int(sys.argv[i + 1])
            needles[f"balance(int64)={v}"] = struct.pack("<q", v)
        if a == "--lines" and i + 1 < len(sys.argv):
            for tok in sys.argv[i + 1].split(","):
                if tok.strip().isdigit():
                    for fmt, tag in (("<i", "i32"), ("<q", "i64")):
                        needles[f"lineid({tag})={tok}"] = struct.pack(fmt, int(tok))
        if a == "--names" and i + 1 < len(sys.argv):
            for nm in sys.argv[i + 1].split(","):
                if nm.strip():
                    needles[f"name(utf8)={nm}"] = nm.encode("utf-8")
                    needles[f"name(utf16)={nm}"] = nm.encode("utf-16-le")

    print("待搜索:", list(needles.keys()))

    hits = {k: [] for k in needles}
    addr = 0
    total_scanned = 0
    regions = 0
    t0 = time.time()
    mbi = MEMORY_BASIC_INFORMATION()
    CHUNK = 8 * 1024 * 1024
    while addr < 0x7FFFFFFFFFFF:
        got = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not got:
            break
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize or 0
        if size == 0:
            addr += 0x1000
            continue
        readable = (mbi.State == MEM_COMMIT and mbi.Protect != PAGE_NOACCESS and not (mbi.Protect & PAGE_GUARD))
        if readable and size < 0x40000000:  # 跳过超大区域，避免爆内存
            regions += 1
            off = 0
            buf = ctypes.create_string_buffer(CHUNK)
            read = ctypes.c_size_t()
            while off < size:
                want = min(CHUNK, size - off)
                ok = k32.ReadProcessMemory(h, ctypes.c_void_p(base + off), buf, want, ctypes.byref(read))
                n = read.value
                if ok and n:
                    data = buf.raw[:n]
                    total_scanned += n
                    for key, pat in needles.items():
                        if len(hits[key]) >= 20:
                            continue
                        start = data.find(pat)
                        while start != -1 and len(hits[key]) < 20:
                            hits[key].append(base + off + start)
                            start = data.find(pat, start + 1)
                off += want
        addr = base + size

    k32.CloseHandle(h)
    dt = time.time() - t0
    print(f"\n扫描完成：{regions} 个区域 / {total_scanned/1024/1024/1024:.2f} GB / {dt:.1f} 秒")
    for key, addrs in hits.items():
        print(f"  {key}: 命中 {len(addrs)} 处" + (f"，首个 @0x{addrs[0]:X}" if addrs else ""))


if __name__ == "__main__":
    main()
