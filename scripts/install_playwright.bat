@echo off
setlocal
cd /d "%~dp0\.."

echo ============================================
echo  EVA - Playwright Browser Installer
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [FAIL] Virtual environment .venv not found.
    echo [FAIL] Run: python -m venv .venv
    exit /b 1
)

echo [1/2] Installing playwright package (if not present)...
".venv\Scripts\python.exe" -m pip install "playwright>=1.40"
if errorlevel 1 (
    echo [FAIL] pip install playwright failed.
    exit /b 1
)

echo.
echo [2/2] Downloading Chromium browser (one-time, ~150 MB)...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo [FAIL] playwright install chromium failed.
    exit /b 1
)

echo.
echo ============================================
echo  [OK] Playwright + Chromium installed.
echo ============================================
endlocal