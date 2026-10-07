# Wire Judge — version 0.12.27

The replay files are located in `%APPDATA%\Boundless Dynamics, LLC\VTOLVR\SaveData\Replays` on Windows.

Wire Judge opens a VTOL VR `.vtr` replay and displays each player's approach to the carrier.

## Start on macOS or Windows

Python 3.11 or newer. Open a terminal in the project folder.

Mac terminal:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

## Build a portable Windows EXE

On a Windows computer with Python 3.11 or newer installed, double-click **build_windows.bat**. The first build needs internet access to download dependencies.

The finished app is **dist/Wire_Judge.exe**. Share that file; users can double-click it without installing Python or libraries. Icons and carrier assets are bundled inside it. Build Windows executables on Windows; macOS needs a separate build.

Before sharing, open a replay and check the carrier map, graphs, and saved wire choices in the built EXE.

## First use

1. Click **Select Replay** and select a `.vtr` file.
2. Click **Select Carrier**, search for the carrier unit, and confirm your selection.
3. Choose **Case 1** or **Case 3** from the recovery dropdown.
4. Select a player's attempt to view its graphs, then set the wire caught or **Bolter**.

Wire choices save automatically. Attempt edits save with **Save & apply** and return when you reopen the same replay and select the same carrier.

## Tabs

| Tab | Contents |
| --- | --- |
| Approach Viewer | Player attempts, wire choices, total scores, and glide, localizer, groundspeed/AoA graphs. |
| Scores | Players ranked by their best scored attempt, with category scores and totals. Column winners are green and starred. |
| Attempt Editor | A player's flight timeline and carrier-relative map; add, delete, or trim attempts. Double-click a player in Approach Viewer to open their log. |
| Settings | Approach & graphs, Point Values, and Carrier Config. |

## Quick controls

| Control | Action |
| --- | --- |
| All / Last / Best attempt | Filter the Approach Viewer list. |
| Data points | Show recorded samples on the approach graphs. |
| Graph reset / zoom / pan | Restore the view, select a zoom area, or move around a graph. |
| Score column headings / best-only toggle | Change sorting or show each player's best attempt. |
| Flights dropdown | Show or hide flights on the editor map and timeline. |
| Map Home / − / + | Return to the carrier at 2 NM zoom, zoom out, or zoom in. Mouse wheel zooms; dragging pans. |
| Timeline − / + | Zoom out or in. Drag to pan; click to move the red cursor. Clicking a map trail also moves the cursor. |
| Center on cursor / Focus attempt / Full timeline | Center the timeline, frame the selected attempt, or show the full log. |
| Start / Stop handles | Drag to change the selected attempt's boundaries. |
| Add Attempt / Delete Attempt | Create an attempt at the cursor or remove the selected attempt. |
| Save & apply / Reset changes | Save pending edits or discard them. The editor save button turns green when edits are pending. |
| Restore defaults | Fill settings with the defaults below; click Save & apply to save them. |
| Case 1 Glide Start reset arrow | Set Glide Start to the configured glide slope's 600 ft MSL intercept. |

## Settings

### Approach & graphs

| Setting | Default | Purpose |
| --- | --- | --- |
| Case 1 / Case 3 Render Distance | 2 / 11 NM | Distance shown on approach graphs and the editor localizer. |
| Glide slope ± | 0.7° | Glide envelope and scoring tolerance. |
| Localizer ± | 2.5° | Localizer envelope and scoring tolerance, including the Case 3 platform. |
| AoA ± | 4° | Graph range around the 8° target: 4–12°. AoA scoring uses a fixed ±5° tolerance. |
| Case 1 / Case 3 Glide Start | 0.75 / 2.25 NM | Begin glide, localizer, and AoA grading. |
| Glide End | 0.08 NM | End approach grading; landing points come from the selected wire. |
| Platform Alt ± | 300 ft | Altitude tolerance around 1,200 ft MSL. |
| Platform Spd ± | 50 knots | Groundspeed tolerance around the leg's target speed. |
| Leg 1 Speed | 250 knots | Target groundspeed from 10 to 6 DME. |
| Speed Change Deadzone | 1 NM | Speed grading is excluded for this total width centered on 6 DME: 6.5–5.5 DME. |
| Leg 2 Speed | 200 knots | Target groundspeed from 6 to 3 DME. |
| Platform Start / End | 8 / 3 NM | Bounds for Case 3 platform grading; these do not move the physical legs. |

### Point Values

Category values are maximum available points. Case 3 platform position combines lateral and altitude accuracy equally.

| Category | Case 1 | Case 3 |
| --- | --- | --- |
| Platform Position Accuracy | — | 750 |
| Platform Speed Accuracy | — | 750 |
| Localizer | 1,000 | 1,000 |
| Glide | 1,000 | 1,000 |
| AoA | 1,000 | 500 |
| Approach total | 3,000 | 4,000 |

| Landing | Default points |
| --- | --- |
| Bolter | 0 |
| 1 Wire | 250 |
| 2 Wire | 750 |
| 3 Wire | 1,000 |
| 4 Wire | 500 |

### Carrier Config

Offsets locate the glide origin relative to the carrier unit. Distances are metres; angles are degrees.

| Setting | Default | Purpose |
| --- | --- | --- |
| X Offset | 7 m | Right (+) / left (−). |
| Y Offset | 6 m | Up (+) / down (−). |
| Z Offset | −82 m | Forward (+) / aft (−). |
| Runway Offset | −10° | Runway rotation relative to the carrier; negative is counterclockwise. |
| Glide Slope Angle | 3.5° | Target glide slope angle. |
