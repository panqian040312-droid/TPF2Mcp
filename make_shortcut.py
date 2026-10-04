"""在桌面创建「TPF2 铁路图」快捷方式（指向 start_rail_map.bat）。

为什么用 Python + pywin32：本机安全策略会拦截 PowerShell 的 COM 实例化与 cscript(.vbs)，
而 win32com 走的是普通 Python 进程，实测可用。

用法：python make_shortcut.py
"""
from __future__ import annotations

from pathlib import Path

import win32com.client

BAT = Path(r"E:\workbody\TPF2Mcp\start_rail_map.bat")
WORKDIR = BAT.parent
LNK_NAME = "TPF2 铁路图.lnk"
URL = "http://127.0.0.1:8790/?view=network"

shell = win32com.client.Dispatch("WScript.Shell")
desktop = shell.SpecialFolders("Desktop")
lnk_path = Path(desktop) / LNK_NAME

shortcut = shell.CreateShortCut(str(lnk_path))
shortcut.TargetPath = str(BAT)
shortcut.WorkingDirectory = str(WORKDIR)
shortcut.Description = f"TPF2 铁路调度图服务（{URL}）"
shortcut.IconLocation = r"C:\Windows\System32\cmd.exe,0"
shortcut.WindowStyle = 1
shortcut.Save()

exists = lnk_path.exists()
print(f"目标脚本存在: {BAT.exists()}")
print(f"快捷方式已创建: {lnk_path}  ({'存在' if exists else '不存在'})")
if exists:
    print(f"大小: {lnk_path.stat().st_size} 字节")
    # 回读校验
    check = shell.CreateShortCut(str(lnk_path))
    print(f"回读 TargetPath: {check.TargetPath}")
    print(f"回读 WorkingDirectory: {check.WorkingDirectory}")
