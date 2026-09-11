r"""build_bouts.py -- DATA-ANALYST pipeline for the Selective Sampling-Bout analysis
(reactions_2). Detects rare pause+cast sampling bouts on a translation-invariant
head-body bearing kinematic, characterizes them (Deliverable A), runs H1/H2/H3
trial-level inference, and SAVES per-bout / per-trial objects + stats. Builds NO
figures/reports; it only stores the arrays figures will plot.

Pre-registered plan (PLAN.md / plan.json, D1-D12). Seed 1234. TRIAL-LEVEL inference
only (Wilcoxon + trial bootstrap 2000); NEVER per-event point-bootstrap.

Interpreter: "$AR_PY". Run:
    "$AR_PY" build_bouts.py            # full 114
    "$AR_PY" build_bouts.py --slice 5  # slice-first smoke test (no saves)
"""
from __future__ import annotations

import os
import sys
import json
import time
import logging
import argparse
import datetime as _dt

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reactions2_common as r2  # noqa: E402
import plume_common as pc       # noqa: E402  (re-exported via r2 but used directly too)

# --------------------------------------------------------------------- paths
BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
DATA_DIR = os.path.join(BASE, "data")
LOG_DIR = os.path.join(BASE, "logs")
H5_PATH = os.path.join(DATA_DIR, "bouts.h5")
BOUTS_JSON = os.path.join(DATA_DIR, "bouts.json")
STATS_JSON = os.path.join(DATA_DIR, "stats.json")
ODOR_FIELDS_H5 = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5"
AGG_PATH = r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5"

SEED = 1234
N_BOOT = 2000
N_PERM = 2000
V1_BASELINE_RATE = 1.7
POOLED_GROUPS = {"Loc1", "Loc2", "Loc3", "Loc4", "Loc5", "Loc6"}
FALLBACK_R_PX = 100.0

# windows (D11)
PERI_WIN = (-1.0, 1.0)
GRID_DT = 0.05
PERI_ODOR_WIN = (-0.5, 0.5)      # H1 peri-odor mean
PRE_ONSET_WIN = (-0.75, -0.25)   # H2 pre-onset mean
SLOPE_WIN = (-1.0, 0.0)          # H2 onset-aligned slope

# D6 rarity gate
D6_TIGHTEN_TRIGGER = 0.5

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("build_bouts")


