"""s1a_import_pulses — port of Stage1_Import/s1a_import_pulses.m.

STAGE 1a -- Data behind Figures 1-2: paired PID + ethanol sensor to brief
ethanol PULSES.

Strategy (closest-to-paper first):
  1. Load the paper's processed file (Fig1/data.mat) -> ETH_all_sorted,
     PID_all_sorted, durations_sorted. This IS the publication data.
  2. If absent, auto-discover raw *.dat in P.raw.pulses, read PID/ETH/valve,
     derive the pulse duration from the VALVE channel (extract_pulse_metrics)
     and/or the filename (_Pulse_Ns), window each pulse, and sort by duration.

OUTPUT (dict): ETH_all_sorted, PID_all_sorted, durations_sorted, t, Fs.
Reference: Tariq et al. (2020), Figs. 1-2. Source: Figure1.m.
"""
from __future__ import annotations

import glob
import os

import numpy as np

from mouse_arena import config, dataio, metadata
from mouse_arena.io_labview import read_labview_dat

# ---- default (unresolved-on-this-machine) path roots, overridable via `paths` ----
_DEFAULT_ARENA_ROOT = os.environ.get(
    "MA_ARENA_ROOT", os.path.join(os.sep, "GireLab_Data", "Mouse_Arena")
)


def _paper_root(paths):
    """Resolve the paper backup root directory (s1a configuration)."""
    paths = paths or {}
    return paths.get(
        "paper_root",
        os.path.join(paths.get("arena_root", _DEFAULT_ARENA_ROOT),
                     "Ethanol Sensor Data", "Paper_BackUp", "Paper"),
    )


def _default_files_pulses(paths):
    """Return candidate paths to the paper's Fig1/data.mat (s1a processed file)."""
    return [os.path.join(_paper_root(paths), "Fig1", "data.mat")]


def _default_raw_pulses(paths):
    """Return candidate paths to the paper's raw Fig1 pulse data."""
    return [os.path.join(_paper_root(paths), "Fig1", "Figure1", "Data")]


def import_from(path, params=None):
    """Pure transform: load the paper's Fig1 data.mat and compute t/Fs.

    MATLAB:
        S = load(src);
        ETH_all_sorted = S.ETH_all_sorted;
        PID_all_sorted = S.PID_all_sorted;
        durations_sorted = S.durations_sorted(:)';
        t = (0:size(ETH_all_sorted,2)-1)/Fs;
    """
    if params is None:
        params = config.get_params()
    Fs = params.Fs

    S = dataio.load_mat(path)
    ETH_all_sorted = np.asarray(S["ETH_all_sorted"], dtype=np.float64)
    PID_all_sorted = np.asarray(S["PID_all_sorted"], dtype=np.float64)
    durations_sorted = np.asarray(S["durations_sorted"], dtype=np.float64).reshape(-1)

    ncols = ETH_all_sorted.shape[1]
    t = np.arange(ncols, dtype=np.float64) / Fs

    return {
        "ETH_all_sorted": ETH_all_sorted,
        "PID_all_sorted": PID_all_sorted,
        "durations_sorted": durations_sorted,
        "t": t,
        "Fs": Fs,
    }


def _from_raw(rawdir, params):
    """Fallback: derive pulses.mat fields from raw LabView .dat files.

    MATLAB:
        files = dir(fullfile(rawdir,'*.dat'));
        files = files(~contains({files.name},'Baseline','IgnoreCase',true));
        tPre=60; tPost=240; nPre=round(Fs*tPre); nPost=round(Fs*tPost);
        for each file: D = read_labview_dat(...); [onsets,dur_s] = extract_pulse_metrics(D.val,Fs);
            meta = parse_trial_meta(name);
            for each onset: window [onset-nPre, onset+nPost], clip to [1,N];
                duration = meta.duration if present else dur_s(i)
        sort rows by duration ascending.
    """
    Fs = params.Fs
    all_paths = sorted(glob.glob(os.path.join(rawdir, "*.dat")))
    files = [p for p in all_paths if "baseline" not in os.path.basename(p).lower()]

    tPre, tPost = 60.0, 240.0
    nPre = int(round(Fs * tPre))
    nPost = int(round(Fs * tPost))

    ETH_all, PID_all, durations = [], [], []
    for fpath in files:
        D = read_labview_dat(fpath, params.chan_pid, params)
        onsets, dur_s, _freq_hz = metadata.extract_pulse_metrics(D["val"], Fs)
        meta = metadata.parse_trial_meta(os.path.basename(fpath))
        ETH = np.asarray(D["ETH"]).reshape(-1)
        PID = np.asarray(D["PID"]).reshape(-1)
        N = ETH.size
        for i, onset in enumerate(onsets):
            idx = np.arange(onset - nPre, onset + nPost + 1)   # 1-based, inclusive
            idx = np.clip(idx, 1, N)
            ETH_all.append(ETH[idx - 1])
            PID_all.append(PID[idx - 1])
            if not np.isnan(meta["duration"]):
                durations.append(meta["duration"])
            else:
                durations.append(dur_s[min(i, dur_s.size - 1)] if dur_s.size else np.nan)

    ETH_all = np.asarray(ETH_all, dtype=np.float64)
    PID_all = np.asarray(PID_all, dtype=np.float64)
    durations = np.asarray(durations, dtype=np.float64)

    order = np.argsort(durations, kind="stable")
    durations_sorted = durations[order]
    ETH_all_sorted = ETH_all[order, :] if ETH_all.size else ETH_all
    PID_all_sorted = PID_all[order, :] if PID_all.size else PID_all

    ncols = ETH_all_sorted.shape[1] if ETH_all_sorted.ndim == 2 else 0
    t = np.arange(ncols, dtype=np.float64) / Fs

    return {
        "ETH_all_sorted": ETH_all_sorted,
        "PID_all_sorted": PID_all_sorted,
        "durations_sorted": durations_sorted,
        "t": t,
        "Fs": Fs,
    }


def run(params=None, paths=None):
    """Higher-level entry: resolve the paper file (or raw fallback) and import it."""
    if params is None:
        params = config.get_params()
    paths = paths or {}

    candidates = paths.get("files_pulses") or _default_files_pulses(paths)
    src = metadata.ma_first(candidates)
    if src:
        return import_from(src, params)

    raw_candidates = paths.get("raw_pulses") or _default_raw_pulses(paths)
    rawdir = metadata.ma_first(raw_candidates, must_exist=True)
    return _from_raw(rawdir, params)
