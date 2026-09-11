# Mouse Arena Data Console

An interactive viewer for the **Mouse Arena aggregate**
(`..\..\DATA\Mouse Arena Aggregate Data.h5`), modeled on the Rat Arena Data
Console. It shows freely-behaving navigation trials (Tariq et al., eNeuro
8(1) ENEURO.0285-20.2020, Figs 7–8): the mouse's head trajectory over the arena,
overlaid with **ethanol-contact dots coloured by plume concentration** (jet), the
**target odor port** as a red circle, and the **ethanol sensor time series** below.

It reads the aggregate through the read-only accessor
`..\..\DATA\code\mouse_arena_aggregate_io.py` — it never parses the HDF5 by hand.

## Environment

The GUI runs from a dedicated **conda-forge** environment, `ma-console`, which
has a self-consistent Qt6 / ICU / runtime stack. (The pip `PySide6` in the
`vras` venv could not load here: `vras` sits on top of Anaconda's Python, and
Anaconda injects its own Qt6/ICU into the process, which collides with pip's
PySide6 — producing `ImportError: DLL load failed while importing QtWidgets`.)
Create the env once:

```bat
conda create -n ma-console -c conda-forge python=3.12 pyside6 matplotlib numpy h5py -y
```

`vras` is untouched and still used for the analysis pipeline; only the console
uses `ma-console`.

## Run it

```bat
:: from Data Console\code
run_mouse_arena_console.bat
```

The `.bat` runs the `ma-console` env's Python directly
(`%USERPROFILE%\anaconda3\envs\ma-console\python.exe`), falling back to
`conda run -n ma-console`. To run by hand:

```bat
conda activate ma-console
python run_mouse_arena_console.py ["path\to\Mouse Arena Aggregate Data.h5"]
```

If no path is given the default repo location is used. (`diag_qt.py` in this
folder is a small Qt-DLL diagnostic kept for troubleshooting.)

## What it shows

The Mouse Arena behavior data is a flat set of navigation trials, each tagged
with an **IR status** (infrared / deep-red) and a **recording date** (parsed from
the trial's file name). There is no animal/predictability grouping, no DLC, and
no pellets — so the two primary selectors are **IR status** and **Date**, with a
per-trial checkbox strip.

```
row 1 : [IR status v] [Date v] [End loc v] | Trials: (All)(#0 a.. T.. L..)(...)
row 2 : Signal: (o) Deconvolved (o) Raw   |  Seconds: [start]-[end]
row 3 : Contacts [x]  Alpha[ ] Min[ ] Max[ ] | α<thr→0 [x] [thr]
        [Refresh] [Save image…]                 Trial length: <indicator>
```

- **IR status / Date** — pick the illumination condition and recording day; "All"
  overlays across dates (or statuses).
- **End loc** — the target odor-port (end) location (`Loc N`; there were several,
  one per trial). Pick one and **only the trials/animals that ran to that
  location become selectable**; "All locations" keeps them all.
- **Trials** — `All`, or individual trials for the current status + date + end
  location (labelled `#<index> a<animal> T<trial> L<loc>`). Selecting several
  overlays them.
- **Signal** — colour and time series driven by the **deconvolved** ethanol
  (sensor kinetics removed) or the **raw** head-sensor trace.
- **Seconds** — restrict to a `[start, end]` window of the trial (0 = to the end).
- **Contacts / Alpha / Min / Max** — toggle the ethanol-contact dots and set their
  opacity and the jet colour range.
- **α<thr→0** — concentration below the threshold is drawn fully transparent (the
  analogue of the Rat Arena density alpha-threshold).
- **Trial length** — duration of the selected trial, or min/mean/max across
  several.

The ethanol time series carries three dashed reference lines in the same
normalised units: **red = the alpha threshold**, **green = the colormap max
(`Max`)**, and **cyan = the colormap min (`Min`)**. **Click and drag any of these
lines up or down** to set that value directly — the cursor turns into a
vertical-resize arrow when you're over a line, and on release the dots, colorbar,
and the `Min` / `Max` / threshold boxes all update to match (dragging the red
line also switches on `α<thr→0`).

The arena **caption** names exactly what's shown: the trial's recording name
(when a single trial is selected), the IR status, the end (odor-port) location,
and the date. **Save image…** likewise names the file after the data on screen —
the trial's own recording name for a single trial (e.g.
`mouse_arena_infrared_allDates_Loc1_11-20-2019-...-Trial0_Loc1_deconv.png`), or
an `N-trials` summary otherwise.

### Concentration normalisation

Plume concentration is normalised to **[0, 1] across the current selection**
(divided by the selection's peak). So the dot colours, the alpha threshold, the
`Min`/`Max` colour range, and the time-series threshold line all live in the same
`[0, 1]` units — the same convention the Rat Arena console uses for its
normalised pellet/trajectory density.

### Background image

There is no Mouse Arena arena photo in the repo or aggregate yet, so the console
draws on a neutral panel spanning the tracking-pixel extent
(`arena_config.ARENA_EXTENT_PX`, from `mouse_arena/config.py` `arena_px =
[0,580,0,280]`). Drop an arena image at `assets\arena_background.png` (or
`.tiff`) and it is picked up automatically as the backdrop, stretched onto that
extent. If your data doesn't fill the panel, tune `ARENA_EXTENT_PX`.

## Layout

```
Data Console/
  code/
    assets/                        (optional arena_background.png / .tiff)
    mouse_arena_console/
      __init__.py  __main__.py  app.py
      arena_config.py             constants, palette, path/asset resolution
      data.py                     DataStore over the aggregate accessor (no Qt)
      arena_view.py               arena + ethanol-time-series rendering
      main_window.py              the control bar + wiring
    run_mouse_arena_console.py    launcher
    run_mouse_arena_console.bat   launcher (Windows)
    README.md                     this file
  commands/                       command log (creation + updates) + figures
  figures/                        saved views (empty until you save some)
  Guides/                         user guides (empty for now)
```

## Notes / not yet implemented

- The aggregate must exist first — build it with
  `..\..\DATA\code\build_mouse_arena_aggregate.py` (calcium omitted; all behavior
  trials tagged by lighting).
- The console plots the **head** track (where the ethanol sensor sits) and colours
  it by concentration; `arena_config.TRAJ_POINT` can be switched to `"body"`.
- No cleaning/alignment write-back exists yet (the Mouse Arena behavior tracks are
  already the paper's processed positions); the empty `Guides/` and `figures/`
  folders mirror the Rat Arena layout for when those are added.
