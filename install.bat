@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Visual Measurement ^& Metrology Studio
echo  Install
echo ============================================

set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
)
echo %PYEXE% | findstr /I "WindowsApps" >nul
if not errorlevel 1 set "PYEXE="
if not defined PYEXE (
    echo [ERROR] Python 3.10+ was not found.
    echo Install Python from python.org and enable the py launcher.
    echo The Microsoft Store alias "python.exe" cannot be used.
    pause
    exit /b 1
)

"%PYEXE%" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.10 or newer is required.
    pause
    exit /b 1
)
echo Using Python: %PYEXE%

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%PYEXE%" -m venv .venv
    if errorlevel 1 goto :fail
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo Preparing folders, OpenCV, ArUco, camera check and smoke test...
".venv\Scripts\python.exe" tests\install_check.py
if errorlevel 1 goto :fail

echo.
echo Install finished.
echo Start the application with start.bat
pause
exit /b 0

:fail
echo.
echo Install failed. See the messages above.
pause
exit /b 1
