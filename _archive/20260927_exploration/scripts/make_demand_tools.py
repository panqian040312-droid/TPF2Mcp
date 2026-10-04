"""生成两样东西：
1) ui/rail-map/rail-network-data.json —— collect-line-demand.py --all-rail 需要的线路清单
2) collect_demand.bat —— 用户终端双击即可全量采集真实客流（CRLF + 纯 ASCII）
"""
import json
from pathlib import Path

ROOT = Path(r"E:\workbody\TPF2Mcp")
MOD = Path(r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1")

net = json.load(open(MOD / "bridge/rail-network.json", encoding="utf-8"))
snap = json.load(open(MOD / "bridge/state.json", encoding="utf-8"))
names = {int(l["entity_id"]): l["name"] for l in snap["lines"]}

manifest = {
    "schema_version": 1,
    "source": "bridge/rail-network.json",
    "lines": [{"entity_id": int(l["entity_id"]), "name": names.get(int(l["entity_id"]))} for l in net["lines"]],
}
out = ROOT / "ui/rail-map/rail-network-data.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print("已写出", out, "线路数", len(manifest["lines"]))

lines = [
    "@echo off",
    "chcp 936 >nul",
    "title TPF2 demand sampler",
    "set \"PYTHONPATH=\"",
    "set \"PYTHONSTARTUP=\"",
    "set \"TPF2_MCP_MOD_DIR=C:\\Program Files (x86)\\Steam\\userdata\\1070536217\\1066780\\local\\staging_area\\tpf2mcp_1\"",
    "set \"PY=C:\\Users\\RailG\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe\"",
    "cd /d E:\\workbody\\TPF2Mcp",
    "echo ==========================================",
    "echo  Collect REAL passenger/cargo demand",
    "echo  (read-only; the game must be running",
    "echo   with a save loaded and NOT paused)",
    "echo ==========================================",
    "echo.",
    "\"%PY%\" tools\\collect-line-demand.py --all-rail --database E:\\workbody\\TPF2Mcp\\_state\\line-demand.sqlite3",
    "echo.",
    "echo Done. Database: E:\\workbody\\TPF2Mcp\\_state\\line-demand.sqlite3",
    "pause",
]
bat = ROOT / "collect_demand.bat"
bat.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))
print("已写出", bat, bat.stat().st_size, "字节（CRLF/ASCII）")
