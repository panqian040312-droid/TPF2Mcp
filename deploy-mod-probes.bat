@echo off
chcp 936 >nul
title Deploy TPF2Mcp - probes (minimal, 6 files)
setlocal

set "PROJ=E:\workbody\TPF2Mcp\tpf2_mod"
set "STAGE=C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
set "FAILED=0"

echo ============================================================
echo  TPF2Mcp  minimal deploy  -  6 files
echo    2 new collectors : layer_passenger / terminal_waiting_probe
echo    3 hook edits     : layer_registry / runtime / state
echo    1 port fix       : strings.lua  8765 -^> 8790
echo ------------------------------------------------------------
echo  BEFORE you run this:
echo    Transport Fever 2 must be FULLY CLOSED.
echo    It locks res\*.lua while running, and it reads mod Lua
echo    only at startup - loading a save on top is NOT enough.
echo ============================================================
echo.
pause
echo.

call :one "res\scripts\tpf2_mcp\collectors\layer_passenger.lua"
call :one "res\scripts\tpf2_mcp\collectors\terminal_waiting_probe.lua"
call :one "res\scripts\tpf2_mcp\collectors\layer_registry.lua"
call :one "res\scripts\tpf2_mcp\runtime.lua"
call :one "res\scripts\tpf2_mcp\state.lua"
call :one "strings.lua"

echo.
if "%FAILED%"=="0" goto :all_ok
echo ==== SOME FILES FAILED - see [DIFF] / [FAIL] lines above ====
echo      Most likely TPF2 is still running and holding the files.
echo      Close the game and run this script again.
goto :done

:all_ok
echo ==== DEPLOY DONE - all 6 files present and md5-verified ====
echo.
echo  Next:
echo    1. start Transport Fever 2, load the save, keep 1x speed
echo    2. wait about 60 seconds
echo    3. tell the assistant
echo.
echo  Where the results will appear:
echo    bridge\terminal-waiting-probe.json  (after one get_game_state)
echo    bridge\layer-passenger.json         (one round every 12000 updates)
goto :done

:done
echo.
pause
exit /b


rem ---------------------------------------------------------------
rem  :one  <relative path>
rem  same relative path on both sides:  tpf2_mod\X  ->  staging\X
rem ---------------------------------------------------------------
:one
set "SRC=%PROJ%\%~1"
set "DST=%STAGE%\%~1"

attrib -R "%DST%" >nul 2>&1

copy /Y "%SRC%" "%DST%" >nul 2>&1
if errorlevel 1 (
    del /F /Q "%DST%" >nul 2>&1
    copy /Y "%SRC%" "%DST%" >nul 2>&1
)
if errorlevel 1 goto :copy_fail

set "H1="
set "H2="
for /f "delims=" %%H in ('certutil -hashfile "%SRC%" MD5 ^| findstr /r /c:"^[0-9a-f][0-9a-f]"') do set "H1=%%H"
for /f "delims=" %%H in ('certutil -hashfile "%DST%" MD5 ^| findstr /r /c:"^[0-9a-f][0-9a-f]"') do set "H2=%%H"
set "H1=%H1: =%"
set "H2=%H2: =%"

if /i "%H1%"=="%H2%" goto :ok
echo [DIFF] %~1
echo         src=%H1%
echo         dst=%H2%
set "FAILED=1"
goto :eof

:copy_fail
echo [FAIL] could not copy  %~1
set "FAILED=1"
goto :eof

:ok
echo [OK]   %~1
goto :eof
