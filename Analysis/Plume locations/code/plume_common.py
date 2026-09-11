r"""plume_common.py -- shared, correctness-critical helpers for the Plume Locations
analysis (Task 1 odor fields + Task 2 signal enhancement). Both tasks import THIS
module so cleaning / clock-alignment / grouping / encounter-detection are identical
everywhere. Read-only w.r.t. DATA. Run this file directly for its self-checks.

Interpreter: run with "$AR_PY". Version tag below is written into output attrs.
"""
from __future__ import annotations

import os
import re
import sys
import numpy as np

VERSION = "plume_common/1.0"
SEED = 1234

AGG_PATH = r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5"
ACCESSOR_DIR = r"C:\Projects\Repos\Mouse Arena\DATA\code"
ARENA = (0.0, 580.0, 0.0, 280.0)  # xmin, xmax, ymin, ymax
DEJUMP_PCTILE = 99.5
ENDPOINT_SPREAD_WARN_PX = 2.0

_LOC_RE = re.compile(r"_Loc(\d+)")
_ANIMAL_RE = re.compile(r"(\d{6})")  # date-like animal/session token in file_name


# --------------------------------------------------------------------------- IO
def load_trials():
    """Return the list of 114 per-trial dicts via the read-only accessor."""
    if ACCESSOR_DIR not in sys.path:
        sys.path.insert(0, ACCESSOR_DIR)
    from mouse_arena_aggregate_io import Aggregate
    agg = Aggregate(AGG_PATH)
    trials = agg.behavior()
    meta = {
        "aggregate_path": agg.path,
        "schema_version": agg.schema_version,
        "Fs": agg.Fs,
        "reference": agg.reference,
    }
    agg.close()
    return trials, meta


# ---------------------------------------------------------------------- GROUPING
def group_of(file_name):
    """End-location group from file_name: 'LocN', else 'anotherLoc', else 'UNKNOWN'."""
    m = _LOC_RE.search(file_name or "")
    if m:
        return "Loc" + m.group(1)
    if "anotherLoc" in (file_name or ""):
        return "anotherLoc"
    return "UNKNOWN"


def animal_of(file_name):
    """Best-effort animal/session id = first 6-digit token in file_name (else '?')."""
    m = _ANIMAL_RE.search(file_name or "")
    return m.group(1) if m else "?"


def group_trials(trials):
    """dict group -> list of trial dicts, preserving order."""
    groups = {}
    for tr in trials:
        groups.setdefault(group_of(tr["file_name"]), []).append(tr)
    return groups


def validate_groups(groups, warn=print):
    """Warn if any Loc group's endpoint spread exceeds ENDPOINT_SPREAD_WARN_PX.
    Returns dict group -> {n, endpoint(2,), spread(2,)}."""
    info = {}
    for g, lst in sorted(groups.items()):
        eps = np.asarray([np.asarray(tr["endpoint"], float) for tr in lst], float)
        spread = eps.max(0) - eps.min(0)
        info[g] = {"n": len(lst), "endpoint": eps.mean(0), "spread": spread}
        if g.startswith("Loc") and np.any(spread > ENDPOINT_SPREAD_WARN_PX):
            warn(f"WARNING: {g} endpoint spread {spread} px > {ENDPOINT_SPREAD_WARN_PX}")
    return info


# --------------------------------------------------------------------- CLEANING
def _in_box(xy):
    x = xy[:, 0]
    y = xy[:, 1]
    return (np.isfinite(x) & np.isfinite(y) &
            (x >= ARENA[0]) & (x <= ARENA[1]) & (y >= ARENA[2]) & (y <= ARENA[3]))


def pooled_dejump_Q(trials, track="head", pctile=DEJUMP_PCTILE):
    """Global de-jump threshold Q = `pctile` of consecutive step sizes among
    box-kept samples, pooled across all trials. One Q so every trial is treated
    identically."""
    steps = []
    for tr in trials:
        xy = np.asarray(tr[track], float)
        m = _in_box(xy)
        kept = xy[m]
        if kept.shape[0] >= 2:
            d = np.linalg.norm(np.diff(kept, axis=0), axis=1)
            steps.append(d)
    if not steps:
        return np.inf
    return float(np.percentile(np.concatenate(steps), pctile))


