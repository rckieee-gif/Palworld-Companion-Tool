@echo off
title Update Game Data
cd /d "%~dp0\.."
where uv >nul 2>&1 || (
    echo uv not found. Install from https://docs.astral.sh/uv/
    pause
    exit /b 1
)
if exist .venv\Scripts\python.exe (
    rmdir /s /q .venv
)
uv venv .venv
uv pip install --no-cache -r requirements.txt
".venv\Scripts\python.exe" scripts\scrs\update_game_data.py %*
if exist uv.lock del uv.lock
pause
exit /b %errorlevel%
