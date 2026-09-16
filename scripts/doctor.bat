@echo off
setlocal
cd /d "%~dp0\.."
echo ============================================
echo  EVA Doctor - Phase 1
echo ============================================

set OK=0
set FAIL=0

REM 1. Python
where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found in PATH
    set /a FAIL+=1
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK]   %%v
    set /a OK+=1
)

REM 2. Virtual environment
if exist ".venv\Scripts\python.exe" (
    echo [OK]   Virtual environment: .venv
    set /a OK+=1
) else (
    echo [FAIL] Virtual environment .venv not found
    set /a FAIL+=1
)

REM 3. Config files
if exist "config\config.yaml" (
    echo [OK]   config\config.yaml
    set /a OK+=1
) else (
    echo [FAIL] config\config.yaml missing
    set /a FAIL+=1
)

if exist "config\user_config.yaml" (
    echo [OK]   config\user_config.yaml
) else (
    echo [WARN] config\user_config.yaml missing (created on first save)
)

REM 4. .env
if exist ".env" (
    echo [OK]   .env present
    set /a OK+=1
) else (
    echo [WARN] .env missing - copy .env.example to .env
)

REM 5. Data directories
if exist "data\logs" (
    echo [OK]   data\logs
    set /a OK+=1
) else (
    echo [FAIL] data\logs missing
    set /a FAIL+=1
)

if exist "data\archive" (
    echo [OK]   data\archive
) else (
    echo [WARN] data\archive missing
)

REM 6. Python packages
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import httpx, yaml, dotenv, pydantic" >nul 2>nul
    if errorlevel 1 (
        echo [FAIL] Required packages missing ^(run: pip install -r requirements.txt^)
        set /a FAIL+=1
    ) else (
        echo [OK]   Required packages importable
        set /a OK+=1
    )
)

echo ============================================
echo  OK: %OK%    FAIL: %FAIL%
echo ============================================
if %FAIL% GTR 0 exit /b 1
endlocal