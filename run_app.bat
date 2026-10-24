@echo off
title EchoBridge Offline Speech Translator
cd /d "%~dp0"
echo Starting EchoBridge Offline Translator...
call .venv\Scripts\activate.bat
python app.py
pause
