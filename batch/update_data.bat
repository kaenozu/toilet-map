@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   Toilet Map - Quick Data Update
echo   Runs scraper + processor + verification
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"

REM Step 1: Scrape
echo [1/3] Running scraper...
python "%SCRIPT_DIR%scrape_runner.py" %*
if errorlevel 1 (
    echo.
    echo [ERROR] Scraping failed.
    pause
    exit /b 1
)

REM Step 2: Verify
echo.
echo [2/3] Verifying data...
python "%SCRIPT_DIR%verify_data.py"
if errorlevel 1 (
    echo.
    echo [WARN] Verification failed, but data was saved.
)

REM Step 3: Done
echo.
echo [3/3] All done!
echo Run: streamlit run app.py
echo.
pause
exit /b 0
