@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Stop Melovia

echo ====================================================================
echo                   STOPPING MELOVIA SERVERS
echo ====================================================================
echo Shutting down processes on ports 8000 (API) and 3000 (Web)...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 3000; $pids = Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { try { $proc = Get-Process -Id $p -ErrorAction SilentlyContinue; if ($proc) { Write-Host ('[INFO] Terminating PID ' + $p + ' (' + $proc.ProcessName + ')...'); Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } } catch {} }; Write-Host '[SUCCESS] All Melovia server processes have been stopped.' } else { Write-Host '[INFO] No running Melovia servers found on ports 8000 or 3000.' }; exit 0"

echo ====================================================================
echo Melovia servers have been shut down cleanly.
echo ====================================================================
ping 127.0.0.1 -n 3 >nul 2>&1
exit /b 0
