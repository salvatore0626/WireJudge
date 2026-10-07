@echo off
setlocal
cd /d "%~dp0"

echo Building portable Wire Judge for Windows...
echo Python 3.11 or newer must be installed on this build computer.

py -3 -m venv .build-venv
if errorlevel 1 goto failed

".build-venv\Scripts\python.exe" -m pip install -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto failed

".build-venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name Wire_Judge ^
  --icon "assets\app_icon.ico" ^
  --add-data "assets:assets" ^
  app.py
if errorlevel 1 goto failed

echo.
echo Done! Share dist\Wire_Judge.exe with your users.
echo They do not need Python or any extra libraries installed.
pause
exit /b 0

:failed
echo.
echo Build failed. Read the error above before closing this window.
pause
exit /b 1
