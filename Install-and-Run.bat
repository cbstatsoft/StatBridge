@echo off
setlocal
cd /d "%~dp0"
for %%V in (3.12 3.13 3.11) do (
  py -%%V -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    py -%%V install.py %*
    goto finished
  )
)
python install.py %*
:finished
set "statbridge_exit=%errorlevel%"
if not "%statbridge_exit%"=="0" pause
exit /b %statbridge_exit%
