@echo off
chcp 936 >nul
title TPF2 - Industry diagnosis
set "PYTHONPATH="
set "PYTHONSTARTUP="
set "PY=C:\Users\RailG\.workbuddy\binaries\python\versions\3.13.12\python.exe"
cd /d E:\workbody\TPF2Mcp
echo ==========================================
echo  Industry diagnosis  (2_brain_analysis)
echo.
echo  Reads bridge\layer-industry.json written
echo  by the in-game mod. Run the game once if
echo  the data looks stale.
echo ==========================================
echo.
"%PY%" 2_brain_analysis\diagnose-industries.py
echo.
pause
