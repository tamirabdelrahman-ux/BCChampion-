@echo off
cd /d "%~dp0"
if exist "dist\BCChampion.exe" (
    start "" "dist\BCChampion.exe"
    exit /b 0
)
echo BCChampion.exe has not been built yet.
echo Please double-click SETUP_BCCHAMPION.bat first.
pause
