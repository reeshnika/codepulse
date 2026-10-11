@echo off
title CodePulse Agent
cd /d C:\codepulse\codepulse
set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
echo ============================================================
echo   CodePulse Keystroke Agent
echo   Interactive Keyboard Telemetry Collector
echo ============================================================
echo.
python -u -m agent.agent
pause
