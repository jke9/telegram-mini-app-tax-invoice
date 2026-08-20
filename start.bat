@echo off
title JKE Tax Invoice Generator - Servers
color 0A
echo.
echo  =====================================================
echo    JKE TAX INVOICE GENERATOR — STARTING SERVERS
echo  =====================================================
echo.
echo  [1] Frontend  →  http://localhost:8030
echo  [2] API       →  http://localhost:8031
echo.
echo  Starting API backend (port 8031)...
start "API Server - Port 8031" cmd /k "cd /d %~dp0 && python api_server.py"
timeout /t 2 /nobreak >nul

echo  Starting Frontend server (port 8030)...
start "Frontend - Port 8030" cmd /k "cd /d %~dp0 && python server.py"
timeout /t 2 /nobreak >nul

echo.
echo  Both servers are running! Opening Mini App in browser...
timeout /t 1 /nobreak >nul
start http://localhost:8030

echo.
echo  Press any key to close this launcher window.
pause >nul
