@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

echo ============================================
echo  EVA Doctor - Full Diagnostics
echo ============================================
echo.

set OK=0
set FAIL=0
set WARN=0

REM ------------------------------------------------------------------ #
REM 1. Python
REM ------------------------------------------------------------------ #
where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found in PATH
    set /a FAIL+=1
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK]   %%v
    set /a OK+=1
)

REM ------------------------------------------------------------------ #
REM 2. Virtual environment
REM ------------------------------------------------------------------ #
if exist ".venv\Scripts\python.exe" (
    echo [OK]   Virtual environment: .venv
    set /a OK+=1
) else (
    echo [FAIL] .venv missing - run scripts\install.bat
    set /a FAIL+=1
)

REM ------------------------------------------------------------------ #
REM 3. Config files
REM ------------------------------------------------------------------ #
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
    echo [WARN] config\user_config.yaml missing ^(created on first save^)
    set /a WARN+=1
)

if exist "config\permissions.yaml" (
    echo [OK]   config\permissions.yaml
    set /a OK+=1
) else (
    echo [WARN] config\permissions.yaml missing
    set /a WARN+=1
)

if exist "config\network_whitelist.yaml" (
    echo [OK]   config\network_whitelist.yaml
    set /a OK+=1
) else (
    echo [WARN] config\network_whitelist.yaml missing
    set /a WARN+=1
)

REM ------------------------------------------------------------------ #
REM 4. .env file
REM ------------------------------------------------------------------ #
if exist ".env" (
    echo [OK]   .env present
    set /a OK+=1

    findstr /B /C:"DEEPSEEK_API_KEY=" .env | findstr /V /C:"DEEPSEEK_API_KEY=$" >nul
    if errorlevel 1 (
        echo [WARN] DEEPSEEK_API_KEY is empty - EVA brain won't work
        set /a WARN+=1
    ) else (
        echo [OK]   DEEPSEEK_API_KEY set
        set /a OK+=1
    )
) else (
    echo [FAIL] .env missing - copy .env.example to .env
    set /a FAIL+=1
)

REM ------------------------------------------------------------------ #
REM 5. Data directories
REM ------------------------------------------------------------------ #
for %%d in (
    "data"
    "data\logs"
    "data\screenshots"
    "data\recordings"
    "data\knowledge"
    "data\workspace"
    "data\security"
) do (
    if exist %%d (
        echo [OK]   %%d
    ) else (
        echo [WARN] %%d missing ^(created on first use^)
        set /a WARN+=1
    )
)

REM ------------------------------------------------------------------ #
REM 6. Python packages - core
REM ------------------------------------------------------------------ #
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import httpx, yaml, dotenv, pydantic" >nul 2>nul
    if errorlevel 1 (
        echo [FAIL] Core packages missing ^(run: pip install -r requirements.txt^)
        set /a FAIL+=1
    ) else (
        echo [OK]   Core packages ^(httpx, yaml, dotenv, pydantic^)
        set /a OK+=1
    )

    REM 6b. cryptography
    ".venv\Scripts\python.exe" -c "import cryptography" >nul 2>nul
    if errorlevel 1 (
        echo [WARN] cryptography missing ^(licensing/security disabled^)
        set /a WARN+=1
    ) else (
        echo [OK]   cryptography
        set /a OK+=1
    )

    REM 6c. psutil
    ".venv\Scripts\python.exe" -c "import psutil" >nul 2>nul
    if errorlevel 1 (
        echo [WARN] psutil missing ^(system monitor disabled^)
        set /a WARN+=1
    ) else (
        echo [OK]   psutil
        set /a OK+=1
    )

    REM 6d. PySide6
    ".venv\Scripts\python.exe" -c "import PySide6" >nul 2>nul
    if errorlevel 1 (
        echo [WARN] PySide6 missing ^(GUI disabled^)
        set /a WARN+=1
    ) else (
        echo [OK]   PySide6 ^(GUI^)
        set /a OK+=1
    )

    REM 6e. Voice - faster-whisper
    ".venv\Scripts\python.exe" -c "import faster_whisper" >nul 2>nul
    if errorlevel 1 (
        echo [WARN] faster-whisper missing ^(voice STT disabled^)
        set /a WARN+=1
    ) else (
        echo [OK]   faster-whisper ^(STT^)
        set /a OK+=1
    )

    REM 6f. Voice - edge-tts
    ".venv\Scripts\python.exe" -c "import edge_tts" >nul 2>nul
    if errorlevel 1 (
        echo [WARN] edge-tts missing ^(cloud TTS disabled^)
        set /a WARN+=1
    ) else (
        echo [OK]   edge-tts ^(TTS^)
        set /a OK+=1
    )
)

REM ------------------------------------------------------------------ #
REM 7. Memory database
REM ------------------------------------------------------------------ #
if exist "data\eva.db" (
    echo [OK]   data\eva.db exists
    set /a OK+=1
) else (
    echo [WARN] data\eva.db not created yet ^(first run will create^)
    set /a WARN+=1
)

REM ------------------------------------------------------------------ #
REM 8. Ollama check (Phase 18)
REM ------------------------------------------------------------------ #
where ollama >nul 2>nul
if errorlevel 1 (
    echo [WARN] Ollama not found in PATH ^(optional local LLM^)
    set /a WARN+=1
) else (
    echo [OK]   Ollama installed
    set /a OK+=1
)

REM ------------------------------------------------------------------ #
REM 9. License public key (Phase 22)
REM ------------------------------------------------------------------ #
if exist "config\license_public_key.pem" (
    findstr /C:"REPLACE_ME" "config\license_public_key.pem" >nul 2>nul
    if errorlevel 1 (
        echo [OK]   License public key installed
        set /a OK+=1
    ) else (
        echo [WARN] License public key is still placeholder
        set /a WARN+=1
    )
) else (
    echo [WARN] config\license_public_key.pem missing
    set /a WARN+=1
)

REM ------------------------------------------------------------------ #
REM 10. PyInstaller (Phase 22 Batch 4)
REM ------------------------------------------------------------------ #
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>nul
    if errorlevel 1 (
        echo [WARN] PyInstaller not installed ^(needed for build_exe.bat^)
        set /a WARN+=1
    ) else (
        echo [OK]   PyInstaller installed
        set /a OK+=1
    )
)

REM ------------------------------------------------------------------ #
REM 11. Summary
REM ------------------------------------------------------------------ #
echo.
echo ============================================
echo  OK: %OK%    WARN: %WARN%    FAIL: %FAIL%
echo ============================================

if %FAIL% GTR 0 (
    echo.
    echo Some critical checks failed. Fix FAIL items and re-run.
    pause
    exit /b 1
)

echo.
echo All critical checks passed. EVA is ready.
echo.
pause
endlocal