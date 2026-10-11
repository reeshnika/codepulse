@echo off
title CodePulse Agent
cd /d C:\codepulse\codepulse
set PYTHONPATH=.
echo ============================================================
echo   🚀 CodePulse Keystroke Agent
echo   Interactive Keyboard Telemetry Collector
echo ============================================================
echo.
python -u agent/agent.py
pause
