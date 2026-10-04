"""在游戏进程内存中定位"线路对象"：搜索多个独有锚点并做邻近聚类。

安全：只读（PROCESS_VM_READ）。
用法: python mem_find.py [max_gb]
"""
import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PQI, PVM_READ = 0x0400, 0x0010
MEM_COMMIT, PAGE_GUARD, PAGE_NOACCESS = 0x1000, 0x100, 0x01
CHUNK = 16 * 1024 * 1024


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]


def find_pid(name="TransportFever2.exe"):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, encoding="gbk", errors="ignore").stdout
    for line in out.splitlines():
        p = [x.strip('"') for x in line.split('","')]
        if len(p) > 1 and p[1].isdigit():
            return int(p[1])
    return None


# 京广客运（line 224503）独有锚点
ANCHORS = {
    "station-243069": struct.pack("<i", 243069),
    "station-105581": struct.pack("<i", 105581),
    "station-148720": struct.pack("<i", 148720),
    "vehicle-159365": struct.pack("<i", 159365),
    "lineid-224503": struct.pack("<i", 224503),
    "freq-double": struct.pack("<d", 1076.0000117747),
    "freq-float": struct.pack("<f", 1076.0),
}
CAP = 400


def main():
    max_gb = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    pid = find_pid()
    h = k32.OpenProcess(PQI | PVM_READ, False, pid)
    if not h:
        print("OpenProcess 失败")
        return
    print(f"PID={pid} 开始全内存搜索（上限 {max_gb} GB）", flush=True)

    hits = {k: [] for k in ANCHORS}
    addr, scanned = 0, 0
    limit = max_gb * 1024 ** 3
    buf = ctypes.create_string_buffer(CHUNK)
    got = ctypes.c_size_t()
    mbi = MBI()
    t0 = time.time()
    while addr < 0x7FFFFFFFFFFF and scanned < limit:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress or 0, mbi.RegionSize or 0
        if size == 0:
            addr += 0x1000
            continue
        if (mbi.State == MEM_COMMIT and mbi.Protect != PAGE_NOACCESS
                and not (mbi.Protect & PAGE_GUARD) and size < 0x80000000):
            off = 0
            while off < size:
                want = min(CHUNK, size - off)
                if k32.ReadProcessMemory(h, ctypes.c_void_p(base + off), buf, want, ctypes.byref(got)) and got.value:
                    data = buf.raw[:got.value]
                    scanned += got.value
                    for key, pat in ANCHORS.items():
                        if len(hits[key]) >= CAP:
                            continue
                        i = data.find(pat)
                        while i != -1:
                            hits[key].append(base + off + i)
                            if len(hits[key]) >= CAP:
                                break
                            i = data.find(pat, i + 1)
                off += want
        addr = base + size

    print(f"扫描 {scanned/1024**3:.2f} GB / {time.time()-t0:.0f} s")
    for k, v in hits.items():
        print(f"  {k}: {len(v)} 处" + (f"  例: " + ", ".join(f"0x{x:X}" for x in v[:5]) if v else ""))

    # 聚类：找"同时含 station-243069 与 station-148720"的 64KB 邻域
    print("\n=== 邻近聚类（同一 64KB 邻域内同时出现多个锚点）===")
    flat = [(a, k) for k, v in hits.items() for a in v]
    flat.sort()
    used = set()
    for a, k in flat:
        if a in used:
            continue
        bucket = round(a / 65536)
        same = [(b, kk) for b, kk in flat if round(b / 65536) == bucket]
        kinds = sorted({kk for _, kk in same})
        if len(kinds) >= 3 and bucket not in used:
            used.add(bucket)
            print(f"  0x{bucket*65536:X} 附近: " + ", ".join(f"{kk}@0x{b:X}" for b, kk in same[:14]))
    k32.CloseHandle(h)


if __name__ == "__main__":
    main()
