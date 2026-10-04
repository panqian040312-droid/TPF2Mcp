@echo off
chcp 936 >nul
title Deploy TPF2Mcp to staging (full sync)

set "PROJ=E:\workbody\TPF2Mcp"
set "STAGE=C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
set "FAILED=0"

echo ============================================================
echo  Deploy TPF2Mcp  -  mod (res) + python (mcp_server) + tools
echo ============================================================
echo.
echo  BEFORE:  close Transport Fever 2. It locks res\*.lua while running.
echo  AFTER:   1) fully RESTART TPF2 - mod Lua is read only at startup,
echo              loading a save on top of a running game is not enough
echo           2) if the map UI window is open, close and relaunch it
echo              (tools\serve-rail-map.py IS the running server)
echo.
echo  This script syncs WHOLE DIRECTORIES, so a newly added collector is
echo  picked up automatically - there is no file list to forget to update.
echo  /E copies but never deletes, so local-only files survive
echo  (e.g. res\scripts\tpf2_mcp\local_config.lua).
echo.
pause
echo.

rem ------------------------------------------------------------------
rem  1/3  mod body: the whole res\ tree
rem ------------------------------------------------------------------
echo [1/3] syncing res\ ...
robocopy "%PROJ%\tpf2_mod\res" "%STAGE%\res" /E /R:1 /W:1 /NJH /NDL /NP /XD __pycache__
set "ROBOCODE=%ERRORLEVEL%"
if %ROBOCODE% GEQ 8 goto :sync_fail

rem ------------------------------------------------------------------
rem  2/3  python side - the MCP server runs the STAGING copy:
rem       rail-map-service.pyw -> SERVICE_ENTRY = MOD_DIRECTORY/mcp_server/start_ui.py
rem ------------------------------------------------------------------
echo [2/3] syncing mcp_server\ ...
robocopy "%PROJ%\mcp_server" "%STAGE%\mcp_server" /E /R:1 /W:1 /NJH /NDL /NP /XD __pycache__
set "ROBOCODE=%ERRORLEVEL%"
if %ROBOCODE% GEQ 8 goto :sync_fail

rem mod metadata (rarely changes; kept in step so versions do not drift apart)
copy /Y "%PROJ%\tpf2_mod\mod.lua"     "%STAGE%\mod.lua"     >nul
copy /Y "%PROJ%\tpf2_mod\strings.lua" "%STAGE%\strings.lua" >nul

rem ------------------------------------------------------------------
rem  3/3  tools - kept as a per-file list ON PURPOSE:
rem       staging only needs the two runtime files. Most of the project's
rem       tools\ are local one-shot scripts that must NOT be pushed.
rem ------------------------------------------------------------------
echo [3/3] tools\
call :one "1_data_collection\exporters\export-layer-map.py" "tools\export-layer-map.py"
call :one "3_dashboard_ui\server\serve-rail-map.py"         "tools\serve-rail-map.py"

rem ------------------------------------------------------------------
rem  verify: dry-run the res\ sync once more. Anything still listed means
rem  it did not land - usually because TPF2 still holds the file open.
rem ------------------------------------------------------------------
echo.
echo verifying res\ ...
set "LEFT="
for /f "delims=" %%F in ('robocopy "%PROJ%\tpf2_mod\res" "%STAGE%\res" /E /L /NJH /NJS /NDL /NP /XD __pycache__ ^| findstr /r /c:"[.]lua" /c:"[.]txt"') do set "LEFT=1"
if defined LEFT (echo   [WARN] res\ still has differences - see the list above) else (echo   [OK]   res\ is fully in sync)

echo.
if "%FAILED%"=="0" goto :all_ok
echo ==== SOME FILES FAILED - read the lines above ====
goto :done

:all_ok
echo ==== DEPLOY DONE ====
echo.
echo  Next:
echo    1. start Transport Fever 2, load the save, run at 1x
echo    2. wait about 60 seconds - the terrain layer resamples the
echo       whole map spread over many frames
echo    3. close and relaunch the map UI if it was open
echo    4. tell the assistant
goto :done

:sync_fail
echo [FAIL] robocopy reported an error. Most likely Transport Fever 2 is
echo        still running and holding the files open. Close it and rerun.
set "FAILED=1"
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
