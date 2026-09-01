@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please install dependencies first, see README.md.
    pause
    exit /b 1
)

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo Service is already running. Opening browser...
    start "" http://127.0.0.1:8000/
    exit /b 0
)

.venv\Scripts\python.exe server.py
pause
