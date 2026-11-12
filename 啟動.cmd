@echo off
setlocal
set "DUALMIRROR_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%DUALMIRROR_PYTHON%" (
  echo Python 3.12 was not found. See DEVELOPER.md for setup.
  pause
  exit /b 2
)
start "" /D "%~dp0" "%DUALMIRROR_PYTHON%" "%~dp0main.py"