def _setup_logging():
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(os.path.join(LOG_DIR, "build_bouts.log"), mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(sh)


def _utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================ window helpers
def _window_mean(sig, t, event_times, window):
    """Per-event mean of sig over an absolute-time window around each event
    (interp onto a fine grid inside the window, then nanmean). Returns 1D array
    length len(event_times). NaN if no coverage."""
    ev = np.atleast_1d(np.asarray(event_times, float))
    if ev.size == 0:
        return np.array([], float)
    grid, M = r2.peri_event_matrix(sig, t, ev, window=window, grid_dt=GRID_DT)
    with np.errstate(all="ignore"):
        return np.nanmean(M, axis=1)


def _onset_slope(sig, t, event_times, window):
    """Per-event linear-regression slope of sig vs time over `window` (onset at 0).
    Returns 1D array (deg-agnostic; a.u./s). NaN where <2 finite grid points."""
    ev = np.atleast_1d(np.asarray(event_times, float))
    out = np.full(ev.size, np.nan)
    if ev.size == 0:
        return out
    grid, M = r2.peri_event_matrix(sig, t, ev, window=window, grid_dt=GRID_DT)
    for i in range(ev.size):
        y = M[i]
        ok = np.isfinite(y)
        if ok.sum() >= 2 and np.ptp(grid[ok]) > 0:
            lr = stats.linregress(grid[ok], y[ok])
            out[i] = lr.slope
    return out


# ============================================================ PASS 1 kinematics
def _trial_kinematics(tr, Qh, Qb):
    """Clean head & body, interp body onto head clock, compute dt, v_com, phi, omega,
    baseline-subtracted ethanol on head clock. Returns dict or None if too short."""
    ht = np.asarray(tr["head_time"], float)
    bt = np.asarray(tr["body_time"], float)
    head = np.asarray(tr["head"], float)
    body = np.asarray(tr["body"], float)

    idx_h, head_c, ht_c = r2.clean_track(head, ht, Qh)
    idx_b, body_c, bt_c = r2.clean_track(body, bt, Qb)

    n_head_box = int(pc._in_box(head).sum())
    n_body_box = int(pc._in_box(body).sum())
    head_removed = (1 - head_c.shape[0] / n_head_box) if n_head_box else np.nan
    body_removed = (1 - body_c.shape[0] / n_body_box) if n_body_box else np.nan

    if head_c.shape[0] < r2.SG_WIN + 2 or bt_c.size < 2:
        return None

    dt = float(np.median(np.diff(ht_c)))
    if not np.isfinite(dt) or dt <= 0:
        return None

    body_h = r2.interp_xy_to_head(ht_c, bt_c, body_c)
    v_com = r2.speed_savgol(body_h, dt)
    phi = r2.bearing_phi(head_c, body_h)
    omega = r2.angular_speed_omega(phi, dt)

    eth = np.asarray(tr["ethanol"], float)
    eth_t = np.asarray(tr["ethanol_time"], float)
    eth_bs_sensor = r2.baseline_subtract_ethanol(eth, eth_t)
    eth_bs_h = r2.align_signal(ht_c, eth_t, eth_bs_sensor)

    dur = float(ht_c[-1] - ht_c[0]) if ht_c.size > 1 else 0.0

    return {
        "head_c": head_c, "body_h": body_h, "head_t": ht_c,
        "dt": dt, "v_com": v_com, "phi": phi, "omega": omega,
        "eth_bs_h": eth_bs_h, "dur": dur,
        "head_removed": head_removed, "body_removed": body_removed,
        "endpoint": r2.endpoint_of(tr),
    }


# ============================================================ PASS 2 per-trial
def _detect_and_measure(kin, bout_params, v_pause, omega_min, end_loc, rng):
    """Given kinematics + thresholds, detect bouts + incidental, measure per-bout
    odor features, f_bout/f_occ, and per-trial H1/H2/H3 summary stats. Returns dict."""
    head_c = kin["head_c"]; head_t = kin["head_t"]
    v_com = kin["v_com"]; phi = kin["phi"]; omega = kin["omega"]
    eth_bs_h = kin["eth_bs_h"]; dur = kin["dur"]

    bouts = r2.detect_bouts(v_com, phi, omega, head_t, v_pause, omega_min,
                            tau_pause=bout_params["tau_pause"],
                            dphi_min=bout_params["dphi_min"],
                            t_merge=bout_params["t_merge"])
    inc_idx = r2.detect_incidental(v_com, omega, head_t, v_pause, omega_min)

    onset_idx = np.array([b["onset_idx"] for b in bouts], int)
    peak_idx = np.array([b["peak_idx"] for b in bouts], int)
    onset_times = head_t[onset_idx] if onset_idx.size else np.array([], float)
    peak_times = head_t[peak_idx] if peak_idx.size else np.array([], float)
    inc_times = head_t[inc_idx] if inc_idx.size else np.array([], float)

    # ---- odor field / in-odor lookup (D9)
    field = r2.load_odor_field(end_loc, path=ODOR_FIELDS_H5) if end_loc in POOLED_GROUPS or end_loc == "anotherLoc" else None
    ep = kin["endpoint"]

    def _in_odor_xy(xs, ys):
        xs = np.atleast_1d(np.asarray(xs, float)); ys = np.atleast_1d(np.asarray(ys, float))
        if field is not None:
            return r2.is_in_odor(field, xs, ys, cutoff=r2.ODOR_CUTOFF)
        # fallback: within FALLBACK_R_PX of source endpoint
        return np.hypot(xs - ep[0], ys - ep[1]) <= FALLBACK_R_PX

    if onset_idx.size:
        ox = head_c[onset_idx, 0]; oy = head_c[onset_idx, 1]
        in_odor = _in_odor_xy(ox, oy)
    else:
        in_odor = np.array([], bool)

    # ---- per-bout odor features
    peri_odor = _window_mean(eth_bs_h, head_t, onset_times, PERI_ODOR_WIN)      # H1
    pre_onset = _window_mean(eth_bs_h, head_t, onset_times, PRE_ONSET_WIN)      # H2
    onset_slope = _onset_slope(eth_bs_h, head_t, onset_times, SLOPE_WIN)        # H2

    # incidental peri-odor (specificity)
    inc_peri_odor = _window_mean(eth_bs_h, head_t, inc_times, PERI_ODOR_WIN)
    inc_pre_onset = _window_mean(eth_bs_h, head_t, inc_times, PRE_ONSET_WIN)

    # ---- H1(a): matched-count random-time null (per-trial null mean)
    n_b = onset_idx.size
    span_lo, span_hi = (head_t[0], head_t[-1]) if head_t.size else (0.0, 0.0)
    null_peri_mean = np.nan
    if n_b >= 1 and dur > 0:
        rand_t = rng.uniform(span_lo, span_hi, size=(N_PERM, n_b))
        perm_means = np.full(N_PERM, np.nan)
        # vectorize per-perm via window mean of all draws at once
        flat = rand_t.reshape(-1)
        wm = _window_mean(eth_bs_h, head_t, flat, PERI_ODOR_WIN).reshape(N_PERM, n_b)
        with np.errstate(all="ignore"):
            perm_means = np.nanmean(wm, axis=1)
        null_peri_mean = float(np.nanmean(perm_means))

    # ---- H2 null (pre-onset matched null) + trial baseline
    trial_baseline = float(np.nanmedian(eth_bs_h)) if np.any(np.isfinite(eth_bs_h)) else np.nan
    null_pre_mean = np.nan
    if n_b >= 1 and dur > 0:
        rand_t2 = rng.uniform(span_lo, span_hi, size=(N_PERM, n_b))
        flat2 = rand_t2.reshape(-1)
        wm2 = _window_mean(eth_bs_h, head_t, flat2, PRE_ONSET_WIN).reshape(N_PERM, n_b)
        with np.errstate(all="ignore"):
            null_pre_mean = float(np.nanmean(np.nanmean(wm2, axis=1)))

    # ---- H3: f_bout, f_occ, permutation null
    all_in_odor = _in_odor_xy(head_c[:, 0], head_c[:, 1])
    f_occ = float(np.mean(all_in_odor)) if all_in_odor.size else np.nan
    f_bout = float(np.mean(in_odor)) if in_odor.size else np.nan
    f_bout_null_mean = np.nan
    if n_b >= 1 and head_c.shape[0] >= 1:
        # draw n_b random FRAME indices (uniform over kept head frames), 2000 draws
        ridx = rng.integers(0, head_c.shape[0], size=(N_PERM, n_b))
        # in-odor per frame precomputed -> average fraction per draw
        frac_null = all_in_odor[ridx].mean(axis=1)
        f_bout_null_mean = float(np.mean(frac_null))

    # ---- per-trial summaries (bouts)
    def _nm(a):
        a = np.asarray(a, float)
        return float(np.nanmean(a)) if a.size and np.any(np.isfinite(a)) else np.nan

    bout_v_com = np.array([b["v_com_during"] for b in bouts], float)
    bout_excursion = np.array([b["excursion_deg"] for b in bouts], float)
    bout_peak_omega = np.array([b["peak_omega"] for b in bouts], float)
    bout_dur = np.array([b["dur_s"] for b in bouts], float)

    # incidental kinematics for selectivity (v_com at peak, omega at peak)
    inc_v_com = v_com[inc_idx] if inc_idx.size else np.array([], float)
    inc_peak_omega = omega[inc_idx] if inc_idx.size else np.array([], float)

    return {
        "bouts": bouts,
        "onset_idx": onset_idx, "peak_idx": peak_idx,
        "onset_times": onset_times, "peak_times": peak_times,
        "inc_idx": inc_idx, "inc_times": inc_times,
        "in_odor": in_odor,
        "peri_odor": peri_odor, "pre_onset": pre_onset, "onset_slope": onset_slope,
        "inc_peri_odor": inc_peri_odor, "inc_pre_onset": inc_pre_onset,
        "bout_count": int(n_b),
        "bout_rate": (n_b / dur) if dur > 0 else np.nan,
        "n_incidental": int(inc_idx.size),
        "f_bout": f_bout, "f_occ": f_occ, "f_bout_null_mean": f_bout_null_mean,
        "trial_baseline": trial_baseline,
        # per-trial mean summaries for trial-level inference
        "m_peri_odor": _nm(peri_odor),
        "m_null_peri": null_peri_mean,
        "m_pre_onset": _nm(pre_onset),
        "m_null_pre": null_pre_mean,
        "m_onset_slope": _nm(onset_slope),
        "m_inc_peri_odor": _nm(inc_peri_odor),
        "m_inc_pre_onset": _nm(inc_pre_onset),
        "m_bout_v_com": _nm(bout_v_com),
        "m_bout_excursion": _nm(bout_excursion),
        "m_bout_peak_omega": _nm(bout_peak_omega),
        "m_inc_v_com": _nm(inc_v_com),
        "m_inc_peak_omega": _nm(inc_peak_omega),
        "bout_v_com": bout_v_com, "bout_excursion": bout_excursion,
        "bout_peak_omega": bout_peak_omega, "bout_dur": bout_dur,
        "inc_v_com": inc_v_com, "inc_peak_omega": inc_peak_omega,
    }


# ============================================================ stats helpers
def _wilcoxon_greater(diff):
    """One-sided Wilcoxon signed-rank (H1: median diff > 0) on paired diffs.
    Returns (stat, p, n_used). Drops NaN and exact zeros (wilcoxon default)."""
    d = np.asarray(diff, float)
    d = d[np.isfinite(d)]
    n = d.size
    if n < 1 or np.all(d == 0):
        return (np.nan, np.nan, int(n))
    try:
        res = stats.wilcoxon(d, alternative="greater", zero_method="wilcox")
        return (float(res.statistic), float(res.pvalue), int(n))
    except ValueError:
        return (np.nan, np.nan, int(n))


def _trial_bootstrap_ci(values, n_boot=N_BOOT, seed=SEED, agg=np.nanmean):
    """Trial-level bootstrap 95% CI of an aggregate (default mean) over per-trial
    values. Resamples TRIALS with replacement (never events)."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    n = v.size
    boots = np.array([agg(v[rng.integers(0, n, n)]) for _ in range(n_boot)])
    return (float(agg(v)), float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5)))


def _median(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    return float(np.median(a)) if a.size else np.nan


def _peri_curve(rows, key_times, sig_key, window=PERI_WIN, seed=SEED):
    """Onset-aligned mean curve + 95% CI (trial bootstrap) of a signal over `window`.
    rows: list of per-trial dicts with kin[sig_key], head_t, and event times key_times.
    Trial-level: each trial contributes its per-trial MEAN curve; bootstrap over trials.
    Returns dict with grid, mean, lo, hi, n_events, n_trials."""
    grid = np.arange(window[0], window[1] + 1e-9, GRID_DT)
    per_trial_curves = []
    n_events = 0
    for row in rows:
        ev = row[key_times]
        if ev.size == 0:
            continue
        sig = row["kin"][sig_key]
        _, M = r2.peri_event_matrix(sig, row["kin"]["head_t"], ev, window=window, grid_dt=GRID_DT)
        with np.errstate(all="ignore"):
            tc = np.nanmean(M, axis=0)
        if np.any(np.isfinite(tc)):
            per_trial_curves.append(tc)
            n_events += ev.size
    if not per_trial_curves:
        return {"grid": grid, "mean": np.full(grid.size, np.nan),
                "lo": np.full(grid.size, np.nan), "hi": np.full(grid.size, np.nan),
                "n_events": 0, "n_trials": 0}
    C = np.vstack(per_trial_curves)
    with np.errstate(all="ignore"):
        mean = np.nanmean(C, axis=0)
    rng = np.random.default_rng(seed)
    nt = C.shape[0]
    boots = np.empty((N_BOOT, grid.size))
    for i in range(N_BOOT):
        samp = C[rng.integers(0, nt, nt)]
        with np.errstate(all="ignore"):
            boots[i] = np.nanmean(samp, axis=0)
    lo = np.nanpercentile(boots, 2.5, axis=0)
    hi = np.nanpercentile(boots, 97.5, axis=0)
    return {"grid": grid, "mean": mean, "lo": lo, "hi": hi,
            "n_events": int(n_events), "n_trials": int(nt)}


def _null_peri_curve(rows, seed=SEED):
    """Matched-count random-time NULL onset-aligned eth_bs curve (H1 band). For each
    trial with >=1 bout, draw n_bout random times, build one null curve = mean over
    those draws averaged over a modest number of resamples, then trial-bootstrap."""
    grid = np.arange(PERI_WIN[0], PERI_WIN[1] + 1e-9, GRID_DT)
    per_trial_curves = []
    rng = np.random.default_rng(seed)
    for row in rows:
        n_b = row["bout_onset_times"].size
        if n_b == 0:
            continue
        ht = row["kin"]["head_t"]; sig = row["kin"]["eth_bs_h"]
        if ht.size < 2:
            continue
        lo_t, hi_t = ht[0], ht[-1]
        # 200 null draws to stabilize the trial's null curve (bounded)
        n_draw = 200
        rt = rng.uniform(lo_t, hi_t, size=n_draw * n_b)
        _, M = r2.peri_event_matrix(sig, ht, rt, window=PERI_WIN, grid_dt=GRID_DT)
        with np.errstate(all="ignore"):
            tc = np.nanmean(M, axis=0)
        if np.any(np.isfinite(tc)):
            per_trial_curves.append(tc)
    if not per_trial_curves:
        return {"grid": grid, "mean": np.full(grid.size, np.nan),
                "lo": np.full(grid.size, np.nan), "hi": np.full(grid.size, np.nan),
                "n_trials": 0}
    C = np.vstack(per_trial_curves)
    with np.errstate(all="ignore"):
        mean = np.nanmean(C, axis=0)
    rng2 = np.random.default_rng(seed + 1)
    nt = C.shape[0]
    boots = np.empty((N_BOOT, grid.size))
    for i in range(N_BOOT):
        samp = C[rng2.integers(0, nt, nt)]
        with np.errstate(all="ignore"):
            boots[i] = np.nanmean(samp, axis=0)
    return {"grid": grid, "mean": mean,
            "lo": np.nanpercentile(boots, 2.5, axis=0),
            "hi": np.nanpercentile(boots, 97.5, axis=0), "n_trials": int(nt)}


# ============================================================ main
def _pass1_thresholds(kins):
    v_com_pool = np.concatenate([k["v_com"][np.isfinite(k["v_com"])] for k in kins if k])
    omega_pool = np.concatenate([k["omega"][np.isfinite(k["omega"])] for k in kins if k])
    v_pause = float(np.percentile(v_com_pool, r2.V_PAUSE_PCT))
    omega_min = float(np.percentile(omega_pool, r2.OMEGA_PCT))
    return v_pause, omega_min


def _pooled_median_rate(rows):
    rates = [r["bout_rate"] for r in rows if r["in_pooled"] and np.isfinite(r["bout_rate"])]
    return float(np.median(rates)) if rates else np.nan


def main(n_slice=None):
    _setup_logging()
    t0 = time.time()
    logger.info("build_bouts start seed=%d version=%s slice=%s", SEED, r2.VERSION, n_slice)

    np.random.seed(SEED)
    trials, meta = pc.load_trials()
    logger.info("loaded %d trials (schema %s, Fs %.1f)", len(trials), meta["schema_version"], meta["Fs"])

    if n_slice:
        trials = trials[:n_slice]
        logger.info("SLICE mode: %d trials, no saves", len(trials))

    Qh = r2.pooled_dejump_Q(trials, "head")
    Qb = r2.pooled_dejump_Q(trials, "body")
    logger.info("dejump Q head=%.3f body=%.3f", Qh, Qb)

    # ---- PASS 1
    kins = []
    for tr in trials:
        try:
            kins.append(_trial_kinematics(tr, Qh, Qb))
        except Exception as e:
            logger.warning("PASS1 skip %s: %s", tr.get("file_name", "?"), e)
            kins.append(None)

    v_pause, omega_min = _pass1_thresholds(kins)
    logger.info("v_pause(25pct)=%.4f px/s  omega_min(90pct)=%.4f deg/s", v_pause, omega_min)

    # slice self-check
    if n_slice:
        ok = 0
        for k in kins:
            if k is None:
                continue
            assert np.nanmedian(k["v_com"]) > 0, "v_com not sane"
            om = k["omega"][np.isfinite(k["omega"])]
            assert om.size and np.nanmedian(om) > 0, "omega not sane"
            ok += 1
        logger.info("slice kinematics sane on %d trials", ok)

    # ---- PASS 2 with D6 gate loop
    bout_params = {"tau_pause": r2.TAU_PAUSE, "dphi_min": r2.DPHI_MIN, "t_merge": r2.T_MERGE}
    omega_pct = r2.OMEGA_PCT
    omega_pool = np.concatenate([k["omega"][np.isfinite(k["omega"])] for k in kins if k])
    tighten_path = []
    rng_master = np.random.default_rng(SEED)

    def _run_pass2(bp, om_min):
        rows = []
        for ti, (tr, kin) in enumerate(zip(trials, kins)):
            if kin is None:
                logger.warning("PASS2 skip trial %d %s: no kinematics", ti, tr.get("file_name", "?"))
                continue
            end_loc = r2.group_of(tr["file_name"])
            in_pooled = end_loc in POOLED_GROUPS
            try:
                seed_i = SEED + ti * 101 + 1
                m = _detect_and_measure(kin, bp, v_pause, om_min, end_loc,
                                        np.random.default_rng(seed_i))
            except Exception as e:
                logger.warning("PASS2 skip trial %d %s: %s", ti, tr.get("file_name", "?"), e)
                continue
            m.update({"trial_index": ti, "file_name": tr["file_name"],
                      "end_loc": end_loc, "in_pooled": in_pooled, "kin": kin,
                      "bout_onset_times": m["onset_times"]})
            rows.append(m)
        return rows

    rows = _run_pass2(bout_params, omega_min)
    achieved = _pooled_median_rate(rows)
    logger.info("D6: pooled median bout rate = %.5f /s (params tau=%.2f dphi=%.1f omega_pct=%.1f omega_min=%.2f)",
                achieved, bout_params["tau_pause"], bout_params["dphi_min"], omega_pct, omega_min)
    tighten_path.append({"omega_pct": omega_pct, "dphi_min": bout_params["dphi_min"],
                         "tau_pause": bout_params["tau_pause"], "omega_min": omega_min,
                         "achieved_rate": achieved})

    # tighten only if > trigger (expected: PASSES at defaults, no tightening)
    guard = 0
    while np.isfinite(achieved) and achieved > D6_TIGHTEN_TRIGGER and guard < 8:
        guard += 1
        bout_params["dphi_min"] += 20.0
        omega_pct = min(99.0, omega_pct + 2.0)
        bout_params["tau_pause"] += 0.05
        omega_min = float(np.percentile(omega_pool, omega_pct))
        logger.info("D6 TIGHTEN step %d -> dphi=%.1f omega_pct=%.1f tau=%.2f omega_min=%.2f",
                    guard, bout_params["dphi_min"], omega_pct, bout_params["tau_pause"], omega_min)
        rows = _run_pass2(bout_params, omega_min)
        achieved = _pooled_median_rate(rows)
        tighten_path.append({"omega_pct": omega_pct, "dphi_min": bout_params["dphi_min"],
                             "tau_pause": bout_params["tau_pause"], "omega_min": omega_min,
                             "achieved_rate": achieved})
        logger.info("D6 after tighten: pooled median rate = %.5f /s", achieved)

    d6_tightened = guard > 0
    logger.info("D6 FINAL: rate=%.5f /s tightened=%s params=%s omega_min=%.3f",
                achieved, d6_tightened, bout_params, omega_min)

    # slice-mode bout sanity
    if n_slice:
        n_bouts_total = sum(r["bout_count"] for r in rows)
        logger.info("slice: %d bouts across %d trials; in_odor dtype ok=%s",
                    n_bouts_total,
                    len(rows),
                    all(r["in_odor"].dtype == bool for r in rows if r["in_odor"].size))
        for r in rows:
            if r["in_odor"].size:
                assert r["in_odor"].dtype == bool
        logger.info("SLICE self-check PASS; exiting without save")
        return

    pooled_rows = [r for r in rows if r["in_pooled"]]
    another_rows = [r for r in rows if r["end_loc"] == "anotherLoc"]

    # ---------------------------------------------------- STATS
    stats_out = _compute_stats(pooled_rows, another_rows, rows, v_pause, omega_min,
                               bout_params, omega_pct, kins, achieved, d6_tightened,
                               tighten_path)

    # ---------------------------------------------------- figure curves
    fig_curves = _figure_curves(pooled_rows)
    stats_out["figure_curves_meta"] = {
        "F2A_eth": {"n_events": fig_curves["F2A_eth"]["n_events"],
                    "n_trials": fig_curves["F2A_eth"]["n_trials"]},
        "F2A_null_trials": fig_curves["F2A_null"]["n_trials"],
        "F2A_incidental": {"n_events": fig_curves["F2A_inc"]["n_events"],
                           "n_trials": fig_curves["F2A_inc"]["n_trials"]},
    }

    # example trial (most bouts among pooled) -- D12
    ex = max(pooled_rows, key=lambda r: r["bout_count"]) if pooled_rows else None
    if ex is not None:
        stats_out["deliverable_A"]["example_trial"] = {
            "file_name": ex["file_name"], "trial_index": ex["trial_index"],
            "bout_count": ex["bout_count"], "bout_rate": ex["bout_rate"]}

    # ---------------------------------------------------- SAVE
    _save_h5(rows, v_pause, omega_min, bout_params, achieved, fig_curves, kins)
    _save_bouts_json(rows)
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats_out, f, indent=2, default=_json_default)
    logger.info("wrote %s", STATS_JSON)

    logger.info("build_bouts done in %.1fs", time.time() - t0)
    _print_summary(stats_out, ex)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(str(type(o)))


# ============================================================ stats assembly
def _compute_stats(pooled, another, allrows, v_pause, omega_min, bp, omega_pct,
                   kins, achieved, d6_tightened, tighten_path):
    ge1 = [r for r in pooled if r["bout_count"] >= 1]
    counts = np.array([r["bout_count"] for r in pooled], float)
    rates = np.array([r["bout_rate"] for r in pooled if np.isfinite(r["bout_rate"])], float)

    head_rm = np.nanmean([k["head_removed"] for k in kins if k])
    body_rm = np.nanmean([k["body_removed"] for k in kins if k])

    n_bouts_pooled = int(sum(r["bout_count"] for r in pooled))
    n_inc_pooled = int(sum(r["n_incidental"] for r in pooled))

    meta = {
        "seed": SEED, "VERSION": r2.VERSION, "created_utc": _utc_now(),
        "v_pause_px_s": v_pause, "omega_min_deg_s": omega_min, "omega_pct": omega_pct,
        "final_bout_params": {"tau_pause": bp["tau_pause"], "dphi_min": bp["dphi_min"],
                              "t_merge": bp["t_merge"], "v_pause_pct": r2.V_PAUSE_PCT,
                              "omega_pct": omega_pct},
        "dejump_removed_frac": {"head": float(head_rm), "body": float(body_rm)},
        "v1_baseline_rate": V1_BASELINE_RATE,
        "n_boot": N_BOOT, "n_perm": N_PERM, "odor_cutoff": r2.ODOR_CUTOFF,
        "d6_tightened": bool(d6_tightened), "d6_tighten_trigger": D6_TIGHTEN_TRIGGER,
        "d6_tighten_path": tighten_path,
        "n_pooled_trials": len(pooled), "n_anotherLoc_trials": len(another),
    }

    # ------- Deliverable A
    rate_mean, rate_lo, rate_hi = _trial_bootstrap_ci(rates)
    bout_vcom = _median([r["m_bout_v_com"] for r in ge1])
    inc_vcom = _median([r["m_inc_v_com"] for r in ge1 if np.isfinite(r["m_inc_v_com"])])
    bout_exc = _median([r["m_bout_excursion"] for r in ge1])
    inc_exc_all = _median([r["m_inc_peak_omega"] for r in ge1])  # incidental has no excursion; use peak omega only
    bout_pom = _median([r["m_bout_peak_omega"] for r in ge1])
    inc_pom = _median([r["m_inc_peak_omega"] for r in ge1 if np.isfinite(r["m_inc_peak_omega"])])

    # trial-level selectivity comparisons (bouts vs incidental), over trials with both
    def _paired(a_key, b_key):
        A, B = [], []
        for r in ge1:
            if np.isfinite(r[a_key]) and np.isfinite(r[b_key]):
                A.append(r[a_key]); B.append(r[b_key])
        return np.array(A), np.array(B)

    va, vb = _paired("m_bout_v_com", "m_inc_v_com")
    s_vcom_stat, s_vcom_p, s_vcom_n = _wilcoxon_greater(vb - va)  # incidental > bout (v_com)
    pa, pb = _paired("m_bout_peak_omega", "m_inc_peak_omega")
    s_pom_stat, s_pom_p, s_pom_n = _wilcoxon_greater(pa - pb)     # bout >= incidental (peak omega)

    deliverable_A = {
        "rarity": {
            "pooled_median_bout_rate_per_s": _median(rates),
            "bout_rate_mean_trialboot_ci": [rate_mean, rate_lo, rate_hi],
            "count_distribution": {"min": int(np.min(counts)) if counts.size else 0,
                                    "median": float(np.median(counts)) if counts.size else 0.0,
                                    "max": int(np.max(counts)) if counts.size else 0},
            "frac_trials_ge1_bout": float(np.mean(counts >= 1)) if counts.size else 0.0,
            "frac_trials_0_bout": float(np.mean(counts == 0)) if counts.size else 0.0,
            "v1_baseline_rate_per_s": V1_BASELINE_RATE,
            "fold_rarer_than_v1": (V1_BASELINE_RATE / _median(rates)) if _median(rates) > 0 else np.inf,
            "achieved_pooled_median_rate_per_s": achieved,
            "d6_gate_passes": bool(achieved <= D6_TIGHTEN_TRIGGER),
        },
        "selectivity": {
            "note_low_com_definitional": "Bouts require a locomotor pause; low v_com during bouts is DEFINITIONAL, not a result.",
            "median_v_com_bouts": bout_vcom, "median_v_com_incidental": inc_vcom,
            "median_excursion_bouts_deg": bout_exc,
            "median_peak_omega_bouts_deg_s": bout_pom, "median_peak_omega_incidental_deg_s": inc_pom,
            "trial_wilcoxon_incidental_gt_bout_vcom": {"stat": s_vcom_stat, "p": s_vcom_p, "n_trials": s_vcom_n},
            "trial_wilcoxon_bout_ge_incidental_peakomega": {"stat": s_pom_stat, "p": s_pom_p, "n_trials": s_pom_n},
        },
        "n_bouts_pooled": n_bouts_pooled, "n_incidental_pooled": n_inc_pooled,
        "n_contributing_trials": len(ge1),
    }

    # ------- amplitude check (before odor claims)
    peri_vals = np.array([r["m_peri_odor"] for r in ge1 if np.isfinite(r["m_peri_odor"])], float)
    all_bout_peri = np.concatenate([r["peri_odor"][np.isfinite(r["peri_odor"])] for r in ge1]) if ge1 else np.array([])
    amplitude = {
        "peri_bout_eth_median": _median(peri_vals),
        "eth_range_ref": 0.14, "eth_floor_ref": 4e-4,
        "frac_bouts_peri_gt_0p01": float(np.mean(all_bout_peri > 0.01)) if all_bout_peri.size else np.nan,
        "above_floor": bool(_median(peri_vals) > 4e-4) if np.isfinite(_median(peri_vals)) else False,
    }

    # ------- H1
    # (a) bout peri-odor vs matched null (per-trial)
    diff_h1 = np.array([r["m_peri_odor"] - r["m_null_peri"] for r in ge1
                        if np.isfinite(r["m_peri_odor"]) and np.isfinite(r["m_null_peri"])])
    h1a_stat, h1a_p, h1a_n = _wilcoxon_greater(diff_h1)
    obs_h1 = _median([r["m_peri_odor"] for r in ge1 if np.isfinite(r["m_peri_odor"]) and np.isfinite(r["m_null_peri"])])
    null_h1 = _median([r["m_null_peri"] for r in ge1 if np.isfinite(r["m_peri_odor"]) and np.isfinite(r["m_null_peri"])])
    obs_m, obs_lo, obs_hi = _trial_bootstrap_ci([r["m_peri_odor"] for r in ge1])
    # (b) specificity bouts vs incidental
    sb, si = _paired("m_peri_odor", "m_inc_peri_odor")
    h1b_stat, h1b_p, h1b_n = _wilcoxon_greater(sb - si)

    H1 = {
        "lead_magnitude": {"median_peri_bout_eth": obs_h1, "median_null_eth": null_h1,
                           "peri_bout_mean_trialboot_ci": [obs_m, obs_lo, obs_hi],
                           "delta_median_obs_minus_null": (obs_h1 - null_h1) if (np.isfinite(obs_h1) and np.isfinite(null_h1)) else np.nan},
        "a_bout_vs_null": {"wilcoxon_stat": h1a_stat, "p_greater": h1a_p, "n_trials": h1a_n},
        "b_bout_vs_incidental": {"wilcoxon_stat": h1b_stat, "p_greater": h1b_p, "n_trials": h1b_n,
                                 "median_bout_peri": _median(sb.tolist()), "median_incidental_peri": _median(si.tolist())},
        "amplitude_check": amplitude,
        "accept_H1": bool(np.isfinite(h1a_p) and h1a_p < 0.05 and np.isfinite(h1b_p) and h1b_p < 0.05),
    }

    # ------- H2
    diff_pre_base = np.array([r["m_pre_onset"] - r["trial_baseline"] for r in ge1
                              if np.isfinite(r["m_pre_onset"]) and np.isfinite(r["trial_baseline"])])
    h2b_stat, h2b_p, h2b_n = _wilcoxon_greater(diff_pre_base)
    diff_pre_null = np.array([r["m_pre_onset"] - r["m_null_pre"] for r in ge1
                              if np.isfinite(r["m_pre_onset"]) and np.isfinite(r["m_null_pre"])])
    h2n_stat, h2n_p, h2n_n = _wilcoxon_greater(diff_pre_null)
    slopes = np.array([r["m_onset_slope"] for r in ge1 if np.isfinite(r["m_onset_slope"])])
    h2s_stat, h2s_p, h2s_n = _wilcoxon_greater(slopes)

    # control: incidental pre-onset vs trial baseline (should NOT exceed if H2 specific)
    inc_ge1 = [r for r in pooled if r["n_incidental"] >= 1]
    diff_inc_pre = np.array([r["m_inc_pre_onset"] - r["trial_baseline"] for r in inc_ge1
                             if np.isfinite(r["m_inc_pre_onset"]) and np.isfinite(r["trial_baseline"])])
    h2c_stat, h2c_p, h2c_n = _wilcoxon_greater(diff_inc_pre)

    # spatial control: split bouts by in_odor True/False -> pre-onset odor within each (pooled per-bout medians)
    pre_in, pre_out = [], []
    for r in ge1:
        io = r["in_odor"]; pre = r["pre_onset"]
        m = min(io.size, pre.size)
        for j in range(m):
            if np.isfinite(pre[j]):
                (pre_in if io[j] else pre_out).append(pre[j])

    H2 = {
        "direction_first": {"median_pre_onset_eth": _median([r["m_pre_onset"] for r in ge1]),
                            "median_trial_baseline": _median([r["trial_baseline"] for r in ge1]),
                            "median_onset_slope_au_per_s": _median(slopes.tolist())},
        "pre_vs_baseline": {"wilcoxon_stat": h2b_stat, "p_greater": h2b_p, "n_trials": h2b_n},
        "pre_vs_null": {"wilcoxon_stat": h2n_stat, "p_greater": h2n_p, "n_trials": h2n_n},
        "onset_slope_gt0": {"wilcoxon_stat": h2s_stat, "p_greater": h2s_p, "n_trials": h2s_n,
                            "median_slope": _median(slopes.tolist())},
        "control_incidental_pre_vs_baseline": {"wilcoxon_stat": h2c_stat, "p_greater": h2c_p, "n_trials": h2c_n,
                                               "interpretation": "H2 is specific if incidental does NOT show pre>baseline"},
        "control_spatial_split": {"median_pre_onset_in_odor": _median(pre_in),
                                  "median_pre_onset_out_odor": _median(pre_out),
                                  "n_bouts_in_odor": len(pre_in), "n_bouts_out_odor": len(pre_out)},
        "accept_H2": bool(np.isfinite(h2b_p) and h2b_p < 0.05 and np.isfinite(h2n_p) and h2n_p < 0.05
                          and np.isfinite(h2s_p) and h2s_p < 0.05),
    }

    # ------- H3
    diff_bout_occ = np.array([r["f_bout"] - r["f_occ"] for r in ge1
                              if np.isfinite(r["f_bout"]) and np.isfinite(r["f_occ"])])
    h3o_stat, h3o_p, h3o_n = _wilcoxon_greater(diff_bout_occ)
    diff_bout_null = np.array([r["f_bout"] - r["f_bout_null_mean"] for r in ge1
                               if np.isfinite(r["f_bout"]) and np.isfinite(r["f_bout_null_mean"])])
    h3n_stat, h3n_p, h3n_n = _wilcoxon_greater(diff_bout_null)
    frac_enriched = float(np.mean(diff_bout_occ > 0)) if diff_bout_occ.size else np.nan

    H3 = {
        "direction_first": {"median_f_bout": _median([r["f_bout"] for r in ge1]),
                            "median_f_occ": _median([r["f_occ"] for r in ge1]),
                            "median_f_bout_minus_null": _median(diff_bout_null.tolist())},
        "f_bout_gt_f_occ": {"wilcoxon_stat": h3o_stat, "p_greater": h3o_p, "n_trials": h3o_n},
        "f_bout_gt_null": {"wilcoxon_stat": h3n_stat, "p_greater": h3n_p, "n_trials": h3n_n},
        "frac_trials_enriched": frac_enriched,
        "odor_cutoff": r2.ODOR_CUTOFF,
        "amplitude_above_floor": amplitude["above_floor"],
        "accept_H3": bool(np.isfinite(h3o_p) and h3o_p < 0.05 and np.isfinite(h3n_p) and h3n_p < 0.05),
    }

    return {"meta": meta, "deliverable_A": deliverable_A, "H1": H1, "H2": H2, "H3": H3}


def _figure_curves(pooled):
    ge1 = [r for r in pooled if r["bout_count"] >= 1]
    inc1 = [r for r in pooled if r["inc_times"].size >= 1]
    F2A_eth = _peri_curve(ge1, "onset_times", "eth_bs_h")
    F2A_null = _null_peri_curve(ge1)
    F2A_inc = _peri_curve(inc1, "inc_times", "eth_bs_h")
    F2B_vcom = _peri_curve(ge1, "onset_times", "v_com")
    F2B_omega = _peri_curve(ge1, "onset_times", "omega")

    # F1 arrays
    rate_arr = np.array([r["bout_rate"] for r in pooled if np.isfinite(r["bout_rate"])], float)
    bout_vcom = np.concatenate([r["bout_v_com"][np.isfinite(r["bout_v_com"])] for r in ge1]) if ge1 else np.array([])
    bout_exc = np.concatenate([r["bout_excursion"][np.isfinite(r["bout_excursion"])] for r in ge1]) if ge1 else np.array([])
    bout_pom = np.concatenate([r["bout_peak_omega"][np.isfinite(r["bout_peak_omega"])] for r in ge1]) if ge1 else np.array([])
    inc_vcom = np.concatenate([r["inc_v_com"][np.isfinite(r["inc_v_com"])] for r in inc1]) if inc1 else np.array([])
    inc_pom = np.concatenate([r["inc_peak_omega"][np.isfinite(r["inc_peak_omega"])] for r in inc1]) if inc1 else np.array([])

    return {"F2A_eth": F2A_eth, "F2A_null": F2A_null, "F2A_inc": F2A_inc,
            "F2B_vcom": F2B_vcom, "F2B_omega": F2B_omega,
            "F1_rate": rate_arr, "F1_bout_vcom": bout_vcom, "F1_bout_exc": bout_exc,
            "F1_bout_pom": bout_pom, "F1_inc_vcom": inc_vcom, "F1_inc_pom": inc_pom}


# ============================================================ HDF5 save
def _ds(g, name, arr):
    arr = np.asarray(arr)
    kw = {}
    if arr.dtype.kind in "fiu" and arr.size >= 256:
        kw = {"compression": "gzip", "compression_opts": 4, "shuffle": True}
    g.create_dataset(name, data=arr, **kw)


def _save_h5(rows, v_pause, omega_min, bp, achieved, fig_curves, kins):
    import h5py
    tmp = H5_PATH + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with h5py.File(tmp, "w") as f:
        f.attrs["seed"] = SEED
        f.attrs["VERSION"] = r2.VERSION
        f.attrs["v_pause_px_s"] = v_pause
        f.attrs["omega_min_deg_s"] = omega_min
        f.attrs["tau_pause"] = bp["tau_pause"]
        f.attrs["dphi_min"] = bp["dphi_min"]
        f.attrs["t_merge"] = bp["t_merge"]
        f.attrs["odor_cutoff"] = r2.ODOR_CUTOFF
        f.attrs["achieved_pooled_median_rate_per_s"] = achieved
        f.attrs["source_aggregate"] = AGG_PATH
        f.attrs["source_odor_fields"] = ODOR_FIELDS_H5
        f.attrs["created_utc"] = _utc_now()
        f.attrs["README"] = ("Selective sampling-bout objects. /bouts = per-bout table; "
                             "/trials/<idx> = per-trial arrays for figures; "
                             "/figure_curves = precomputed onset-aligned curves. seed 1234, trial-level inference.")

        # /bouts table
        bt = f.create_group("bouts")
        cols = {"trial_index": [], "file_name": [], "end_loc": [], "in_pooled": [],
                "onset_time": [], "peak_time": [], "dur_s": [], "peak_omega": [],
                "excursion_deg": [], "v_com_during": [], "in_odor": [],
                "peri_odor_mean": [], "pre_onset_odor": [], "onset_slope": []}
        for r in rows:
            nb = r["bout_count"]
            for j in range(nb):
                b = r["bouts"][j]
                cols["trial_index"].append(r["trial_index"])
                cols["file_name"].append(r["file_name"])
                cols["end_loc"].append(r["end_loc"])
                cols["in_pooled"].append(r["in_pooled"])
                cols["onset_time"].append(float(r["onset_times"][j]))
                cols["peak_time"].append(float(r["peak_times"][j]))
                cols["dur_s"].append(float(b["dur_s"]))
                cols["peak_omega"].append(float(b["peak_omega"]))
                cols["excursion_deg"].append(float(b["excursion_deg"]))
                cols["v_com_during"].append(float(b["v_com_during"]))
                cols["in_odor"].append(bool(r["in_odor"][j]))
                cols["peri_odor_mean"].append(float(r["peri_odor"][j]) if j < r["peri_odor"].size else np.nan)
                cols["pre_onset_odor"].append(float(r["pre_onset"][j]) if j < r["pre_onset"].size else np.nan)
                cols["onset_slope"].append(float(r["onset_slope"][j]) if j < r["onset_slope"].size else np.nan)
        strdt = h5py.string_dtype("utf-8")
        for k, v in cols.items():
            if k in ("file_name", "end_loc"):
                bt.create_dataset(k, data=np.array(v, dtype=object), dtype=strdt)
            elif k == "in_pooled" or k == "in_odor":
                bt.create_dataset(k, data=np.array(v, bool))
            elif k == "trial_index":
                _ds(bt, k, np.array(v, np.int32))
            else:
                _ds(bt, k, np.array(v, float))

        # /trials/<idx>
        tg = f.create_group("trials")
        for r in rows:
            kin = r["kin"]
            g = tg.create_group(f"{r['trial_index']:03d}")
            _ds(g, "head_c", kin["head_c"].astype(np.float32))
            _ds(g, "body_h", kin["body_h"].astype(np.float32))
            _ds(g, "head_t", kin["head_t"].astype(float))
            _ds(g, "v_com", kin["v_com"].astype(np.float32))
            _ds(g, "omega", kin["omega"].astype(np.float32))
            _ds(g, "phi", kin["phi"].astype(np.float32))
            _ds(g, "eth_bs_h", kin["eth_bs_h"].astype(np.float32))
            _ds(g, "bout_onset_times", r["onset_times"].astype(float))
            _ds(g, "bout_peak_times", r["peak_times"].astype(float))
            _ds(g, "incidental_times", r["inc_times"].astype(float))
            g.attrs["file_name"] = r["file_name"]
            g.attrs["end_loc"] = r["end_loc"]
            g.attrs["in_pooled"] = r["in_pooled"]
            g.attrs["bout_count"] = r["bout_count"]
            g.attrs["bout_rate"] = float(r["bout_rate"]) if np.isfinite(r["bout_rate"]) else np.nan
            g.attrs["n_incidental"] = r["n_incidental"]
            g.attrs["f_bout"] = float(r["f_bout"]) if np.isfinite(r["f_bout"]) else np.nan
            g.attrs["f_occ"] = float(r["f_occ"]) if np.isfinite(r["f_occ"]) else np.nan
            g.attrs["endpoint"] = kin["endpoint"].astype(float)

        # /figure_curves
        fc = f.create_group("figure_curves")
        for name, cur in fig_curves.items():
            if isinstance(cur, dict):
                sub = fc.create_group(name)
                for kk, vv in cur.items():
                    if isinstance(vv, np.ndarray):
                        _ds(sub, kk, vv.astype(float))
                    else:
                        sub.attrs[kk] = vv
            else:
                _ds(fc, name, np.asarray(cur, float))

        f.attrs["build_complete"] = 1  # LAST
    os.replace(tmp, H5_PATH)
    logger.info("wrote %s (build_complete=1)", H5_PATH)


def _save_bouts_json(rows):
    per_bout = []
    per_trial = []
    for r in rows:
        per_trial.append({
            "trial_index": r["trial_index"], "file_name": r["file_name"],
            "end_loc": r["end_loc"], "in_pooled": r["in_pooled"],
            "bout_count": r["bout_count"],
            "bout_rate": float(r["bout_rate"]) if np.isfinite(r["bout_rate"]) else None,
            "n_incidental": r["n_incidental"],
            "f_bout": float(r["f_bout"]) if np.isfinite(r["f_bout"]) else None,
            "f_occ": float(r["f_occ"]) if np.isfinite(r["f_occ"]) else None,
            "m_pre_onset": float(r["m_pre_onset"]) if np.isfinite(r["m_pre_onset"]) else None,
            "m_peri_odor": float(r["m_peri_odor"]) if np.isfinite(r["m_peri_odor"]) else None,
            "trial_baseline": float(r["trial_baseline"]) if np.isfinite(r["trial_baseline"]) else None,
        })
        for j in range(r["bout_count"]):
            b = r["bouts"][j]
            per_bout.append({
                "trial_index": r["trial_index"], "file_name": r["file_name"],
                "end_loc": r["end_loc"], "in_pooled": r["in_pooled"],
                "onset_time": float(r["onset_times"][j]), "peak_time": float(r["peak_times"][j]),
                "dur_s": float(b["dur_s"]), "peak_omega": float(b["peak_omega"]),
                "excursion_deg": float(b["excursion_deg"]), "v_com_during": float(b["v_com_during"]),
                "in_odor": bool(r["in_odor"][j]),
                "peri_odor_mean": float(r["peri_odor"][j]) if j < r["peri_odor"].size and np.isfinite(r["peri_odor"][j]) else None,
                "pre_onset_odor": float(r["pre_onset"][j]) if j < r["pre_onset"].size and np.isfinite(r["pre_onset"][j]) else None,
                "onset_slope": float(r["onset_slope"][j]) if j < r["onset_slope"].size and np.isfinite(r["onset_slope"][j]) else None,
            })
    with open(BOUTS_JSON, "w", encoding="utf-8") as f:
        json.dump({"per_bout": per_bout, "per_trial": per_trial}, f, indent=2, default=_json_default)
    logger.info("wrote %s (%d bouts, %d trials)", BOUTS_JSON, len(per_bout), len(per_trial))


def _print_summary(s, ex):
    dA = s["deliverable_A"]; r = dA["rarity"]
    logger.info("=== SUMMARY ===")
    logger.info("v_pause=%.3f px/s  omega_min=%.3f deg/s", s["meta"]["v_pause_px_s"], s["meta"]["omega_min_deg_s"])
    logger.info("pooled median rate=%.5f/s  count med=%.0f max=%d  %%>=1 bout=%.1f%%  D6 pass=%s",
                r["pooled_median_bout_rate_per_s"], r["count_distribution"]["median"],
                r["count_distribution"]["max"], 100 * r["frac_trials_ge1_bout"], r["d6_gate_passes"])
    logger.info("H1 bout-vs-null p=%.4g  H1 bout-vs-inc p=%.4g  above_floor=%s",
                s["H1"]["a_bout_vs_null"]["p_greater"], s["H1"]["b_bout_vs_incidental"]["p_greater"],
                s["H1"]["amplitude_check"]["above_floor"])
    logger.info("H2 pre>baseline p=%.4g  slope>0 p=%.4g", s["H2"]["pre_vs_baseline"]["p_greater"],
                s["H2"]["onset_slope_gt0"]["p_greater"])
    logger.info("H3 f_bout>f_occ p=%.4g  frac enriched=%.2f", s["H3"]["f_bout_gt_f_occ"]["p_greater"],
                s["H3"]["frac_trials_enriched"])
    if ex:
        logger.info("example trial=%s count=%d", ex["file_name"], ex["bout_count"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", type=int, default=None)
    args = ap.parse_args()
    main(n_slice=args.slice)
