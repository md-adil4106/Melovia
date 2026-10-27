@echo off
setlocal
cd /d "%~dp0..\web"
title Melovia Web Frontend (Port 3000)
set "PATH=%APPDATA%\npm;%ProgramFiles%\nodejs;%PATH%"

echo ====================================================================
echo                  MELOVIA NEXT.JS WEB FRONTEND
echo                     http://localhost:3000
echo ====================================================================
echo.

pnpm dev

if errorlevel 1 (
    echo.
    echo [ERROR] Frontend dev server stopped unexpectedly.
    pause
)
