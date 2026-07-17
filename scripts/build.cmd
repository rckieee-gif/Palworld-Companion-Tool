@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" build\nuitka\build_nuitka.py --standalone
exit /b %errorlevel%
