@echo off
title EchoBridge Web Server
echo.
echo  =====================================================
echo   EchoBridge Web Server
echo  =====================================================
echo.

cd /d "%~dp0"

REM Try FastAPI server first (richer API), fall back to lite server
.venv\Scripts\python.exe -c "import fastapi" 2>nul
if %errorlevel% == 0 (
    echo  Using FastAPI server...
    echo  Open http://localhost:8000 in your browser
    echo.
    .venv\Scripts\python.exe web_server.py
) else (
    echo  Using Lite server (no extra dependencies)...
    echo  Open http://localhost:8000 in your browser
    echo.
    .venv\Scripts\python.exe web_server_lite.py 8000
)

pause
