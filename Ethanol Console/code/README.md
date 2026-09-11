# Mouse Arena Ethanol Console

A trial-by-trial tool for setting **odor-contact thresholds** on the head-mounted
ethanol sensor traces in the Mouse Arena aggregate, and persisting them to a JSON
that downstream analyses can reference.

It is modeled on the **Mouse Arena Data Console** (same aggregate, same accessor,
same `ma-console` conda-forge environment, same arena frame and file-name
parsing) but is focused on one job: letting a human look at each trial's ethanol
trace, pick an accurate threshold, and see immediately how many odor contacts
that threshold implies and where they fall relative to the odor source.

## What it shows

For the currently selected trial, three linked panels:

- **Trajectory map** (left) — the head track in the arena pixel frame
  (`[0,580] x [0,280]`, y downward), with a **red dot at every odor-contact
  onset** and a **red circle at the target odor port** (the reward `endpoint`).
- **Binary preview** (top right) — a green band showing where odor is **on vs
  off** along time at the current threshold (only qualifying contact episodes).
- **Thresholding trace** (bottom right) — the **baseline-subtracted** ethanol
  signal with the **draggable red threshold line**; qualifying episodes are
  shaded. Box-zoom / pan on this panel (the preview shares its time axis).

The **number of contacts** and their **Euclidean distance from the odor port**
(min / mean / max, px) are shown live in the control bar.

## How a threshold becomes "odor contacts"

1. Pick the signal — **Deconvolved** (`ethdeconv`, default) or **Raw** (`ethanol`).
2. **Baseline-subtract** it (rolling low-percentile; default 10th percentile over
   a 20 s window) — on by default.
3. An **odor contact** = a contiguous above-threshold episode lasting at least
   **Min dur (s)** (default 0.05 s). Briefer spikes are ignored.
4. Each contact's head position is taken at its **onset**, via **shared-origin**
   alignment of the head clock and the ethanol clock (the head track can begin
   several seconds after t=0; the two clocks share a seconds origin). Distance is
   the Euclidean pixel distance from that position to the odor port.

## Controls

| Control | What it does |
|---|---|
| IR status / Date / End loc | Narrow the set of trials you step through. |
| Trial ▾, ◀ Prev, Next ▶, **← / → arrows** | Move through the filtered trials one at a time. |
| Signal: Deconvolved / Raw | Which trace to threshold. |
| Baseline subtract, pct, win(s) | Rolling-percentile baseline before thresholding. |
| Min dur (s) | Minimum above-threshold episode duration to count as a contact. |
| Threshold spin / drag red line / **Auto** | Set the threshold (native, baseline-subtracted units). Auto = median + k·MAD. |
| **Save (Enter)** | Write this trial's threshold + contacts to the master JSON. |
| Nav toolbar | Box-zoom, pan, home/back/forward on the trace + preview. |

On landing on a trial, the threshold **seeds from the saved JSON value** (if the
trial was thresholded before with the same signal), otherwise from the **auto**
estimate. Trials already saved show a `✓` in the trial list.

## Where thresholds are saved

A single master file, **`ethanol_thresholds.json`**, keyed by recording
(file) name, is written to:

- `Ethanol Console/output/ethanol_thresholds.json` (primary), and
- `DATA/ethanol_thresholds.json` (mirror, next to the aggregate).

Every save stamps the file (`created_utc`, `updated_utc`, `generated_local`) and
the trial (`set_utc`, `set_local`). Each trial entry records the signal, baseline
params, threshold, min-duration, contact onsets, per-contact distances, and the
odor-port location — everything a downstream program needs to reproduce the
odor-on mask. See the user guide for the full schema.

## Running it

Uses the **same** dedicated conda-forge environment as the Data Console
(`pyside6 + matplotlib + numpy + h5py` — no SciPy needed; the baseline is pure
NumPy). Create it once if you have not already:

```
conda create -n ma-console -c conda-forge python=3.12 pyside6 matplotlib numpy h5py
```

Then launch:

```
run_ethanol_console.bat  ["path\to\Mouse Arena Aggregate Data.h5"]
```

or directly:

```
python run_ethanol_console.py  ["path\to\...h5"]
```

With no path it uses `../../DATA/Mouse Arena Aggregate Data.h5`.

## Layout

```
Ethanol Console/
  code/
    ethanol_console/
      __init__.py        Qt DLL isolation (no-op under conda), version
      console_config.py  constants, palette, path + JSON-output resolution
      data.py            accessor wrapper, baseline, contact detection (pure NumPy)
      thresholds.py      master-JSON store (+ DATA mirror, timestamps)
      view.py            render() + Qt canvas (draggable line + box-zoom toolbar)
      main_window.py     the window (navigation, threshold, save)
      app.py, __main__.py
    run_ethanol_console.py / .bat
    README.md
  guides/                user guide (docx)
  output/                ethanol_thresholds.json is written here
  commands/  figures/
```

`data.py`'s functions (`rolling_percentile_baseline`, `detect_contacts`,
`auto_threshold`) are plain NumPy and can be imported directly by analyses.
