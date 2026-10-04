@echo off
chcp 936 >nul
title TPF2 - Line economics
set "PYTHONPATH="
set "PYTHONSTARTUP="
set "PY=C:\Users\RailG\.workbuddy\binaries\python\versions\3.13.12\python.exe"
cd /d E:\workbody\TPF2Mcp
echo ==========================================
echo  Line economics  (2_brain_analysis)
echo.
echo  Estimated revenue vs maintenance cost
echo  per line. Needs bridge\economy-probe.json
echo  and bridge\layer-lines.json.
echo ==========================================
echo.
"%PY%" 2_brain_analysis\analyze-line-economics.py
echo.
pause
