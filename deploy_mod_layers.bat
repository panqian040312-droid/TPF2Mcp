@echo off
chcp 936 >nul
title Deploy mod layers (terrain + lines + bridge flags)

set "PROJ=E://workbody//TPF2Mcp"
set "STAGE=C://Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
set "FAILED=0"

echo ==========================================
echo  Deploy mod layers to staging
echo ==========================================
echo.
echo  Close Transport Fever 2 first.
echo  Also close the map UI so the new export-layer-map.py
echo  is picked up when it restarts.
echo.
pause
echo.
call :one "tpf2_mod\res\scripts\tpf2_mcp\collectors\common.lua" "res\scripts\tpf2_mcp\collectors\common.lua"
call :one "tpf2_mod\res\scripts\tpf2_mcp\collectors\layer_registry.lua" "res\scripts\tpf2_mcp\collectors\layer_registry.lua"
call :one "tpf2_mod\res\scripts\tpf2_mcp\collectors\layer_road.lua" "res\scripts\tpf2_mcp\collectors\layer_road.lua"
call :one "tpf2_mod\res\scripts\tpf2_mcp\collectors\layer_vehicles.lua" "res\scripts\tpf2_mcp\collectors\layer_vehicles.lua"
call :one "tpf2_mod\res\scripts\tpf2_mcp\collectors\rail_network.lua" "res\scripts\tpf2_mcp\collectors\rail_network.lua"
call :one "tools\export-layer-map.py" "tools\export-layer-map.py"

echo.
if "%FAILED%"=="0" goto :all_ok
echo ==== SOME FILES FAILED - read the lines above ====
goto :done

:all_ok
echo ==== ALL FILES DEPLOYED, MD5 MATCHED ON BOTH SIDES ====
echo.
echo  Next:
echo    1. start Transport Fever 2, load the save, run at 1x
echo    2. wait about 40 seconds - terrain sampling and the
echo       new line layer both finish in that time
echo    3. tell the assistant
goto :done

:done
echo.
pause
goto :eof


:one
set "S=%PROJ%\%~1"
set "D=%STAGE%\%~2"
set "H1="
set "H2="

copy /Y "%S%" "%D%" >nul 2>&1
if errorlevel 1 goto :copy_fail

for /f "delims=" %%H in ('certutil -hashfile "%S%" MD5 ^| findstr /r /c:"^[0-9a-f][0-9a-f]"') do set "H1=%%H"
for /f "delims=" %%H in ('certutil -hashfile "%D%" MD5 ^| findstr /r /c:"^[0-9a-f][0-9a-f]"') do set "H2=%%H"
set "H1=%H1: =%"
set "H2=%H2: =%"

if /i "%H1%"=="%H2%" goto :ok
echo [DIFF] %~2
echo        src: %H1%
echo        dst: %H2%
set "FAILED=1"
goto :eof

:copy_fail
echo [FAIL] could not copy %~2
set "FAILED=1"
goto :eof

:ok
echo [OK]   %~2
goto :eof
