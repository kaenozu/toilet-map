@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   Toilet Map - Quick Data Update
echo   Runs nationwide scrape + verification
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"

REM Step 1: Scrape nationwide
echo [1/3] Running nationwide scrape pipeline...
python "%SCRIPT_DIR%nationwide_runner.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Nationwide scrape failed.
    pause
    exit /b 1
)

REM Step 2: Sync JSON to SQLite
echo.
echo [2/3] Syncing JSON to SQLite...
python "%SCRIPT_DIR%sync_db.py"
if errorlevel 1 (
    echo.
    echo [ERROR] SQLite sync failed.
    pause
    exit /b 1
)

REM Step 3: Verify synced data
echo.
echo [3/3] Verifying synced data...
python "%SCRIPT_DIR%verify_data.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Verification failed. Review the quality gate output before publishing.
    pause
    exit /b 1
)

REM Final step: Done
echo.
echo [3/3] All done!
echo Updated files:
echo   - data\toilets.json.gz
echo   - data\toilets.db
echo Run: streamlit run app.py
echo.
pause
exit /b 0
