@echo off
cd /d "%~dp0.."
where py >nul 2>nul
if errorlevel 1 (
    python -m game.game_config_editor
) else (
    py -3 -m game.game_config_editor
)
if errorlevel 1 pause
