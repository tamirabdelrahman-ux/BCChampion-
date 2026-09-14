@echo off
cd /d "%~dp0"
if exist "dist\BCChampion_Stop.exe" (
    start "" "dist\BCChampion_Stop.exe"
    exit /b 0
)
echo BCChampion_Stop.exe has not been built yet.
echo Please run SETUP_BCCHAMPION.bat first.
pause
