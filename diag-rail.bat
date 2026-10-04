@echo off
chcp 936 >nul
title TPF2 - Rail deadlock risks
set "PYTHONPATH="
set "PYTHONSTARTUP="
set "PY=C:\Users\RailG\.workbuddy\binaries\python\versions\3.13.12\python.exe"
cd /d E:\workbody\TPF2Mcp
echo ==========================================
echo  Rail deadlock / clearance risks
echo  (2_brain_analysis)
echo.
echo  Scans every station for platforms that
echo  cannot clear a train. Can take a while on
echo  a large save.
echo ==========================================
echo.
"%PY%" 2_brain_analysis\find_deadlock_risks.py
echo.
pause
