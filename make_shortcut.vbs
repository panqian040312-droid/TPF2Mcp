Option Explicit
Dim sh, desktop, lnk
Set sh = CreateObject("WScript.Shell")
desktop = sh.SpecialFolders("Desktop")

Set lnk = sh.CreateShortcut(desktop & "\TPF2 Rail Map.lnk")
lnk.TargetPath = "E:\workbody\TPF2Mcp\start_rail_map.bat"
lnk.WorkingDirectory = "E:\workbody\TPF2Mcp"
lnk.Description = "TPF2 rail map service - http://127.0.0.1:8765/?view=network"
lnk.IconLocation = "C:\Windows\System32\cmd.exe,0"
lnk.WindowStyle = 1
lnk.Save

WScript.Echo "created: " & desktop & "\TPF2 Rail Map.lnk"
