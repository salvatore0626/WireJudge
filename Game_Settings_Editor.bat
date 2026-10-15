@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python game_config_editor.py
) else (
    py -3 game_config_editor.py
)
if errorlevel 1 pause
