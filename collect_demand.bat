@echo off
chcp 936 >nul
title TPF2 demand sampler
set "PYTHONPATH="
set "PYTHONSTARTUP="
set "TPF2_MCP_MOD_DIR=C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
set "PY=C:\Users\RailG\.workbuddy\binaries\python\versions\3.13.12\python.exe"
cd /d E:\workbody\TPF2Mcp
echo ==========================================
echo  Collect REAL passenger/cargo demand
echo  (read-only; the game must be running
echo   with a save loaded and NOT paused)
echo ==========================================
echo.
"%PY%" 1_data_collection\probes\collect-line-demand.py --all-rail --database E:\workbody\TPF2Mcp\_state\line-demand.sqlite3
echo.
echo Done. Database: E:\workbody\TPF2Mcp\_state\line-demand.sqlite3
pause
