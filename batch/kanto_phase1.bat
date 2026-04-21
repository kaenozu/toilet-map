@echo off
chcp 65001 >nul 2>&1

echo ============================================
echo   Kanto Phase 1 Scraper
echo   Target: 7 prefecture capitals
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"

REM Pythonスクリプトを実行
python "%SCRIPT_DIR%kanto_phase1.py" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Phase 1 scraping failed.
    echo Check the logs above for details.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Phase 1 completed successfully!
echo ============================================
echo.
pause
exit /b 0