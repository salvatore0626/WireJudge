# Wire Judge V1.2
by STRAYDOG0626

Open a VTOL VR `.vtr` replay to view carrier approaches, score landings, and watch the replay on a 2D map.

## Start the app

**Windows EXE:** Open `Wire_Judge.exe`. No Python or library installation is needed.

To build the EXE yourself, install Python 3.11 or newer on Windows and run `build_windows.bat`. The first build needs internet access. The finished app is `dist/Wire_Judge.exe`.

**Run from source:** Install Python 3.11 or newer, then open PowerShell or Terminal in the project folder.

Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Mac:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

## First use

1. Click **Select Replay** and open a `.vtr` file.
2. Click **Select Carrier** and choose the carrier.
3. Select **Case 1** or **Case 3**.
4. Choose a player's attempt to view it. Set **Wire Caught** or **Bolter** when known.

Windows replays are usually in:

```text
%APPDATA%\Boundless Dynamics, LLC\VTOLVR\SaveData\Replays\
```

Wire choices save automatically. Attempt edits save with **Save & Apply** and return when you reopen the same replay and carrier.

## Tabs

| Tab | Use |
| --- | --- |
| Approach Viewer | View attempts, compare approaches, inspect graphs, and set wires. |
| Replay Map | Play the replay, inspect aircraft or missiles, and follow a selected aircraft. |
| Scoreboard | View all, best, or latest scores. Export selected attempts to an Excel file in Downloads. |
| Attempt Editor | Add, delete, or trim attempts using the map and timeline. |
| Settings | Adjust graphs, replay display, point values, application options, and carrier configuration. |

## Main controls

- **Shift-click attempts** to compare up to four. Click without Shift to return to a single attempt.
- **Graph buttons** show or hide graphs. Enable **Black Box** and use its dropdown to select metrics.
- **Click a graph** with Pan and Zoom off to show the red cursor and values. Double-click a bottom timestamp or an attempt to open it in Replay Map.
- **Maps:** drag to pan, scroll to zoom, and use **Home** to return to the carrier. **Follow** tracks your selection in Replay Map.
- **Attempt Editor:** drag the Start/Stop handles to trim an attempt, then click **Save & Apply**. **Reset Changes** discards unsaved edits.
