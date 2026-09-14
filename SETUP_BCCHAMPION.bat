@echo off
setlocal
cd /d "%~dp0"
title BCChampion Setup

echo ============================================================
echo BCChampion Windows Desktop v1.0.0 - One-time Setup
echo ============================================================
echo.
echo This setup creates a private Python environment inside this
echo BCChampion folder and installs the required packages.
echo It does NOT install BCChampion system-wide.
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py"
    goto :havepython
)

where python >nul 2>&1
if %errorlevel%==0 (
    set "PY=python"
    goto :havepython
)

echo Python was not found on this computer.
echo.
echo For this source build, Python 3 is needed to build/run the app.
echo The final BCChampion.exe will not require Python.
echo.
echo Please install Python 3 from:
echo https://www.python.org/downloads/windows/
echo.
echo IMPORTANT: during installation select "Add python.exe to PATH".
echo Then close this window and double-click SETUP_BCCHAMPION.bat again.
echo.
pause
exit /b 1

:havepython
echo [1/4] Creating BCChampion private environment...
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
    if errorlevel 1 goto :failed
)

echo [2/4] Updating package installer...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed

echo [3/4] Installing BCChampion requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo [4/4] Installing PyInstaller and building Windows executables...
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto :failed

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean BCChampion.spec
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean BCChampion_Stop.spec
if errorlevel 1 goto :failed

echo.
echo ============================================================
echo SETUP COMPLETE
echo ============================================================
echo.
echo Your BCChampion runnable program is in:
echo   dist\BCChampion.exe
echo.
echo Double-click RUN_BCCHAMPION.bat to start BCChampion.
echo You can use sample_data for your first test.
echo.
pause
exit /b 0

:failed
echo.
echo ============================================================
echo SETUP DID NOT COMPLETE
echo ============================================================
echo Please take a screenshot of the error above and send it to me.
echo.
pause
exit /b 1
