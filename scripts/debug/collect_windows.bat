@echo off
setlocal
cd /d "%~dp0\..\.."
venv\Scripts\python.exe scripts\debug\collect_windows_debug_log.py
echo.
echo Debug collection complete.
echo Files generated in REPO_ROOT:
echo  - logs_windows.txt
echo  - error_log_windows.txt
pause
