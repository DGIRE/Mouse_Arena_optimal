#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arena_config.py -- constants, palette, and asset/path resolution for the
Mouse Arena Data Console.

Calibration constants mirror ``mouse_arena/config.py`` (``Params``) and the
Mouse Arena aggregate root attributes:

    Fs        = 500      (head-mounted ethanol sensor sampling rate, Hz)
    arena_px  = [0, 580, 0, 280]   (tracking-pixel bounding box)

Coordinate frame
----------------
Behavior body/head positions are stored in the arena tracking-pixel frame
(image convention: x rightward, y downward). There is no arena photo in the
repo or the aggregate yet, so the console draws on a neutral panel spanning
``ARENA_EXTENT_PX``; drop an image at ``assets/arena_background.(png|tiff)`` and
it is picked up automatically as the backdrop, stretched onto that same extent.

Selection model (vs the Rat Arena console)
-------------------------------------------
The Mouse Arena behavior data is a flat set of navigation trials, each tagged
with an illumination condition (infrared / deep-red) and a recording date parsed
from its file name -- there is no animal/predictability grouping, no DLC, and no
pellets. So the two primary selectors are **IR status** and **Date**, with a
per-trial checkbox strip. Each trial carries a head + body track, a head-mounted
ethanol trace (raw and deconvolved), and a single target odor-port location
(the reward ``endpoint``), which is drawn as a red circle.
"""
from __future__ import annotations

import os

# ---- calibration (from mouse_arena/config.py + aggregate root attrs) ----
FS_DEFAULT = 500.0

# Tracking-pixel extent the data lives in: (x_min, x_max, y_min, y_max).
# From mouse_arena/config.py Params.arena_px = [0, 580, 0, 280].
ARENA_EXTENT_PX = (0.0, 580.0, 0.0, 280.0)

# ---- illumination (IR status) selector ----
LIGHTING_ALL = "all"
LIGHTING_ORDER = ("infrared", "deep-red")     # preferred display order; others appended

# ---- trajectory (fixed: head, where the ethanol sensor sits) ----
TRAJ_POINT = "head"                # "head" | "body"
TRAJ_LINE_COLOR = "#9aa4b0"
TRAJ_LINE_ALPHA = 0.45
TRAJ_LINE_LW = 1.0

# ---- ethanol plume signal (selectable at runtime) ----
SIGNAL_DECONV = "deconv"           # ethdeconv (sensor kinetics removed) -- default
SIGNAL_RAW = "raw"                 # raw head-sensor trace
DEFAULT_SIGNAL = SIGNAL_DECONV

# ---- ethanol "contact" dots (color by normalised plume concentration) ----
CONTACT_CMAP = "jet"
DEFAULT_ALPHA = 0.8
DEFAULT_VMIN = 0.0
DEFAULT_VMAX = 1.0
DEFAULT_DOT_SIZE = 14.0
DEFAULT_CONTACTS_ON = True
# Alpha threshold: normalised concentration below this is drawn fully transparent
# (the analogue of the Rat Arena density alpha-threshold), and the value is shown
# on the ethanol time series as a dashed red line.
DEFAULT_ALPHA_THRESH_ON = True
DEFAULT_ALPHA_THRESH = 0.15

# ---- target odor port (reward endpoint) marker ----
PORT_COLOR = "#e8000b"             # red
PORT_SIZE = 260.0
PORT_LW = 2.2

# Concentration is normalised to [0, 1] across the current selection (like the
# Rat Arena normalised density), so alpha / threshold / vmin / vmax all live in
# [0, 1] and the time-series dashed line is in the same units.
NORM_EPS = 1e-12

# Colours for overlaying multiple trials' ethanol time series.
TRIAL_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf",
                "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

# Cap the per-trial checkbox strip; above this only an "All" checkbox is shown.
MAX_TRIAL_CHECKBOXES = 24

# ---- asset / path resolution ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_CODE_DIR = os.path.dirname(_HERE)                    # .../Data Console/code
_ASSETS_DIR = os.path.join(_CODE_DIR, "assets")

# Where the aggregate normally lives, relative to this repo checkout.
_REPO_ROOT = os.path.abspath(os.path.join(_CODE_DIR, "..", ".."))  # .../Mouse Arena
DEFAULT_AGG_PATH = os.path.join(
    _REPO_ROOT, "DATA", "Mouse Arena Aggregate Data.h5")

# The accessor module ships in DATA/code; add it to sys.path at import time.
AGG_IO_DIR = os.path.join(_REPO_ROOT, "DATA", "code")


def background_candidates():
    """Ordered list of places an (optional) arena background image may live."""
    return [
        os.path.join(_ASSETS_DIR, "arena_background.png"),
        os.path.join(_ASSETS_DIR, "arena_background.tiff"),
        os.path.join(_ASSETS_DIR, "arena_background.tif"),
        os.path.join(_REPO_ROOT, "DATA", "arena_background.png"),
    ]


def resolve_background():
    """Return the first existing background-image path, or None (neutral panel)."""
    for p in background_candidates():
        if os.path.isfile(p):
            return p
    return None


def resolve_aggregate(explicit=None):
    """Pick the aggregate path: explicit arg > default repo location."""
    if explicit and os.path.isfile(explicit):
        return explicit
    return DEFAULT_AGG_PATH
