@echo off
title CodePulse Dashboard Server
cd /d C:\codepulse\codepulse
set PYTHONPATH=.
echo ============================================================
echo   ⚡ CodePulse Dashboard Server
echo   Web UI: http://localhost:5000/
echo ============================================================
echo.
python backend/app.py
pause
