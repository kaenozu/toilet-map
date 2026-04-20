@echo off
chcp 65001 >nul 2>&1

echo ============================================
echo   Toilet Map - Kumagaya Scraper
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "QUERIES_FILE=%SCRIPT_DIR%queries.txt"
set "RAW_DIR=%SCRIPT_DIR%raw_parts"
set "RAW_OUTPUT=%SCRIPT_DIR%raw_data.json"
set "PROCESSED=%SCRIPT_DIR%..\data\toilets.json"
set "PROGRESS_FILE=%SCRIPT_DIR%.progress"

set "SLEEP_BETWEEN=120"
set "MAX_RETRIES=2"
set "RETRY_SLEEP=300"

if "%~1"=="--reset" (
    if exist "%PROGRESS_FILE%" del /q "%PROGRESS_FILE%"
    if exist "%RAW_DIR%" rmdir /s /q "%RAW_DIR%"
    echo Progress cleared.
    echo.
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Start Docker Desktop first.
    pause
    exit /b 1
)

if not exist "%QUERIES_FILE%" (
    echo [ERROR] queries.txt not found
    pause
    exit /b 1
)

echo Starting scrape via Python wrapper...
echo.

python "%SCRIPT_DIR%scrape_runner.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Scraping failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   All done!
echo ============================================
echo.
pause
exit /b 0
