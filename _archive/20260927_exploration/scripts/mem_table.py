"""解析内存里的 (entity_id, value) 记录数组，判断它是不是"车站→待运量"之类的表。

安全：只读。
用法: python mem_table.py 0x20F8EC3A380 [span_kb]
"""
import ctypes
import ctypes.wintypes as wt
import json
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PQI, PVM_READ = 0x0400, 0x0010
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]

MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")


def find_pid(name="TransportFever2.exe"):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, encoding="gbk", errors="ignore").stdout
    for line in out.splitlines():
        p = [x.strip('"') for x in line.split('","')]
        if len(p) > 1 and p[1].isdigit():
            return int(p[1])
    return None


def read_span(h, start, size, chunk=4096):
    out = bytearray()
    off = 0
    buf = ctypes.create_string_buffer(chunk)
    got = ctypes.c_size_t()
    while off < size:
        want = min(chunk, size - off)
        ok = k32.ReadProcessMemory(h, ctypes.c_void_p(start + off), buf, want, ctypes.byref(got))
        if ok and got.value == want:
            out += buf.raw[:want]
        else:
            out += b"\xcc" * want
        off += want
    return bytes(out)


def main():
    addr = int(sys.argv[1], 16)
    span_kb = int(sys.argv[2]) if len(sys.argv) > 2 else 512
    pid = find_pid()
    h = k32.OpenProcess(PQI | PVM_READ, False, pid)
    if not h:
        print("OpenProcess 失败")
        return

    start = addr - span_kb * 1024 // 2
    size = span_kb * 1024
    data = read_span(h, start, size)
    print(f"读取 0x{start:X} .. 0x{start+size:X}（{size//1024} KB）")

    # 车道①：识别所有"看起来像 (id, small value)" 的 4 字节对齐记录
    recs = []
    for off in range(0, size - 8, 4):
        v1, v2 = struct.unpack_from("<II", data, off)
        if 1000 <= v1 <= 2_000_000 and v2 <= 2_000_000:
            recs.append((start + off, v1, v2))
    print(f"候选记录 {len(recs)} 条")

    net = json.load(open(MOD / "bridge/rail-network.json", encoding="utf-8"))
    snap = json.load(open(MOD / "bridge/state.json", encoding="utf-8"))
    stations = {s["entity_id"]: s.get("name") for s in net["stations"]}
    allent = set()
    for key in ("lines", "vehicles", "stations", "industries", "towns"):
        for e in snap.get(key) or []:
            if isinstance(e, dict) and isinstance(e.get("entity_id"), int):
                allent.add(e["entity_id"])

    # 命中统计
    hit_station = [r for r in recs if r[1] in stations]
    hit_any = [r for r in recs if r[1] in allent]
    print(f"其中命中【铁路车站ID】{len(hit_station)} 条 / 该表车站共 {len(stations)}；命中任意已知实体 {len(hit_any)} 条")
    print("命中实体类型分布:", Counter(
        ("line" if r[1] in {l['entity_id'] for l in snap['lines']} else
         "vehicle" if r[1] in {v['entity_id'] for v in snap['vehicles']} else
         "station" if r[1] in stations else
         "industry" if r[1] in {i['entity_id'] for i in snap['industries']} else
         "town" if r[1] in {t['entity_id'] for t in snap['towns']} else "?") for r in hit_any))

    print("\n=== 按地址顺序列出前 40 条命中车站的记录 ===")
    for a, i, v in sorted(hit_station)[:40]:
        print(f"  0x{a:X}  id={i:<8} value={v:<8} {stations[i]}")

    print("\n=== 车站出现次数（前 15）===")
    c = Counter(i for _, i, _ in hit_station)
    for i, n in c.most_common(15):
        vals = [v for _, ii, v in hit_station if ii == i]
        print(f"  {stations[i]:<12} id={i} 出现 {n} 次，值={vals[:8]}")

    # 关键：看我们的走廊车站
    print("\n=== 走廊相关车站的数值 ===")
    for name in ("天津", "广州北站", "Hanoi中央车站", "Jeddah", "中山西站", "台北", "Istanbul附站"):
        ids = [i for i, n2 in stations.items() if n2 == name]
        for i in ids:
            vals = [v for _, ii, v in hit_station if ii == i]
            print(f"  {name:<12} id={i:<7} 值={vals if vals else '（本窗口无记录）'}")
    k32.CloseHandle(h)


if __name__ == "__main__":
    main()
