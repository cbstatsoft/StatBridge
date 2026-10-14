@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Install-and-Run.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe launch.py %*
set "statbridge_exit=%errorlevel%"
if not "%statbridge_exit%"=="0" pause
exit /b %statbridge_exit%
