@echo off
title Jullie Assistant
cd /d "%~dp0"
py -3.12 jullie.py
echo.
echo Jullie has stopped. Press any key to close this window.
pause >nul