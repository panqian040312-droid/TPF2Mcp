@echo off
chcp 936 >nul
title Deploy TPF2 MCP mod files
setlocal

set "SRC=E:/workbody/TPF2Mcp/tpf2_mod/res/scripts/tpf2_mcp"
set "DST=C:/Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1\res\scripts\tpf2_mcp"

echo ==========================================
echo  Deploy world_probe + state.lua + runtime.lua
echo ==========================================
echo.

tasklist /FI "IMAGENAME eq TransportFever2.exe" 2>nul | findstr /I TransportFever2 >nul
if not errorlevel 1 goto game_running

if exist "%DST%" goto target_ok
echo [ERROR] target folder not found:
echo   %DST%
echo.
pause
exit /b 1

:target_ok
echo [1/3] collectors\world_probe.lua
copy /Y "%SRC%\collectors\world_probe.lua" "%DST%\collectors\world_probe.lua"

echo [2/3] state.lua
copy /Y "%SRC%\state.lua" "%DST%\state.lua"

echo [3/3] runtime.lua
copy /Y "%SRC%\runtime.lua" "%DST%\runtime.lua"

echo.
echo ===== verify: the three lines below must show today's date =====
for %%F in ("%DST%\collectors\world_probe.lua") do echo   world_probe.lua   %%~zF bytes   %%~tF
for %%F in ("%DST%\state.lua") do echo   state.lua         %%~zF bytes   %%~tF
for %%F in ("%DST%\runtime.lua") do echo   runtime.lua       %%~zF bytes   %%~tF
echo.
echo done. Now start Transport Fever 2 and load your save.
echo.
pause
exit /b 0

:game_running
echo [STOP] Transport Fever 2 is still running.
echo.
echo   The game locks the mod files while it is open, so the copy would fail.
echo   Please:
echo     1. Exit the game completely (back to desktop)
echo     2. Run this script again
echo     3. Then start the game
echo.
pause
exit /b 1
