"""s1b_import_frequency — port of Stage1_Import/s1b_import_frequency.m.

STAGE 1b -- Data behind Figures 3-4: paired PID + sensor to 5/10/15 Hz
ethanol fluctuations.

Strategy: load paper file (Fig3/Data/data.mat or Fig4/data.mat) giving
ETH_all_sorted, PID_all_sorted, freqs_sorted, val_all_sorted. Fallback:
auto-discover raw *.dat, read the valve channel, derive frequency directly
(extract_pulse_metrics) with the filename (_Frequency_NHz) as a check.

OUTPUT (dict): ETH_all_sorted, PID_all_sorted, freqs, t, Fs.
Reference: Tariq et al. (2020), Figs. 3-4. Source: Figure3.m.
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
    """Resolve the paper backup root directory (s1b configuration)."""
    paths = paths or {}
    return paths.get(
        "paper_root",
        os.path.join(paths.get("arena_root", _DEFAULT_ARENA_ROOT),
                     "Ethanol Sensor Data", "Paper_BackUp", "Paper"),
    )


def _default_files_frequency(paths):
    """Return candidate paths to the paper's Fig3/Fig4 frequency data."""
    paper = _paper_root(paths)
    return [
        os.path.join(paper, "Fig3", "Data", "data.mat"),
        os.path.join(paper, "Fig4", "data.mat"),
    ]


def _default_raw_frequency(paths):
    """Return candidate paths to the paper's raw Fig3 frequency data."""
    return [os.path.join(_paper_root(paths), "Fig3", "Data", "data")]


def _select_freqs(S):
    """Select the per-row frequency label array from the loaded paper file.

    The publication's Fig3/Fig4 processed .mat carries the frequency label
    that is row-aligned with ETH_all_sorted/PID_all_sorted under the plain
    'freqs' variable; 'freqs_sorted' (when present) is an auxiliary
    ascending-order copy of the same labels, not the row-aligned one. We
    therefore prefer 'freqs' and fall back to 'freqs_sorted' only when
    'freqs' itself is absent (matches the golden Fig3 fixture).
    """
    if "freqs" in S:
        return np.asarray(S["freqs"], dtype=np.float64).reshape(-1)
    return np.asarray(S["freqs_sorted"], dtype=np.float64).reshape(-1)


def import_from(path, params=None):
    """Pure transform: load the paper's Fig3/Fig4 data.mat and compute t/Fs.

    MATLAB:
        S = load(src);
        ETH_all_sorted = S.ETH_all_sorted;
        PID_all_sorted = S.PID_all_sorted;
        if isfield(S,'freqs_sorted'); freqs = S.freqs_sorted(:)';
        else; freqs = S.freqs(:)'; end
        t = (0:size(ETH_all_sorted,2)-1)/Fs;
    """
    if params is None:
        params = config.get_params()
    Fs = params.Fs

    S = dataio.load_mat(path)
    ETH_all_sorted = np.asarray(S["ETH_all_sorted"], dtype=np.float64)
    PID_all_sorted = np.asarray(S["PID_all_sorted"], dtype=np.float64)
    freqs = _select_freqs(S)

    ncols = ETH_all_sorted.shape[1]
    t = np.arange(ncols, dtype=np.float64) / Fs

    return {
        "ETH_all_sorted": ETH_all_sorted,
        "PID_all_sorted": PID_all_sorted,
        "freqs": freqs,
        "t": t,
        "Fs": Fs,
    }


def _from_raw(rawdir, params):
    """Fallback: derive frequency.mat fields from raw LabView .dat files.

    MATLAB:
        files = dir(fullfile(rawdir,'*.dat'));
        for each file: D = read_labview_dat(...); [~,~,fhz] = extract_pulse_metrics(D.val,Fs);
            meta = parse_trial_meta(name); fr = meta.freq or round(fhz);
            ETH_all(end+1,:) = D.ETH(:)'; PID_all(end+1,:) = D.PID(:)'; freqs(end+1) = fr;
        [freqs,o] = sort(freqs); ETH_all_sorted=ETH_all(o,:); PID_all_sorted=PID_all(o,:);
    """
    Fs = params.Fs
    files = sorted(glob.glob(os.path.join(rawdir, "*.dat")))

    ETH_all, PID_all, freqs = [], [], []
    for fpath in files:
        D = read_labview_dat(fpath, params.chan_pid, params)
        _onsets, _dur_s, fhz = metadata.extract_pulse_metrics(D["val"], Fs)
        meta = metadata.parse_trial_meta(os.path.basename(fpath))
        fr = meta["freq"] if not np.isnan(meta["freq"]) else round(fhz)
        ETH_all.append(np.asarray(D["ETH"]).reshape(-1))
        PID_all.append(np.asarray(D["PID"]).reshape(-1))
        freqs.append(fr)

    ETH_all = np.asarray(ETH_all, dtype=np.float64)
    PID_all = np.asarray(PID_all, dtype=np.float64)
    freqs = np.asarray(freqs, dtype=np.float64)

    order = np.argsort(freqs, kind="stable")
    freqs_sorted = freqs[order]
    ETH_all_sorted = ETH_all[order, :] if ETH_all.size else ETH_all
    PID_all_sorted = PID_all[order, :] if PID_all.size else PID_all

    ncols = ETH_all_sorted.shape[1] if ETH_all_sorted.ndim == 2 else 0
    t = np.arange(ncols, dtype=np.float64) / Fs

    return {
        "ETH_all_sorted": ETH_all_sorted,
        "PID_all_sorted": PID_all_sorted,
        "freqs": freqs_sorted,
        "t": t,
        "Fs": Fs,
    }


def run(params=None, paths=None):
    """Higher-level entry: resolve the paper file (or raw fallback) and import it."""
    if params is None:
        params = config.get_params()
    paths = paths or {}

    candidates = paths.get("files_frequency") or _default_files_frequency(paths)
    src = metadata.ma_first(candidates)
    if src:
        return import_from(src, params)

    raw_candidates = paths.get("raw_frequency") or _default_raw_frequency(paths)
    rawdir = metadata.ma_first(raw_candidates, must_exist=True)
    return _from_raw(rawdir, params)
