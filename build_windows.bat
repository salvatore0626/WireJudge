@echo off
setlocal
cd /d "%~dp0"

echo Building portable Wire Judge for Windows...

if not exist "game_stats.json" (
  echo Missing game_stats.json. Put it beside this build script before building.
  goto failed
)

py -3 -m venv .build-venv
if errorlevel 1 goto failed

".build-venv\Scripts\python.exe" -m pip install -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto failed

".build-venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name Wire_Judge ^
  --icon "assets\app_icon.ico" ^
  --add-data "assets:assets" ^
  --add-data "game_stats.json:." ^
  app.py
if errorlevel 1 goto failed

echo.
if not exist "dist\game_stats.json" (
  copy /Y "game_stats.json" "dist\game_stats.json" >nul
  if errorlevel 1 goto failed
) else (
  echo Keeping your existing dist\game_stats.json settings.
)

echo Done! Your exe is in dist\Wire_Judge.exe
echo Editable game settings are in dist\game_stats.json
pause
exit /b 0

:failed
echo.
echo Build failed. Read the error above before closing this window.
pause
exit /b 1
