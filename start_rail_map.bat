@echo off
chcp 936 >nul
title TPF2 Rail Map

rem ---------------------------------------------------------------
rem  Thin entry point -- kept only because the desktop shortcut
rem  "TPF2 rail map" points at this file.
rem
rem  ALL the logic lives in rail-map-service.pyw (tray icon +
rem  service supervision + per-run logs). Do not add logic here.
rem
rem  Nothing to stop manually any more: use the tray icon
rem  (right click -> exit), so there is no stop script.
rem ---------------------------------------------------------------

set "PYW=C:\Users\RailG\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
set "APP=E:\workbody\TPF2Mcp\rail-map-service.pyw"
set "URL=http://127.0.0.1:8790/?view=network"

if not exist "%PYW%" goto no_pythonw
if not exist "%APP%" goto no_app

rem  Already running? then just open the page, do not start a second one.
netstat -ano | findstr ":8790" | findstr "LISTENING" >nul
if not errorlevel 1 goto already_running

start "" "%PYW%" "%APP%"
goto :eof

:already_running
echo  Service is already running - opening the page.
start "" "%URL%"
goto :eof

:no_pythonw
echo  ERROR: pythonw.exe not found at
echo    %PYW%
pause
goto :eof

:no_app
echo  ERROR: rail-map-service.pyw not found at
echo    %APP%
pause
goto :eof
