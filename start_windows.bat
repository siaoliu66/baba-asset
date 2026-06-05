@echo off
echo ===================================================
echo   Asset Management System 2026 - Windows Startup
echo ===================================================

:: 1. Check Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b
)

:: 2. Check/Create .venv
if not exist ".venv" (
    echo [SYSTEM] Creating virtual environment .venv ...
    python -m venv .venv
    echo [SYSTEM] Virtual environment created.
)

:: 3. Activate and Install
echo [SYSTEM] Activating virtual environment...
call .venv\Scripts\activate.bat

if exist "requirements.txt" (
    echo [SYSTEM] Installing dependencies...
    pip install -r requirements.txt
) else (
    echo [WARNING] requirements.txt not found.
)

:: 4. Start App
echo ===================================================
echo [SYSTEM] Starting application...
echo ===================================================
echo.

python run.py

if %errorlevel% neq 0 (
    echo.
    echo ===================================================
    echo [ERROR] Application crashed (Code: %errorlevel%)
    echo ===================================================
)

pause
