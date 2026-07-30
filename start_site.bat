@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py"
) else (
    set "PYTHON_CMD=python"
)

start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000/'"
%PYTHON_CMD% server.py

echo.
echo Server stopped. Press any key to close this window.
pause >nul
