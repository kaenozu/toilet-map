@echo off
chcp 65001 >nul 2>&1

echo ============================================
echo   Toilet Map Scraper
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"

if "%~1"=="" (
    set "QUERIES=%SCRIPT_DIR%queries.txt"
) else (
    set "QUERIES=%~1"
)

if not exist "%QUERIES%" (
    echo [ERROR] Queries file not found: %QUERIES%
    echo.
    echo Usage: scrape.bat [queries_file] [--city CITY] [--prefecture PREF] [--reset]
    echo   scrape.bat queries.d\Saitama\batch_001.txt
    pause
    exit /b 1
)

echo Queries: %QUERIES%
echo.

echo "%~2" | find "--reset" >nul 2>&1
if not errorlevel 1 (
    if exist "%SCRIPT_DIR%.progress" del /q "%SCRIPT_DIR%.progress"
    if exist "%SCRIPT_DIR%raw_parts" rmdir /s /q "%SCRIPT_DIR%raw_parts"
    echo Progress cleared.
    echo.
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running.
    pause
    exit /b 1
)

echo Starting scrape...
echo.

python "%SCRIPT_DIR%scrape_runner.py" %*

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
