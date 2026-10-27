@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Melovia Launcher

:: Ensure local tool directories are in PATH
set "PATH=%USERPROFILE%\.local\bin;%APPDATA%\npm;%ProgramFiles%\nodejs;%PATH%"

cls
echo ====================================================================
echo                        MELOVIA LAUNCHER
echo          Explainable, Steerable Music Discovery Engine
echo ====================================================================
echo.

:: 1. Verify uv exists
where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 'uv' was not found in your PATH.
    echo Please install uv from: https://docs.astral.sh/uv/
    echo Or run in PowerShell:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    pause
    exit /b 1
)

:: 2. Verify pnpm exists
where pnpm >nul 2>&1
if errorlevel 1 (
    where pnpm.cmd >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] 'pnpm' was not found in your PATH.
        echo Please install pnpm by running:
        echo   npm install -g pnpm
        echo.
        pause
        exit /b 1
    )
)

:: 3. Setup .env if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env from .env.example...
        copy /y ".env.example" ".env" >nul
    )
)

:: 4. Verify catalog bundle exists
if not exist "data\bundles\v1\manifest.json" (
    echo [INFO] Catalog bundle not found. Generating mock catalog bundle...
    uv run --directory api python ../fixtures/make_mock_catalog.py
    if errorlevel 1 (
        echo [ERROR] Failed to generate catalog bundle.
        pause
        exit /b 1
    )
)

:: 5. Verify database exists
if not exist "api\melovia.db" (
    echo [INFO] Database not found. Seeding SQLite database...
    uv run --directory api python ../fixtures/seed_db.py
)

:: 6. Clean any zombie processes on port 8000 and 3000
echo [INFO] Checking for lingering processes on ports 8000 and 3000...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 3000; $pids = Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } } ; exit 0" >nul 2>&1

:launch_servers
echo.
echo [INFO] Launching FastAPI backend server on port 8000...
start "Melovia API Backend (Port 8000)" "%~dp0scripts\start_api.bat"

echo [INFO] Launching Next.js frontend dev server on port 3000...
start "Melovia Web Frontend (Port 3000)" "%~dp0scripts\start_web.bat"

echo.
echo [INFO] Waiting for servers to initialize...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ready = $false; for ($i=0; $i -lt 40; $i++) { try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ready = $true; break } } catch {} Start-Sleep -Milliseconds 500 }; if ($ready) { exit 0 } else { exit 1 }"

echo.
echo [INFO] Opening Melovia in your default browser...
start http://localhost:3000

:menu
cls
echo ====================================================================
echo                        MELOVIA MUSIC SYSTEM
echo             Explainable, Steerable Recommendation Engine
echo ====================================================================
echo   [RUNNING] Backend API : http://127.0.0.1:8000
echo   [RUNNING] Frontend Web: http://localhost:3000
echo   [RUNNING] API Docs    : http://127.0.0.1:8000/docs
echo ====================================================================
echo   Both servers are running in separate dedicated console windows.
echo   The Web UI has opened in your default web browser.
echo.
echo   Interactive Actions:
echo     [O] Open Web UI in browser (http://localhost:3000)
echo     [D] Open API Documentation (http://127.0.0.1:8000/docs)
echo     [S] Stop all servers and exit
echo     [R] Restart both servers
echo     [Q] Close this launcher menu (servers will keep running)
echo ====================================================================
choice /C ODSRQ /N /M "Select an option [O, D, S, R, Q]: "
if errorlevel 5 exit /b 0
if errorlevel 4 goto restart_servers
if errorlevel 3 goto stop_servers
if errorlevel 2 goto open_docs
if errorlevel 1 goto open_web

:open_web
start http://localhost:3000
goto menu

:open_docs
start http://127.0.0.1:8000/docs
goto menu

:restart_servers
echo.
echo [INFO] Stopping running servers...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 3000; $pids = Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } } ; exit 0" >nul 2>&1
ping 127.0.0.1 -n 3 >nul 2>&1
goto launch_servers

:stop_servers
echo.
echo [INFO] Stopping all Melovia servers...
call "%~dp0stop.bat"
exit /b 0
