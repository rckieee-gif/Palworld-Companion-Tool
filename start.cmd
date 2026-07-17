@echo off
title Palworld Companion Tools
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start.py
) else (
    python start.py
)

set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
