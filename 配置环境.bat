@echo off
cd /d "%~dp0"
echo ==========================================
echo   IELTS Workbench - One-click Setup
echo ==========================================

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "print(1)" >nul 2>nul
    if not errorlevel 1 goto deps
    echo Existing venv is broken. Recreating...
    rmdir /s /q venv
)

where py >nul 2>nul
if not errorlevel 1 (
    echo [1/2] Creating virtual environment (py launcher)...
    py -3 -m venv venv
    goto checkvenv
)

for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        echo [1/2] Creating virtual environment (Python 3.%%V)...
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -m venv venv
        goto checkvenv
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    echo [1/2] Creating virtual environment (python)...
    python -m venv venv
    goto checkvenv
)

where winget >nul 2>nul
if not errorlevel 1 (
    echo Python not found. Installing Python 3.11 via winget...
    winget install -e --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -m venv venv
        goto checkvenv
    )
)

echo.
echo Cannot install Python automatically. Please install Python 3.10+
echo manually from https://www.python.org/downloads/
echo (check "Add python.exe to PATH" during install), then re-run this.
pause
exit /b 1

:checkvenv
if not exist "venv\Scripts\python.exe" (
    echo Failed to create venv. Please retry.
    pause
    exit /b 1
)

:deps
echo [2/2] Installing dependencies (fastapi / uvicorn / watchdog)...
"venv\Scripts\python.exe" -m pip install --upgrade pip fastapi uvicorn watchdog
if errorlevel 1 (
    echo Failed to install dependencies. Check internet and retry.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Done! Now run the start script.
echo ==========================================
pause
