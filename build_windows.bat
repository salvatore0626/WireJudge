@echo off
setlocal
cd /d "%~dp0"

echo Building portable Wire Judge for Windows...

if not exist "game\game_stats.json" (
  echo Missing game\game_stats.json. Keep the game folder beside this build script.
  goto failed
)

if not exist "config\requirements.txt" (
  echo Missing config\requirements.txt.
  goto failed
)

if not exist "app.py" (
  echo Missing app.py.
  goto failed
)

call :find_python
if defined PYTHON_CMD goto build

echo.
echo Python 3 could not be found.
choice /C YN /N /M "Install Python 3.12 now? [Y/N]: "
if errorlevel 2 goto failed
if errorlevel 1 goto install_python
goto failed

:install_python
where winget >nul 2>&1
if errorlevel 1 (
  echo Windows Package Manager is not available.
  goto manual_install
)

winget install --exact --id Python.Python.3.12 ^
  --source winget --scope user --interactive
if errorlevel 1 goto manual_install

rem Check again, including the default installation path.
rem This avoids relying on PATH refreshing in this window.
call :find_python
if defined PYTHON_CMD goto build

echo Python was installed but could not be located in this window.
echo Close this window and run this build script again.
goto failed

:manual_install
echo.
echo Please install Python from:
echo https://www.python.org/downloads/windows/
echo Enable "Add python.exe to PATH" during installation.
echo Then close this window and run this build script again.
goto failed

:build
echo.
echo Using %PYTHON_CMD%

%PYTHON_CMD% -m venv .build-venv
if errorlevel 1 goto failed

".build-venv\Scripts\python.exe" -m pip install ^
  -r config\requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto failed

".build-venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name Wire_Judge ^
  --icon "assets\app_icon.ico" ^
  --add-data "assets:assets" ^
  --add-data "game\game_stats.json:game" ^
  --add-data "game\assets:game/assets" ^
  app.py
if errorlevel 1 goto failed

echo.

echo Done! Your exe is in dist\Wire_Judge.exe
pause
exit /b 0

:find_python
set "PYTHON_CMD="

py -3 -c "import sys, venv; assert sys.version_info.major == 3" >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
  exit /b 0
)

python -c "import sys, venv; assert sys.version_info.major == 3" >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  "%LocalAppData%\Programs\Python\Python312\python.exe" -c "import sys, venv; assert sys.version_info.major == 3" >nul 2>&1
  if not errorlevel 1 (
    set PYTHON_CMD="%LocalAppData%\Programs\Python\Python312\python.exe"
    exit /b 0
  )
)

exit /b 1

:failed
echo.
echo Build failed. Read the error above before closing this window.
pause
exit /b 1
