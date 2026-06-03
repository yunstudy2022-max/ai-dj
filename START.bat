@echo off
chcp 65001 > nul 2>&1
cls

echo.
echo ================================================================
echo  claudio.fm Demo Launcher
echo ================================================================
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.7+ from https://www.python.org
    pause
    exit /b 1
)

cd /d "%~dp0"
echo Project: %cd%
echo.

if not exist ".env" (
    echo Creating .env from template...
    if exist ".env.example" (
        copy .env.example .env > nul
        echo Created .env - please edit it with your API keys
    )
)

echo Checking dependencies...
pip install -q requests python-dotenv psutil websockets 2>nul

cls
echo.
echo ================================================================
echo  Launch Options
echo ================================================================
echo.
echo [1] Quick Demo (1 batch, ~1-2 min)
echo [2] Full Demo (5 batches, ~5-10 min)
echo [3] Quick Test (5 min stress test)
echo [4] Full Test (2 hour stress test)
echo [0] Exit
echo.
set /p choice=Select [0-4]:

if "%choice%"=="1" (
    cls
    python scripts/demo.py --quick
) else if "%choice%"=="2" (
    cls
    python scripts/demo.py --extended
) else if "%choice%"=="3" (
    cls
    python scripts/stress-test.py --duration 5
) else if "%choice%"=="4" (
    cls
    python scripts/stress-test.py --duration 120
) else if "%choice%"=="0" (
    exit /b 0
) else (
    echo Invalid choice
    pause
    goto :start
)

pause
