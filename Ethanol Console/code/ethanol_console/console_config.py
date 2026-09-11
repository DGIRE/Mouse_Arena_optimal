#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
console_config.py -- constants, palette, and path resolution for the
Mouse Arena **Ethanol Console**.

The Ethanol Console is a trial-by-trial thresholding tool for the head-mounted
ethanol sensor traces in the Mouse Arena aggregate. Its job is to let a human
set an accurate per-trial odor-contact threshold and persist it to a JSON that
downstream analyses can reference.

It reuses the Data Console's conventions:

    Fs        = 500      (head-mounted ethanol sensor sampling rate, Hz)
    arena_px  = [0, 580, 0, 280]   (tracking-pixel bounding box, y downward)
    accessor  = mouse_arena_aggregate_io.Aggregate  (in DATA/code)
    signal    = ethdeconv (default) or raw ethanol

Design decisions (confirmed with David, 2026-08-11):
  * Threshold is applied to the **deconvolved** trace by default (raw selectable),
    after a rolling-percentile **baseline subtraction** (reuses the reactions-v1
    baseline: rolling 10th percentile, ~20 s window).
  * An "odor contact" = a contiguous above-threshold episode whose duration is at
    least ``MIN_DURATION_S`` (min-duration crossings).
  * Thresholds are saved into ONE master JSON keyed by recording (file) name,
    written to ``Ethanol Console/output`` and mirrored to ``DATA``. Every save
    stamps the file (created/updated) and the trial (set time).
  * On landing on a trial the threshold seeds from the saved JSON value if present
    (and same signal), else from an auto-estimate (median + k*MAD on the
    baseline-subtracted trace).

Clock alignment (diverges intentionally from the Data Console): the head clock
and the ethanol clock share a seconds origin but the head track can start several
seconds after t=0. This console aligns on that **shared origin** (it does not
zero-base each stream independently), so a contact's on-trace time maps to the
correct head position for the trajectory map and the distance-to-source metric.
"""
from __future__ import annotations

import os

# ---- calibration ----------------------------------------------------------
FS_DEFAULT = 500.0
ARENA_EXTENT_PX = (0.0, 580.0, 0.0, 280.0)   # (x_min, x_max, y_min, y_max)

# ---- illumination (IR status) selector ----
LIGHTING_ALL = "all"
LIGHTING_ORDER = ("infrared", "deep-red")

# ---- trajectory (head, where the ethanol sensor sits) ----
TRAJ_POINT = "head"                 # "head" | "body"
TRAJ_LINE_COLOR = "#9aa4b0"
TRAJ_LINE_ALPHA = 0.5
TRAJ_LINE_LW = 1.0

# ---- ethanol signal ----
SIGNAL_DECONV = "deconv"            # ethdeconv (kinetics removed) -- default
SIGNAL_RAW = "raw"                 # raw head-sensor trace
DEFAULT_SIGNAL = SIGNAL_DECONV

# ---- baseline subtraction (rolling low-percentile), applied BEFORE thresholding ----
BASELINE_ON_DEFAULT = True
BASELINE_PCT = 10.0                # rolling percentile (10th)
BASELINE_WIN_S = 20.0              # window length in seconds
BASELINE_STEP_S = 0.1             # anchor spacing (interp between anchors)

# ---- contact definition (min-duration above-threshold episodes) ----
MIN_DURATION_S = 0.05             # episodes shorter than this do not count
# auto-threshold seed = median + AUTO_THRESH_K * MAD on the baseline-subtracted trace
AUTO_THRESH_K = 5.0

# ---- drawing ----
CONTACT_COLOR = "#e8000b"          # odor-contact onset marker (red)
CONTACT_SIZE = 26.0
ONSET_TICK_COLOR = "#e8000b"
EPISODE_SHADE = "#ffd23f"          # qualifying-episode shading on the trace
EPISODE_SHADE_ALPHA = 0.35
ON_BAND_COLOR = "#2ca02c"          # binary "odor on" band
TRACE_COLOR = "#1f77b4"
BASELINE_COLOR = "#ff7f0e"
THR_LINE_COLOR = "#e8000b"         # draggable threshold line (red, dashed)

# ---- target odor port (reward endpoint) marker ----
PORT_COLOR = "#e8000b"
PORT_SIZE = 260.0
PORT_LW = 2.2

MAX_TRIALS_IN_COMBO = 100000       # no practical cap; navigation is one-at-a-time

# ---- JSON output ----------------------------------------------------------
JSON_FILENAME = "ethanol_thresholds.json"
JSON_SCHEMA = "mouse_arena/ethanol_thresholds/1.0"

# ---- asset / path resolution ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_CODE_DIR = os.path.dirname(_HERE)                         # .../Ethanol Console/code
_CONSOLE_ROOT = os.path.dirname(_CODE_DIR)                 # .../Ethanol Console
_REPO_ROOT = os.path.abspath(os.path.join(_CODE_DIR, "..", ".."))  # .../Mouse Arena

# Where the aggregate normally lives.
DEFAULT_AGG_PATH = os.path.join(_REPO_ROOT, "DATA", "Mouse Arena Aggregate Data.h5")
# The accessor module ships in DATA/code; add it to sys.path at import time.
AGG_IO_DIR = os.path.join(_REPO_ROOT, "DATA", "code")

# Primary + mirror JSON output directories.
OUTPUT_DIR = os.path.join(_CONSOLE_ROOT, "output")
DATA_MIRROR_DIR = os.path.join(_REPO_ROOT, "DATA")


def output_json_path():
    return os.path.join(OUTPUT_DIR, JSON_FILENAME)


def mirror_json_path():
    return os.path.join(DATA_MIRROR_DIR, JSON_FILENAME)


def resolve_aggregate(explicit=None):
    """Pick the aggregate path: explicit arg > default repo location."""
    if explicit and os.path.isfile(explicit):
        return explicit
    return DEFAULT_AGG_PATH