def clean_track(xy, t, Q):
    """Clean a track: keep finite in-box samples, then drop frame-to-frame jumps
    whose step from the immediately preceding box-kept sample exceeds Q. Returns
    (idx, xy_clean, t_clean) where idx indexes the ORIGINAL arrays (so a signal
    aligned to t can be masked the same way). Deterministic; no randomness.

    The reference sample ALWAYS advances to the current sample, whether it is kept
    or dropped (i.e. Q is applied to consecutive box-kept differences). This is
    essential: an anchored reference that only advances on a keep cascades — after
    one >Q jump the mouse's slow drift away from the stale anchor accumulates past
    Q and deletes the entire movement bout (observed: 42898 -> 926 samples). With
    the advancing reference, a 99.5th-percentile Q removes ~0.5% of samples as
    intended (the fastest single-frame transitions / isolated teleport artifacts).
    """
    xy = np.asarray(xy, float)
    t = np.asarray(t, float)
    box = _in_box(xy)
    box_idx = np.nonzero(box)[0]
    if box_idx.size == 0:
        return box_idx, xy[box_idx], t[box_idx]
    kept = xy[box_idx]
    steps = np.r_[0.0, np.linalg.norm(np.diff(kept, axis=0), axis=1)]  # step from prev box-kept
    keep_mask = steps <= Q
    keep_mask[0] = True  # first box-kept sample always retained
    idx = box_idx[keep_mask]
    return idx, xy[idx], t[idx]


def clean_counts(xy, t, Q):
    """Return (n_total, n_after_box, n_after_dejump) for logging."""
    xy = np.asarray(xy, float)
    n = xy.shape[0]
    nb = int(_in_box(xy).sum())
    idx, _, _ = clean_track(xy, t, Q)
    return n, nb, int(idx.size)


# -------------------------------------------------------------------- ALIGNMENT
def align_signal(head_time, sig_time, sig):
    """Bring a sensor-clock signal onto the head clock. NaN outside coverage.
    NEVER resample position onto the sensor clock."""
    head_time = np.asarray(head_time, float)
    sig_time = np.asarray(sig_time, float)
    sig = np.asarray(sig, float)
    return np.interp(head_time, sig_time, sig, left=np.nan, right=np.nan)


def endpoint_of(trial):
    return np.asarray(trial["endpoint"], float).reshape(2)


def dist_to_endpoint(xy, endpoint):
    xy = np.asarray(xy, float)
    ep = np.asarray(endpoint, float).reshape(2)
    return np.hypot(xy[:, 0] - ep[0], xy[:, 1] - ep[1])


# ------------------------------------------------------------- ENCOUNTER DETECT
def mad(x, scale=1.4826):
    """Robust noise estimate: scale * median(|x - median|). NaNs ignored."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.nan
    med = np.median(x)
    return float(scale * np.median(np.abs(x - med)))


def detect_encounters(signal, time, thresh, refractory_s, min_prominence=0.0):
    """Generic encounter detector shared by Task 1 (odor encounters) and Task 2
    (before/after). An encounter = a local peak of `signal` that (a) exceeds
    `thresh`, (b) has prominence >= min_prominence above the surrounding local
    minima, and (c) respects a refractory gap (peaks within refractory_s of an
    already-accepted, larger peak are suppressed). Returns integer peak indices
    into `signal` (sorted by time). NaNs are treated as -inf (never peaks).

    Deterministic. `time` must be strictly increasing seconds.
    """
    s = np.asarray(signal, float).copy()
    t = np.asarray(time, float)
    s[~np.isfinite(s)] = -np.inf
    n = s.size
    if n < 3:
        return np.array([], int)
    # candidate local maxima above threshold
    left = s[1:-1] > s[:-2]
    right = s[1:-1] >= s[2:]
    cand = np.nonzero(left & right & (s[1:-1] > thresh))[0] + 1
    if cand.size == 0:
        return np.array([], int)
    # prominence: peak minus max of the two adjacent troughs within a small window
    keep_prom = []
    for p in cand:
        lo = max(0, p - 1)
        hi = min(n, p + 2)
        local_min = np.min(s[lo:hi])
        if (s[p] - local_min) >= min_prominence:
            keep_prom.append(p)
    cand = np.asarray(keep_prom, int)
    if cand.size == 0:
        return np.array([], int)
    # refractory: greedily accept peaks by descending amplitude, suppress
    # any candidate within refractory_s of an accepted peak.
    order = cand[np.argsort(-s[cand])]
    accepted = []
    acc_t = []
    for p in order:
        tp = t[p]
        if all(abs(tp - at) >= refractory_s for at in acc_t):
            accepted.append(p)
            acc_t.append(tp)
    accepted = np.asarray(sorted(accepted), int)
    return accepted


# -------------------------------------------------------- CONCENTRATION INDICES
def gini(values):
    """Gini coefficient of non-negative values (masked NaNs dropped). 0=uniform,
    ->1 concentrated. Values shifted to be non-negative if a small negative floor."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return np.nan
    if np.min(v) < 0:
        v = v - np.min(v)
    if np.all(v == 0):
        return 0.0
    v = np.sort(v)
    n = v.size
    cum = np.cumsum(v)
    return float((n + 1 - 2 * np.sum(cum) / cum[-1]) / n)


