r"""reactions_common.py -- single source of truth for the Nose-Sweeps analysis.
Imports and reuses the validated plume_common (clean_track advancing-reference
de-jump, mad, group_of, pooled_dejump_Q, align_signal, endpoint_of). Adds velocities
(Savitzky-Golay), the normalized-head-movement ratio R, sweep detectors (R-based and
numerator-only body-frame), baseline-subtracted ethanol, and the odor-reached lookup
that reuses the Plume-locations odor_fields.h5. Everything on the HEAD clock.

Run directly for self-checks. Interpreter: "$AR_PY".
"""
from __future__ import annotations

import os
import sys
import numpy as np
from scipy.signal import savgol_filter, find_peaks

sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import plume_common as pc  # noqa: E402

VERSION = "reactions_common/1.0"
SEED = pc.SEED  # 1234
ARENA = pc.ARENA
ODOR_FIELDS_H5 = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5"
ODOR_CUTOFF = 0.001

# velocity / sweep defaults (D3/D5/D7)
SG_WIN, SG_POLY = 7, 2
R_HEIGHT, R_PROM, REFRACTORY_S = 1.5, 0.5, 0.30
BFRAME_K, BFRAME_PROM_FRAC = 1.5, 0.5
ETH_BASELINE_W_S, ETH_BASELINE_PCT = 20.0, 10.0

# re-exports
clean_track = pc.clean_track
mad = pc.mad
group_of = pc.group_of
pooled_dejump_Q = pc.pooled_dejump_Q
align_signal = pc.align_signal
endpoint_of = pc.endpoint_of


# ------------------------------------------------------------- interpolation
def interp_xy_to_head(head_t, src_t, src_xy):
    """Interpolate a 2-D track onto the head clock (per-axis np.interp; clamp edges)."""
    head_t = np.asarray(head_t, float)
    src_t = np.asarray(src_t, float)
    src_xy = np.asarray(src_xy, float)
    return np.column_stack([np.interp(head_t, src_t, src_xy[:, 0]),
                            np.interp(head_t, src_t, src_xy[:, 1])])


# ------------------------------------------------------------------ velocities
def speed_savgol(xy, dt, win=SG_WIN, poly=SG_POLY):
    """Smoothed speed (px/s) via Savitzky-Golay first derivative per axis (D3).
    Returns an array the length of xy; NaN if too short."""
    xy = np.asarray(xy, float)
    n = xy.shape[0]
    if n < max(win, poly + 2):
        return np.full(n, np.nan)
    w = win if win % 2 == 1 else win + 1
    if w > n:
        w = n if n % 2 == 1 else n - 1
    vx = savgol_filter(xy[:, 0], w, poly, deriv=1, delta=dt)
    vy = savgol_filter(xy[:, 1], w, poly, deriv=1, delta=dt)
    return np.hypot(vx, vy)


def robust_sd(x):
    return 1.4826 * mad(x)


# ---------------------------------------------------------- baseline ethanol
def baseline_subtract_ethanol(eth, eth_t, W_s=ETH_BASELINE_W_S, pct=ETH_BASELINE_PCT):
    """Raw ethanol minus a rolling low-percentile baseline (D8; reuse Plume drift
    removal). Returns the baseline-subtracted trace on the SENSOR clock (align to the
    head clock separately). Uses pandas rolling quantile, centered, min_periods=1."""
    import pandas as pd
    eth = np.asarray(eth, float)
    eth_t = np.asarray(eth_t, float)
    if eth.size < 3:
        return eth - np.nanmedian(eth)
    dt = np.median(np.diff(eth_t))
    win = max(1, int(round(W_s / dt)))
    s = pd.Series(eth)
    baseline = s.rolling(win, min_periods=1, center=True).quantile(pct / 100.0).to_numpy()
    return eth - baseline


# ------------------------------------------------------------- sweep detectors
def _distance_frames(t, refractory_s):
    dt = np.median(np.diff(np.asarray(t, float)))
    return max(1, int(round(refractory_s / dt)))


def detect_sweeps_R(R, t, height=R_HEIGHT, prom=R_PROM, refractory_s=REFRACTORY_S):
    """Local maxima of the normalized-head-movement ratio R (D5). NaN treated as 0."""
    R = np.asarray(R, float)
    Rc = np.where(np.isfinite(R), R, 0.0)
    pk, props = find_peaks(Rc, height=height, prominence=prom,
                           distance=_distance_frames(t, refractory_s))
    return pk


def detect_sweeps_bframe(bframe, t, k=BFRAME_K, prom_frac=BFRAME_PROM_FRAC,
                         refractory_s=REFRACTORY_S):
    """Numerator-only sweep detector on body-frame nose speed (D7): height =
    median + k*robustSD, prominence = prom_frac*robustSD. No v_com in the detector."""
    b = np.asarray(bframe, float)
    finite = b[np.isfinite(b)]
    if finite.size < 3:
        return np.array([], int)
    med = np.median(finite)
    sd = robust_sd(finite)
    if not np.isfinite(sd) or sd <= 0:
        sd = np.std(finite) if finite.size else 1.0
    height = med + k * sd
    prom = prom_frac * sd
    bc = np.where(np.isfinite(b), b, 0.0)
    pk, _ = find_peaks(bc, height=height, prominence=prom,
                       distance=_distance_frames(t, refractory_s))
    return pk


# ---------------------------------------------------------- odor-reached lookup
_ODOR_CACHE = {}


