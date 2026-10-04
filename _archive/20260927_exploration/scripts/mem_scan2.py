"""只读扫描 TPF2 进程内存（性能版）：边扫边写日志，命中即记录。

安全：只申请 PROCESS_QUERY_INFORMATION | PROCESS_VM_READ。
用法: python mem_scan2.py [max_gb]
"""
import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time
import subprocess
from pathlib import Path

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01

LOG = Path(r"E:\workbody\TPF2Mcp\_save\memscan.log")


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


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_pid(name="TransportFever2.exe"):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, encoding="gbk", errors="ignore").stdout
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1])
    return None


NEEDLES = {}
for nm in ("京广客运", "JY客运", "JI线路", "YZ客运"):
    NEEDLES[f"name-utf8:{nm}"] = nm.encode("utf-8")
NEEDLES["lineid-i64:224503"] = struct.pack("<q", 224503)
NEEDLES["lineid-i32:224503"] = struct.pack("<i", 224503)


def main():
    max_gb = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    pid = find_pid()
    if not pid:
        log("找不到 TransportFever2.exe")
        return
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        log(f"OpenProcess 失败 err={ctypes.get_last_error()} pid={pid}")
        return
    log(f"PID={pid} 扫描开始（上限 {max_gb} GB，只读）")

    hits = {k: [] for k in NEEDLES}
    addr, scanned, regions = 0, 0, 0
    limit = max_gb * 1024 ** 3
    CHUNK = 16 * 1024 * 1024
    buf = ctypes.create_string_buffer(CHUNK)
    read = ctypes.c_size_t()
    mbi = MBI()
    t0 = time.time()
    last_log = t0
    while addr < 0x7FFFFFFFFFFF and scanned < limit:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize or 0
        if size == 0:
            addr += 0x1000
            continue
        ok_region = (mbi.State == MEM_COMMIT and mbi.Protect != PAGE_NOACCESS
                     and not (mbi.Protect & PAGE_GUARD) and size < 0x80000000)
        if ok_region:
            regions += 1
            off = 0
            while off < size:
                want = min(CHUNK, size - off)
                if k32.ReadProcessMemory(h, ctypes.c_void_p(base + off), buf, want, ctypes.byref(read)) and read.value:
                    data = buf.raw[:read.value]
                    scanned += read.value
                    for key, pat in NEEDLES.items():
                        if len(hits[key]) >= 10:
                            continue
                        i = data.find(pat)
                        while i != -1 and len(hits[key]) < 10:
                            hits[key].append(base + off + i)
                            log(f"  命中 {key} @0x{base+off+i:X}")
                            i = data.find(pat, i + 1)
                off += want
        addr = base + size
        now = time.time()
        if now - last_log > 20:
            log(f"  进度 {scanned/1024**3:.2f} GB / {regions} 区域")
            last_log = now

    k32.CloseHandle(h)
    log(f"扫描结束 {scanned/1024**3:.2f} GB / {regions} 区域 / {time.time()-t0:.0f}s")
    for key, addrs in hits.items():
        log(f"  {key}: {len(addrs)} 处" + (f" 首个 0x{addrs[0]:X}" if addrs else ""))


if __name__ == "__main__":
    main()
