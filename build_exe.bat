@echo off
REM ── Build a standalone Windows .exe with PyInstaller ──
setlocal
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul || set "PY=py -3"

echo Installing build dependencies ...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements-build.txt
if errorlevel 1 (
  echo.
  echo *** Dependency install failed. See messages above. ***
  pause
  exit /b 1
)

echo.
echo Installing optional fast backends (zlib-ng, isal) — non-fatal if they fail ...
%PY% -m pip install zlib-ng isal

echo.
echo Cleaning previous build ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Running PyInstaller ...
REM Admin elevation (requireAdministrator UAC manifest) is set via uac_admin=True
REM in PS5ImageStudio.spec. PyInstaller ignores CLI flags like --uac-admin when a
REM .spec file is given, so the manifest MUST live in the spec, not here.
%PY% -m PyInstaller --noconfirm --clean PS5ImageStudio.spec
if errorlevel 1 (
  echo.
  echo *** Build FAILED. See messages above. ***
  pause
  exit /b 1
)

echo.
echo ============================================================
echo Build complete.
echo   Run it:  dist\PS5ImageStudio\PS5ImageStudio.exe
echo   Demo:    dist\PS5ImageStudio\PS5ImageStudio.exe --demo
echo ============================================================
pause
