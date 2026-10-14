# Wire Judge V1.3
by STRAYDOG0626

View and score VTOL VR `.vtr` carrier approaches, replay flights on a 2D map, or play **Airfield Defense** in the Game tab.

## Run

**Windows:** Open `Wire_Judge.exe`. No Python installation needed. Build it yourself with Python 3.11+ and `build_windows.bat`.

**Linux build:** On Ubuntu 24.04+ or a compatible Mint version, install prerequisites, then build from the full project folder:

```sh
sudo apt update
sudo apt install python3 python3-venv python3-tk binutils pulseaudio-utils
bash build_linux.sh
./dist/Wire_Judge
```

The first build needs internet access. Build Linux releases on Linux for the intended CPU architecture; test on the distributions you support. Distribute `dist/Wire_Judge` with `dist/game_stats.json`. If needed, run `chmod +x Wire_Judge` after extracting. Sound uses `paplay` or `aplay`.

**Run from source:** Use Python 3.11+ with Tkinter. Open a terminal in the project folder:

Windows:
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Mac/Linux:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

## Replays

Select a replay, choose its carrier, then select **Case 1** or **Case 3** and an attempt. Set **Wire Caught** or **Bolter** when known. Windows replay files are usually under:

```text
%APPDATA%\Boundless Dynamics, LLC\VTOLVR\SaveData\Replays\
```

| Tab | Use |
| --- | --- |
| Approach Viewer | Inspect graphs, Black Box metrics, wires and approach comparisons. |
| Replay Map | Play flights, inspect aircraft/missiles and follow a selection. |
| Scoreboard | View all/best/latest scores; Export selected attempts to Excel in Downloads. |
| Attempt Editor | Add, delete or trim attempts; Save & Apply to keep edits. |
| Game | Airfield Defense campaign. No replay required. |
| Settings | Graphs, scoring, display, sound, application and carrier options. |

Shift-click attempts to compare up to four. Click graphs with Pan/Zoom off to inspect values. Double-click an attempt or bottom timestamp to open Replay Map. Drag maps to pan; scroll to zoom; Home returns Replay Map to the carrier. Wire selections and saved attempt edits persist.

## Airfield Defense

Build defenses, buy aircraft in Hangar, and destroy enemy airfields while protecting yours. Upgrade the airfield to unlock more units and weapons. 
