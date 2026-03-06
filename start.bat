@echo off
REM ─────────────────────────────────────────────
REM  School Management System — Startup Script
REM  For Windows
REM ─────────────────────────────────────────────

echo.
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Please download it from https://python.org/downloads
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
echo  Python found!

REM Move to script directory
cd /d "%~dp0"

REM Kill any previous server running on port 8080
echo.
echo  Checking for existing server on port 8080...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8080 "') do (
    echo  Stopping old server (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak > nul

echo.
echo ==========================================
echo   GISL Schools Management System
echo   Starting up...
echo ==========================================
echo.

REM Start the server in background
start /b python server.py

REM Wait 2 seconds then open browser
timeout /t 2 /nobreak > nul
start http://localhost:8080

echo  App running at: http://localhost:8080
echo.
echo  Login Details:
echo    Email:    admin@school.com
echo    Password: admin123
echo.
echo  Press Ctrl+C or close this window to stop the server.
echo.
pause
