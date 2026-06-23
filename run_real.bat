@echo off
REM ── Lazy_MkPFS Studio — REAL builds ──
setlocal
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul || set "PY=py -3"

echo Launching Lazy_MkPFS Studio with %PY% ...
echo.
%PY% run_studio.py

echo.
echo ============================================================
echo Studio exited with code %errorlevel%.
echo If it crashed, see logs\crash.log and logs\studio.log
echo ============================================================
pause