def normalized_entropy(values):
    """Shannon entropy of the value distribution normalized to [0,1] (1=uniform,
    0=all mass in one bin). NaNs dropped; negatives floored to 0."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    v = np.clip(v, 0, None)
    tot = v.sum()
    if v.size <= 1 or tot <= 0:
        return np.nan
    p = v / tot
    p = p[p > 0]
    H = -np.sum(p * np.log(p))
    return float(H / np.log(v.size))


# ------------------------------------------------------------------- SELF-CHECK
def _selfcheck():
    np.random.seed(SEED)
    ok = True

    # grouping
    assert group_of("x_Loc5.avi.dat") == "Loc5"
    assert group_of("foo_anotherLoc_bar") == "anotherLoc"
    assert group_of("nothing") == "UNKNOWN"

    # box filter + de-jump
    xy = np.array([[10, 10], [11, 10], [900, 900], [12, 10], [-5, 5], [13, 10]], float)
    t = np.arange(len(xy), dtype=float)
    idx, cxy, ct = clean_track(xy, t, Q=50.0)
    # out-of-box (900,900) and (-5,5) removed -> 4 in-box; none exceed Q=50 among kept
    assert idx.tolist() == [0, 1, 3, 5], idx.tolist()

    # de-jump removes a large in-box jump (advancing reference: the teleport
    # sample AND its return sample are both dropped -> [0,1]); no cascade beyond.
    xy2 = np.array([[10, 10], [11, 10], [500, 10], [12, 10]], float)
    t2 = np.arange(4, dtype=float)
    idx2, _, _ = clean_track(xy2, t2, Q=50.0)
    assert idx2.tolist() == [0, 1], idx2.tolist()

    # advancing reference does NOT cascade on slow drift away from an early jump:
    # one big jump then many small steps -> only the jump sample is lost.
    xy3 = np.array([[0, 0], [100, 0], [101, 0], [102, 0], [103, 0], [104, 0]], float)
    t3 = np.arange(6, dtype=float)
    idx3, _, _ = clean_track(xy3, t3, Q=50.0)
    assert idx3.tolist() == [0, 2, 3, 4, 5], idx3.tolist()

    # alignment: exact on a ramp, NaN outside coverage
    st = np.array([0.0, 1.0, 2.0])
    sv = np.array([0.0, 10.0, 20.0])
    ht = np.array([-0.5, 0.5, 1.5, 2.5])
    a = align_signal(ht, st, sv)
    assert np.isnan(a[0]) and np.isnan(a[3])
    assert abs(a[1] - 5.0) < 1e-9 and abs(a[2] - 15.0) < 1e-9

    # detector: three clean peaks, refractory merges the doublet
    sig = np.zeros(100)
    for c in (20, 21, 60):  # 20 & 21 are within refractory -> one kept
        sig[c] = 5.0
    sig[21] = 4.0
    tt = np.arange(100) * 0.01  # 100 Hz
    pk = detect_encounters(sig, tt, thresh=1.0, refractory_s=0.1, min_prominence=1.0)
    assert pk.tolist() == [20, 60], pk.tolist()

    # gini / entropy sanity
    assert abs(gini(np.ones(10)) - 0.0) < 1e-9
    g_conc = gini(np.array([0, 0, 0, 0, 10.0]))
    assert g_conc > 0.7, g_conc
    assert abs(normalized_entropy(np.ones(8)) - 1.0) < 1e-9

    # mad
    assert abs(mad(np.array([0, 0, 0, 0, 0.0]))) < 1e-12

    print("plume_common self-check: PASS")
    return ok


if __name__ == "__main__":
    _selfcheck()
