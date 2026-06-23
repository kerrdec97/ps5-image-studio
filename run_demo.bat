@echo off
REM ── Lazy_MkPFS Studio — DEMO (no real files touched) ──
setlocal
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul || set "PY=py -3"

echo Launching Lazy_MkPFS Studio (DEMO) with %PY% ...
echo.
%PY% run_studio.py --demo

echo.
echo ============================================================
echo Studio exited with code %errorlevel%.
echo If it crashed, see logs\crash.log and logs\studio.log
echo ============================================================
pause
