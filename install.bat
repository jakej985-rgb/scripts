@echo off
setlocal enabledelayedexpansion

:: M3TAL Media Server — Windows Bootstrap Script
:: v2.2.0 — Launch & Exit

:: Set Colors
set GREEN=[32m
set YELLOW=[33m
set BOLD=[1m
set END=[0m

echo %BOLD%=== M3TAL Media Server Installer (Windows Bootstrap) ===%END%
echo.

:: 1. Environment Check
echo [1/2] Checking for Python...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo %YELLOW%[WARN] Python not found in PATH.%END%
        echo Please install Python from https://www.python.org/
        pause
        exit /b 1
    ) else (
        set PY_CMD=py
    )
) else (
    set PY_CMD=python
)

echo [1/2] Checking for Git...
where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %YELLOW%[WARN] Git not found in PATH.%END%
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

:: 2. Repository Setup
if not exist install.py (
    echo %YELLOW%[WARN] install.py not found in current directory.%END%
    set /p CLONE="Would you like to clone M3TAL Media Server now? (y/n) "
    if /i "!CLONE!"=="y" (
        git clone https://github.com/jakej985-rgb/M3tal-Media-Server.git
        cd M3tal-Media-Server
    ) else (
        echo Exiting.
        pause
        exit /b 1
    )
) else (
    echo [OK] Valid M3TAL repository found.
    echo Pulling latest updates from GitHub...
    git pull
)

:: 3. Hand off to Python
echo.
echo %GREEN%[OK] Bootstrap complete.%END%
echo Launching M3TAL Interactive Installer in a new window...

:: Launch in a separate window and exit this batch file
start "M3TAL Media Server Installer" %PY_CMD% install.py %*

echo.
echo %BOLD%[SUCCESS] Installer has taken over in the new window.%END%
echo This bootstrap window will close in 3 seconds.
timeout /t 3 >nul
exit