def load_odor_field(loc, path=ODOR_FIELDS_H5):
    """Load a Plume-locations odor field group read-only. Returns dict or None."""
    if loc in _ODOR_CACHE:
        return _ODOR_CACHE[loc]
    import h5py
    if not os.path.exists(path):
        _ODOR_CACHE[loc] = None
        return None
    with h5py.File(path, "r") as f:
        if loc not in f:
            _ODOR_CACHE[loc] = None
            return None
        g = f[loc]
        field = {"max": g["max"][()], "count": g["count"][()],
                 "x_edges": g["x_edges"][()], "y_edges": g["y_edges"][()]}
    _ODOR_CACHE[loc] = field
    return field


def is_in_odor(field, x, y, cutoff=ODOR_CUTOFF):
    """Vectorized: True where (x,y) maps to a valid (count>=3) bin with max>cutoff.
    x,y are arrays (px). Row = y bin, col = x bin (0-based), matching the odor field."""
    x = np.atleast_1d(np.asarray(x, float))
    y = np.atleast_1d(np.asarray(y, float))
    out = np.zeros(x.shape, bool)
    if field is None:
        return out
    xe, ye = field["x_edges"], field["y_edges"]
    mx, cnt = field["max"], field["count"]
    ny, nx = mx.shape
    col = np.searchsorted(xe, x, side="right") - 1
    row = np.searchsorted(ye, y, side="right") - 1
    ok = (col >= 0) & (col < nx) & (row >= 0) & (row < ny) & np.isfinite(x) & np.isfinite(y)
    idx = np.nonzero(ok)[0]
    if idx.size:
        r, c = row[idx], col[idx]
        mvals = mx[r, c]
        cvals = cnt[r, c]
        good = np.isfinite(mvals) & (mvals > cutoff) & (cvals >= 3)
        out[idx] = good
    return out


# ------------------------------------------------------------ peri-event helper
def peri_event_matrix(sig, t, event_times, window=(-1.0, 1.0), grid_dt=0.05):
    """(n_events, n_grid) matrix of sig interpolated on window grid around each event.
    NaN outside the trace's covered range. grid is inclusive of both ends."""
    t = np.asarray(t, float)
    sig = np.asarray(sig, float)
    grid = np.arange(window[0], window[1] + 1e-9, grid_dt)
    ev = np.atleast_1d(np.asarray(event_times, float))
    M = np.full((ev.size, grid.size), np.nan)
    finite = np.isfinite(sig)
    if finite.sum() < 2:
        return grid, M
    tt, ss = t[finite], sig[finite]
    for i, e in enumerate(ev):
        q = e + grid
        vals = np.interp(q, tt, ss, left=np.nan, right=np.nan)
        M[i] = vals
    return grid, M


# ------------------------------------------------------------------- self-check
def _selfcheck():
    np.random.seed(SEED)
    pc._selfcheck()

    dt = 0.01
    n = 50
    t = np.arange(n) * dt
    xy = np.column_stack([30.0 * t, 40.0 * t])  # constant velocity (30,40) -> speed 50
    sp = speed_savgol(xy, dt)
    assert np.nanmax(np.abs(sp[5:-5] - 50.0)) < 1e-6, sp[5:-5][:3]

    # R guard: v_com all ~0 -> denom floored, R finite
    v_nose = np.full(n, 10.0); v_com = np.zeros(n); v_floor = 2.0
    R = v_nose / np.maximum(v_com, v_floor)
    assert np.all(np.isfinite(R)) and abs(R[0] - 5.0) < 1e-9

    # R sweep detector finds an obvious peak
    R2 = np.ones(n) * 1.0
    R2[25] = 3.0
    pk = detect_sweeps_R(R2, t, height=1.5, prom=0.5, refractory_s=0.30)
    assert 25 in pk.tolist(), pk

    # body-frame detector finds a peak above median+k*SD
    b = np.abs(np.random.default_rng(SEED).normal(5, 1, n))
    b[30] = 30.0
    pkb = detect_sweeps_bframe(b, t)
    assert 30 in pkb.tolist(), pkb

    # baseline subtraction removes a constant offset-ish slow baseline
    ebt = np.arange(2000) * 0.002
    e = np.full(2000, 0.5) + 0.001 * np.sin(2 * np.pi * ebt / 0.1)  # flat + fast wiggle
    ebs = baseline_subtract_ethanol(e, ebt, W_s=20, pct=10)
    assert np.nanmedian(ebs) < 0.2  # slow baseline (~0.5) removed

    # is_in_odor on a synthetic field: one hot bin (count>=3, max>cutoff)
    field = {"max": np.array([[0.0, 0.05], [np.nan, 0.0]]),
             "count": np.array([[5, 5], [1, 5]]),
             "x_edges": np.array([0.0, 10.0, 20.0]),
             "y_edges": np.array([0.0, 10.0, 20.0])}
    assert is_in_odor(field, [15.0], [5.0])[0]      # col1,row0 max .05 count5 -> True
    assert not is_in_odor(field, [5.0], [5.0])[0]   # col0,row0 max 0 -> False
    assert not is_in_odor(field, [5.0], [15.0])[0]  # col0,row1 count1 -> False
    assert not is_in_odor(field, [100.0], [5.0])[0] # out of range

    # peri-event matrix shape + NaN edges
    grid, M = peri_event_matrix(np.arange(100.0), np.arange(100) * 0.01,
                                [0.5], window=(-1.0, 1.0), grid_dt=0.05)
    assert M.shape == (1, grid.size)
    assert np.isnan(M[0, 0])  # -1s before t=0.5 -> t=-0.5 outside [0,..] -> NaN

    print("reactions_common self-check: PASS")


if __name__ == "__main__":
    _selfcheck()
