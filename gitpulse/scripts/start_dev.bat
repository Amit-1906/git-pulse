@echo off
:: GitPulse — Development launcher (Windows CMD/batch)
:: Opens two separate PowerShell windows: one for backend, one for frontend.

setlocal
set "SCRIPTS=%~dp0"
set "ROOT=%SCRIPTS%.."

echo.
echo  ================================================
echo    GitPulse  ^|  Development Launcher
echo  ================================================
echo.
echo  [1/2] Starting FastAPI backend  ...
start "GitPulse Backend"  powershell -NoExit -ExecutionPolicy Bypass -File "%SCRIPTS%start_backend.ps1"

timeout /t 3 /nobreak >nul

echo  [2/2] Starting Streamlit frontend ...
start "GitPulse Frontend" powershell -NoExit -ExecutionPolicy Bypass -File "%SCRIPTS%start_frontend.ps1"

echo.
echo  Services starting in separate windows:
echo    Backend  →  http://localhost:8000
echo    API Docs →  http://localhost:8000/docs
echo    Frontend →  http://localhost:8501
echo.
echo  Close those windows (or press Ctrl+C inside them) to stop the services.
echo.
pause
endlocal

