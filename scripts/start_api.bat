@echo off
setlocal
cd /d "%~dp0..\api"
title Melovia API Backend (Port 8000)
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

echo ====================================================================
echo                  MELOVIA FASTAPI BACKEND SERVER
echo                     http://127.0.0.1:8000
echo                     Docs: http://127.0.0.1:8000/docs
echo ====================================================================
echo.

uv run uvicorn app.main:app --port 8000 --host 127.0.0.1 --reload

if errorlevel 1 (
    echo.
    echo [ERROR] Backend server stopped unexpectedly.
    pause
)
