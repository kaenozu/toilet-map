@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   Toilet Map - Auto Data Expansion
echo   Detects underserved areas, scrapes,
echo   processes, and refreshes the database.
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "DATA_DIR=%SCRIPT_DIR%..\data"
set "PROCESSED=%DATA_DIR%\toilets.json.gz"

REM Step 1: Gap analysis (dry-run first to show plan)
echo [1/5] Analyzing data gaps...
echo.
python "%SCRIPT_DIR%verify_data.py"
if errorlevel 1 goto :fail
echo.
echo --- Gap Analysis Summary ---
python "%SCRIPT_DIR%gap_summary.py"
if errorlevel 1 goto :fail
echo.

REM Step 2: Auto expansion (top 3 underserved areas)
echo [2/5] Running auto expansion (max 3 areas)...
python "%SCRIPT_DIR%auto_expand.py" --max-areas 3
if errorlevel 1 (
    goto :fail
)

REM Step 3: Merge raw data files (if any were produced)
echo.
echo [3/5] Processing raw data (incremental merge)...
if exist "%SCRIPT_DIR%merged_raw.json" (
    python "%SCRIPT_DIR%process_data.py" "%SCRIPT_DIR%merged_raw.json" "%PROCESSED%" --incremental
    if errorlevel 1 goto :fail
)
REM Try each area's raw data file
for %%f in ("%SCRIPT_DIR%raw_data_*.json") do (
    echo   Processing: %%f
    python "%SCRIPT_DIR%process_data.py" "%%f" "%PROCESSED%" --incremental
    if errorlevel 1 goto :fail
)
echo.
echo [3/5] Syncing JSON to SQLite...
python "%SCRIPT_DIR%to_sqlite.py" "%PROCESSED%" --incremental
if errorlevel 1 (
    echo [WARN] SQLite incremental sync failed, trying full refresh...
    python "%SCRIPT_DIR%to_sqlite.py" "%PROCESSED%"
    if errorlevel 1 goto :fail
)
python "%SCRIPT_DIR%sync_db.py" "%PROCESSED%"
if errorlevel 1 goto :fail

REM Step 4: Verify
echo.
echo [4/5] Verifying expanded data...
python "%SCRIPT_DIR%verify_data.py"
if errorlevel 1 goto :fail

REM Step 5: Cleanup temp files
echo.
echo [5/5] Cleaning up temporary files...
call :cleanup

echo.
echo ============================================
echo   Expansion complete!
echo   Run: streamlit run app.py
echo ============================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================
echo   Pipeline failed. Check the error output above.
echo ============================================
echo.
call :cleanup
exit /b 1

:cleanup
for %%f in ("%SCRIPT_DIR%merged_raw.json" "%SCRIPT_DIR%raw_data_*.json") do (
    if exist "%%f" del "%%f"
)
for /d %%d in ("%SCRIPT_DIR%raw_parts_*") do (
    if exist "%%d" rmdir /s /q "%%d"
)
exit /b 0
