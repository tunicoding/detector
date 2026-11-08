@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Once kurulum.bat dosyasini calistirin.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" detector.py %*
if errorlevel 1 pause
