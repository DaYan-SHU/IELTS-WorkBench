@echo off
cd /d "%~dp0"

rem [1/3] Prefer the portable Python shipped on the USB drive (runtime, no install)
if exist "runtime\python.exe" (
    "runtime\python.exe" -c "print(1)" >nul 2>nul
    if not errorlevel 1 (
        "runtime\python.exe" start.py
        pause
        exit /b 0
    )
    echo [WARN] runtime python is broken, falling back to venv...
)

rem [2/3] Then try a venv configured on this PC
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "print(1)" >nul 2>nul
    if not errorlevel 1 (
        "venv\Scripts\python.exe" start.py
        pause
        exit /b 0
    )
)

rem [3/3] Nothing usable: guide the user
echo [ERROR] No usable Python found
echo         - If this PC has Python installed, run the setup script first
echo         - Or copy the complete "runtime" folder together with this program.
pause
exit /b 1
