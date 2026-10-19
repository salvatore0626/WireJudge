#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
trap 'printf "Build failed. Read the error above.\n" >&2' ERR

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Run this script on Linux to build a Linux executable.\n' >&2
    exit 1
fi

python_command="${PYTHON:-python3}"
if ! command -v "$python_command" >/dev/null 2>&1; then
    printf 'Python 3.11 or newer is required. Install it, then retry.\n' >&2
    exit 1
fi
"$python_command" -c 'import sys; sys.exit("Python 3.11 or newer is required.") if sys.version_info < (3, 11) else None'
if ! "$python_command" -c 'import tkinter' >/dev/null 2>&1; then
    printf 'Tkinter is missing. On Ubuntu/Mint: sudo apt install python3-tk\n' >&2
    exit 1
fi
for required in app.py config/requirements.txt game/game_stats.json game/assets assets; do
    if [[ ! -e "$required" ]]; then
        printf 'Missing %s. Keep this script in the full Wire Judge project folder.\n' "$required" >&2
        exit 1
    fi
done

printf 'Building Wire Judge for Linux...\n'
"$python_command" -m venv .build-venv-linux
build_python='.build-venv-linux/bin/python'
"$build_python" -m pip install -r config/requirements.txt 'pyinstaller>=6,<7'
"$build_python" -m PyInstaller \
    --noconfirm --clean --onefile --name Wire_Judge \
    --workpath build/linux --specpath build/linux \
    --add-data "$PWD/assets:assets" \
    --add-data "$PWD/game/game_stats.json:game" \
    --add-data "$PWD/game/assets:game/assets" \
    "$PWD/app.py"

chmod +x dist/Wire_Judge
printf '\nDone! Run: ./dist/Wire_Judge\n'
