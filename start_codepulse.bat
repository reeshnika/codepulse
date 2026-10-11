@echo off
title CodePulse Launcher
echo ============================================================
echo   Starting CodePulse Platform
echo ============================================================

echo [1/3] Starting Backend Server on port 5000...
start "CodePulse Backend" cmd /k ".\venv\Scripts\python.exe backend/app.py"

echo [2/3] Waiting 2 seconds for server startup...
timeout /t 2 /nobreak >nul

echo [3/3] Launching CodePulse Dashboard in browser...
start http://localhost:5000

echo.
echo ============================================================
echo   Starting CodePulse Agent (Keystroke & Flow Monitor)
echo   Type in any window to generate flow analytics!
echo   Press ESC or Ctrl+C to stop.
echo ============================================================
echo.

.\venv\Scripts\python.exe agent/agent.py
pause
