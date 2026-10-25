@echo off
title JayantianAssist Server
echo Starting JayantianAssist Flask server...
cd /d "%~dp0"
".venv\Scripts\python.exe" "JayantianAssist-main\app.py"
pause
