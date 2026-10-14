@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call Install-and-Run.bat --terminal %*
  exit /b
)
.venv\Scripts\python.exe -c "import curses" >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install "windows-curses>=2.4,<3"
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe launch.py --terminal %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Terminal startup failed. Read the error above.
pause
exit /b 1
