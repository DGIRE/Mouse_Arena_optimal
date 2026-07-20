"""s1c_import_spatial — port of Stage1_Import/s1c_import_spatial.m.

STAGE 1c -- Data behind Figure 5: paired PID + sensor at three arena
locations (near source / middle / downwind).

Strategy: load paper file (Fig5/Data/data2_updated.mat) giving
ETH_all_sorted, PID_all_sorted, locations_sorted. Also loads the paper's
precomputed within-trial correlations (corrs_updated.mat) when present.
Fallback: auto-discover raw *.dat and read location from the filename
(_Loc_N) -- location is not recoverable from signal alone.

OUTPUT (dict): ETH_all_sorted, PID_all_sorted, locations_sorted, t, Fs
               [, corrs, corr_locs]
Reference: Tariq et al. (2020), Fig. 5. Source: Fig5.m.
"""
from __future__ import annotations

import glob
import os

import numpy as np

from mouse_arena import config, dataio, metadata
from mouse_arena.io_labview import read_labview_dat

_DEFAULT_ARENA_ROOT = os.environ.get(
    "MA_ARENA_ROOT", os.path.join(os.sep, "GireLab_Data", "Mouse_Arena")
)


def _paper_root(paths):
    """Resolve the paper backup root directory (s1c configuration)."""
    paths = paths or {}
    return paths.get(
        "paper_root",
        os.path.join(paths.get("arena_root", _DEFAULT_ARENA_ROOT),
                     "Ethanol Sensor Data", "Paper_BackUp", "Paper"),
    )


def _default_files_spatial(paths):
    """Return candidate paths to the paper's Fig5 spatial data."""
    paper = _paper_root(paths)
    return [
        os.path.join(paper, "Fig5", "Data", "data2_updated.mat"),
        os.path.join(paper, "Fig5", "Data", "data.mat"),
    ]


def _default_files_spatial_corr(paths):
    """Return candidate paths to the paper's Fig5 spatial correlation precompute."""
    paper = _paper_root(paths)
    return [
        os.path.join(paper, "Fig5", "Data", "corrs_updated.mat"),
        os.path.join(paper, "Fig5", "Data", "corrs.mat"),
    ]


def _default_raw_spatial(paths):
    """Return candidate paths to the paper's raw Fig5 spatial data."""
    return [os.path.join(_paper_root(paths), "Fig5", "Data")]


def import_from(path, params=None):
    """Pure transform: load the paper's Fig5 data(2_updated).mat and compute t/Fs.

    MATLAB:
        S = load(src);
        ETH_all_sorted = S.ETH_all_sorted;
        PID_all_sorted = S.PID_all_sorted;
        locations_sorted = S.locations_sorted(:)';
        t = (0:size(ETH_all_sorted,2)-1)/Fs;
    """
    if params is None:
        params = config.get_params()
    Fs = params.Fs

    S = dataio.load_mat(path)
    ETH_all_sorted = np.asarray(S["ETH_all_sorted"], dtype=np.float64)
    PID_all_sorted = np.asarray(S["PID_all_sorted"], dtype=np.float64)
    locations_sorted = np.asarray(S["locations_sorted"], dtype=np.float64).reshape(-1)

    ncols = ETH_all_sorted.shape[1]
    t = np.arange(ncols, dtype=np.float64) / Fs

    return {
        "ETH_all_sorted": ETH_all_sorted,
        "PID_all_sorted": PID_all_sorted,
        "locations_sorted": locations_sorted,
        "t": t,
        "Fs": Fs,
    }


def _from_raw(rawdir, params):
    """Fallback: derive spatial.mat fields from raw LabView .dat files.

    MATLAB:
        files = dir(fullfile(rawdir,'*.dat'));
        for each file: meta = parse_trial_meta(name); skip if meta.loc is NaN;
            D = read_labview_dat(...);
            ETH_all(end+1,:) = D.ETH(:)'; PID_all(end+1,:) = D.PID(:)'; locations(end+1)=meta.loc;
        [locations_sorted,o]=sort(locations);
        ETH_all_sorted=ETH_all(o,:); PID_all_sorted=PID_all(o,:);
    """
    Fs = params.Fs
    files = sorted(glob.glob(os.path.join(rawdir, "*.dat")))

    ETH_all, PID_all, locations = [], [], []
    for fpath in files:
        meta = metadata.parse_trial_meta(os.path.basename(fpath))
        if np.isnan(meta["loc"]):
            continue
        D = read_labview_dat(fpath, params.chan_pid, params)
        ETH_all.append(np.asarray(D["ETH"]).reshape(-1))
        PID_all.append(np.asarray(D["PID"]).reshape(-1))
        locations.append(meta["loc"])

    ETH_all = np.asarray(ETH_all, dtype=np.float64)
    PID_all = np.asarray(PID_all, dtype=np.float64)
    locations = np.asarray(locations, dtype=np.float64)

    order = np.argsort(locations, kind="stable")
    locations_sorted = locations[order]
    ETH_all_sorted = ETH_all[order, :] if ETH_all.size else ETH_all
    PID_all_sorted = PID_all[order, :] if PID_all.size else PID_all

    ncols = ETH_all_sorted.shape[1] if ETH_all_sorted.ndim == 2 else 0
    t = np.arange(ncols, dtype=np.float64) / Fs

    return {
        "ETH_all_sorted": ETH_all_sorted,
        "PID_all_sorted": PID_all_sorted,
        "locations_sorted": locations_sorted,
        "t": t,
        "Fs": Fs,
    }


def run(params=None, paths=None):
    """Higher-level entry: resolve the paper file (or raw fallback), import it,
    and merge in the paper's precomputed within-trial correlations when present.
    """
    if params is None:
        params = config.get_params()
    paths = paths or {}

    candidates = paths.get("files_spatial") or _default_files_spatial(paths)
    src = metadata.ma_first(candidates)
    if src:
        out = import_from(src, params)
    else:
        raw_candidates = paths.get("raw_spatial") or _default_raw_spatial(paths)
        rawdir = metadata.ma_first(raw_candidates, must_exist=True)
        out = _from_raw(rawdir, params)

    corr_candidates = paths.get("files_spatial_corr") or _default_files_spatial_corr(paths)
    corr_src = metadata.ma_first(corr_candidates)
    if corr_src:
        C = dataio.load_mat(corr_src)
        out["corrs"] = np.asarray(C["corrs"], dtype=np.float64).reshape(-1)
        out["corr_locs"] = np.asarray(C["locations_sorted"], dtype=np.float64).reshape(-1)

    return out
