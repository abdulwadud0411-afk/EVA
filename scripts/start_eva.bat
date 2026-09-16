@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo [EVA] Virtual environment not found.
    echo [EVA] Run: python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    exit /b 1
)

".venv\Scripts\python.exe" -m app.main
endlocal