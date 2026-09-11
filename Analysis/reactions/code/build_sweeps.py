r"""build_sweeps.py -- Nose-Sweeps data-analyst pipeline (H1/H2/H3).

Computes per-frame arrays, per-trial + per-sweep metrics, and ALL inferential
statistics for the three pre-registered hypotheses, then SAVES them. Builds NO
figures/reports (that is the figure/report agents' job).

Follows PLAN.md / plan.json (decisions D1-D13) exactly. Seed = 1234 everywhere.
Imports reactions_common (single source of truth); does NOT reimplement primitives.

Interpreter: run with "$AR_PY".
    "$AR_PY" code/build_sweeps.py
"""
from __future__ import annotations

import os
import sys
import json
import time
import logging
import datetime as _dt

import numpy as np

# --- paths ------------------------------------------------------------------
BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions"
CODE_DIR = os.path.join(BASE, "code")
DATA_DIR = os.path.join(BASE, "data")
LOG_DIR = os.path.join(BASE, "logs")
ACCESSOR_DIR = r"C:\Projects\Repos\Mouse Arena\DATA\code"
AGG_PATH = r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5"

for _d in (DATA_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if ACCESSOR_DIR not in sys.path:
    sys.path.insert(0, ACCESSOR_DIR)

import reactions_common as rc  # noqa: E402
from mouse_arena_aggregate_io import Aggregate  # noqa: E402

SEED = rc.SEED  # 1234
VERSION = rc.VERSION
ODOR_CUTOFF = rc.ODOR_CUTOFF

# windows / grid (D13)
PERI_WIN = (-1.0, 1.0)
PERI_GRID_DT = 0.05
ETH_SUM_WIN = (-0.5, 0.5)
H2_WIN = (-0.25, 0.25)
FALLBACK_R_PX = 100.0
FALLBACK_ETH_THR = 0.01

N_PERM = 2000
N_BOOT = 2000

POOLED_LOCS = {"Loc1", "Loc2", "Loc3", "Loc4", "Loc5", "Loc6"}

# --- logging ----------------------------------------------------------------
LOG_PATH = os.path.join(LOG_DIR, "build_sweeps.log")
logger = logging.getLogger("build_sweeps")
logger.setLevel(logging.DEBUG)
_fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout)
_sh.setLevel(logging.INFO)
_sh.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_sh)


def _utc():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
#  Self-check (small, BEFORE heavy compute)
# --------------------------------------------------------------------------- #
def self_check():
    """Fast sanity checks: library self-check + a couple of pipeline invariants."""
    rc._selfcheck()
    # peri_event_matrix sum over a window on a known signal
    t = np.arange(400) * 0.01
    sig = np.ones_like(t) * 2.0
    grid, M = rc.peri_event_matrix(sig, t, [2.0], window=ETH_SUM_WIN, grid_dt=PERI_GRID_DT)
    assert np.isfinite(M).all() and abs(np.nanmean(M) - 2.0) < 1e-9
    # in_odor returns a bool scalar-ish
    field = {"max": np.array([[0.05]]), "count": np.array([[5]]),
             "x_edges": np.array([0.0, 10.0]), "y_edges": np.array([0.0, 10.0])}
    v = bool(rc.is_in_odor(field, [5.0], [5.0])[0])
    assert v is True
    logger.info("self_check: PASS")


# --------------------------------------------------------------------------- #
#  Per-trial core computation (per-frame arrays)
# --------------------------------------------------------------------------- #
def compute_trial_frames(tr, Q_body, Q_head, v_floor):
    """Clean both tracks, put everything on the head clock, compute velocities,
    R, baseline-subtracted ethanol on head clock. Returns a dict or raises."""
    head = np.asarray(tr["head"], float)
    body = np.asarray(tr["body"], float)
    head_t = np.asarray(tr["head_time"], float)
    body_t = np.asarray(tr["body_time"], float)
    eth = np.asarray(tr["ethanol"], float)
    eth_t = np.asarray(tr["ethanol_time"], float)

    # clean both tracks independently (advancing-reference de-jump)
    _, nb_box_head, nb_dj_head = rc.pc.clean_counts(head, head_t, Q_head)
    _, nb_box_body, nb_dj_body = rc.pc.clean_counts(body, body_t, Q_body)
    h_idx, head_c, head_t_c = rc.clean_track(head, head_t, Q_head)
    b_idx, body_c, body_t_c = rc.clean_track(body, body_t, Q_body)
    if head_c.shape[0] < 10 or body_c.shape[0] < 2:
        raise ValueError(f"too few clean samples head={head_c.shape[0]} body={body_c.shape[0]}")

    # head clock: interpolate cleaned body onto cleaned head clock
    body_h = rc.interp_xy_to_head(head_t_c, body_t_c, body_c)

    dt = float(np.median(np.diff(head_t_c)))
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError(f"bad dt={dt}")

    v_nose = rc.speed_savgol(head_c, dt)
    v_com = rc.speed_savgol(body_h, dt)
    bframe = rc.speed_savgol(head_c - body_h, dt)

    R = v_nose / np.maximum(v_com, v_floor)

    binding_frac = float(np.mean(v_com < v_floor))

    # baseline-subtracted ethanol on sensor clock, then aligned to head clock
    eth_bs = rc.baseline_subtract_ethanol(eth, eth_t)
    eth_bs_h = rc.align_signal(head_t_c, eth_t, eth_bs)

    return {
        "head_c": head_c, "body_h": body_h, "head_t": head_t_c, "dt": dt,
        "v_nose": v_nose, "v_com": v_com, "bframe": bframe, "R": R,
        "eth_bs_h": eth_bs_h, "binding_frac": binding_frac,
        # de-jump-only counts (removed AMONG box-kept samples), matches probe/smell-test
        "n_body_dejump_removed": int(nb_box_body - nb_dj_body),
        "n_body_box_kept": int(nb_box_body),
        "n_head_dejump_removed": int(nb_box_head - nb_dj_head),
        "n_head_box_kept": int(nb_box_head),
    }


# --------------------------------------------------------------------------- #
#  PASS 1 -- collect pooled v_com for the global v_floor
# --------------------------------------------------------------------------- #
def pass1_v_floor(trials, Q_body, Q_head):
    """v_floor = 10th percentile of POOLED v_com (all 114 trials, all frames)."""
    pooled = []
    for tr in trials:
        try:
            head = np.asarray(tr["head"], float)
            body = np.asarray(tr["body"], float)
            head_t = np.asarray(tr["head_time"], float)
            body_t = np.asarray(tr["body_time"], float)
            _, head_c, head_t_c = rc.clean_track(head, head_t, Q_head)
            _, body_c, body_t_c = rc.clean_track(body, body_t, Q_body)
            if head_c.shape[0] < 10 or body_c.shape[0] < 2:
                continue
            body_h = rc.interp_xy_to_head(head_t_c, body_t_c, body_c)
            dt = float(np.median(np.diff(head_t_c)))
            if not np.isfinite(dt) or dt <= 0:
                continue
            vc = rc.speed_savgol(body_h, dt)
            pooled.append(vc[np.isfinite(vc)])
        except Exception as e:  # noqa: BLE001
            logger.warning("PASS1 skip %s: %s", tr.get("file_name", "?"), e)
            continue
    allv = np.concatenate(pooled)
    v_floor = float(np.percentile(allv, 10.0))
    logger.info("PASS1: pooled v_com n=%d, v_floor(10th pct)=%.4f px/s", allv.size, v_floor)
    return v_floor, allv


# --------------------------------------------------------------------------- #
#  PASS 2 -- per-trial metrics + sweeps
# --------------------------------------------------------------------------- #
def process_trial(tr, Q_body, Q_head, v_floor, odor_field_cache):
    """Full per-trial processing -> dict with frames, per-trial scalars, per-sweep rows."""
    fn = tr["file_name"]
    end_loc = rc.group_of(fn)
    in_pooled = end_loc in POOLED_LOCS

    F = compute_trial_frames(tr, Q_body, Q_head, v_floor)
    head_c, body_h = F["head_c"], F["body_h"]
    head_t, dt = F["head_t"], F["dt"]
    v_nose, v_com, bframe, R = F["v_nose"], F["v_com"], F["bframe"], F["R"]
    eth_bs_h = F["eth_bs_h"]

    Nh = head_c.shape[0]
    duration = float(head_t[-1] - head_t[0]) if Nh >= 2 else 0.0

    med_vnose = float(np.nanmedian(v_nose))
    med_vcom = float(np.nanmedian(v_com))

    # --- odor field for this trial ---
    field = odor_field_cache.get(end_loc, "MISS")
    if field == "MISS":
        field = rc.load_odor_field(end_loc)
        odor_field_cache[end_loc] = field
    endpoint = rc.endpoint_of(tr)

    def in_odor_fn(x, y, eth_at):
        """Return (bool, method). Primary: odor field; fallback: r<100px or eth>=thr."""
        if field is not None:
            return bool(rc.is_in_odor(field, [x], [y])[0]), "field"
        d = float(np.hypot(x - endpoint[0], y - endpoint[1]))
        e = float(eth_at) if np.isfinite(eth_at) else -np.inf
        return bool((d <= FALLBACK_R_PX) or (e >= FALLBACK_ETH_THR)), "fallback"

    # --- PRIMARY: R-detector sweeps ---
    pk_R = rc.detect_sweeps_R(R, head_t)
    pk_R = np.asarray(pk_R, int)
    sweep_count = int(pk_R.size)
    sweep_rate = float(sweep_count / duration) if duration > 0 else 0.0
    sweep_times_R = head_t[pk_R] if pk_R.size else np.array([], float)

    # --- numerator-only body-frame sweeps (for H2 circularity) ---
    pk_b = rc.detect_sweeps_bframe(bframe, head_t)
    pk_b = np.asarray(pk_b, int)
    sweep_times_bframe = head_t[pk_b] if pk_b.size else np.array([], float)

    # per-sweep records for the R-set
    sweeps = []
    fallback_used = False
    if pk_R.size:
        # summed & mean eth_bs over [-0.5,+0.5]s for each sweep (vectorized matrix)
        grid_e, Me = rc.peri_event_matrix(eth_bs_h, head_t, sweep_times_R,
                                          window=ETH_SUM_WIN, grid_dt=PERI_GRID_DT)
        for j, i in enumerate(pk_R):
            row = Me[j]
            summed_eth = float(np.nansum(row)) if np.isfinite(row).any() else np.nan
            mean_eth = float(np.nanmean(row)) if np.isfinite(row).any() else np.nan
            x, y = float(head_c[i, 0]), float(head_c[i, 1])
            eth_at = eth_bs_h[i]
            ino, method = in_odor_fn(x, y, eth_at)
            if method == "fallback":
                fallback_used = True
            sweeps.append({
                "peak_time": float(head_t[i]),
                "R": float(R[i]),
                "v_nose": float(v_nose[i]),
                "v_com": float(v_com[i]),
                "head_x": x, "head_y": y,
                "nose_driven": bool(v_nose[i] > med_vnose),
                "com_dropout": bool(v_com[i] < med_vcom),
                "summed_eth": summed_eth,
                "mean_eth": mean_eth,
                "in_odor": bool(ino),
            })

    # --- H3 per-trial: f_sweep, f_occ, permutation null ---
    # occupancy: in-odor fraction over ALL kept head frames
    if field is not None:
        occ_mask = rc.is_in_odor(field, head_c[:, 0], head_c[:, 1])
        f_occ = float(np.mean(occ_mask))
    else:
        d_all = np.hypot(head_c[:, 0] - endpoint[0], head_c[:, 1] - endpoint[1])
        occ_mask = (d_all <= FALLBACK_R_PX) | (np.nan_to_num(eth_bs_h, nan=-np.inf) >= FALLBACK_ETH_THR)
        f_occ = float(np.mean(occ_mask))
        fallback_used = True

    sweep_in_odor = np.array([s["in_odor"] for s in sweeps], bool)
    f_sweep = float(np.mean(sweep_in_odor)) if sweep_in_odor.size else np.nan

    # within-trial permutation null: draw n_sweeps random frame indices, in-odor frac
    h3_null_mean = np.nan
    h3_stat = np.nan
    if sweep_count > 0 and Nh > 0:
        rng = np.random.default_rng(SEED)
        # occ_mask is per-frame in-odor over kept frames; sample frames uniformly
        occ_int = occ_mask.astype(float)
        draws = rng.integers(0, Nh, size=(N_PERM, sweep_count))
        null_fracs = occ_int[draws].mean(axis=1)
        h3_null_mean = float(np.mean(null_fracs))
        h3_stat = float(f_sweep - h3_null_mean) if np.isfinite(f_sweep) else np.nan

    # --- H2 per-trial during-sweep v_com (R-set and bframe-set) ---
    def during_vcom(sweep_times):
        if sweep_times.size == 0:
            return np.nan
        _, Mv = rc.peri_event_matrix(v_com, head_t, sweep_times,
                                     window=H2_WIN, grid_dt=PERI_GRID_DT)
        vals = Mv[np.isfinite(Mv)]
        return float(np.mean(vals)) if vals.size else np.nan

    h2_during_Rset = during_vcom(sweep_times_R)
    h2_during_bframe = during_vcom(sweep_times_bframe)
    h2_baseline_vcom = med_vcom  # trial median v_com

    # window-edge baseline (+/-1s edges): mean v_com at the peri-window extremes
    def edge_baseline(sweep_times):
        if sweep_times.size == 0:
            return np.nan
        _, Mv = rc.peri_event_matrix(v_com, head_t, sweep_times,
                                     window=PERI_WIN, grid_dt=PERI_GRID_DT)
        # first and last grid columns = +-1s edges
        edges = np.concatenate([Mv[:, :1].ravel(), Mv[:, -1:].ravel()])
        edges = edges[np.isfinite(edges)]
        return float(np.mean(edges)) if edges.size else np.nan

    h2_edge_baseline_Rset = edge_baseline(sweep_times_R)

    # --- H1b per-trial observed peri-eth (mean over sweeps of mean eth in window) ---
    sweep_mean_eth = np.array([s["mean_eth"] for s in sweeps], float)
    h1b_observed = float(np.nanmean(sweep_mean_eth)) if sweep_mean_eth.size else np.nan

    # --- H1b per-trial null: matched-count random-time window mean eth ---
    h1b_null = np.nan
    if sweep_count > 0 and duration > 0:
        rng = np.random.default_rng(SEED)
        t0, t1 = float(head_t[0]), float(head_t[-1])
        rand_times = rng.uniform(t0, t1, size=(N_PERM, sweep_count))
        # For speed: build the peri matrix per perm draw is expensive; instead sample
        # the window-mean of eth at random times via interpolation on the grid.
        grid = np.arange(ETH_SUM_WIN[0], ETH_SUM_WIN[1] + 1e-9, PERI_GRID_DT)
        finite = np.isfinite(eth_bs_h)
        tt, ss = head_t[finite], eth_bs_h[finite]
        perm_means = np.empty(N_PERM, float)
        if tt.size >= 2:
            for p in range(N_PERM):
                q = rand_times[p][:, None] + grid[None, :]  # (n_sweeps, n_grid)
                vals = np.interp(q.ravel(), tt, ss, left=np.nan, right=np.nan)
                vals = vals.reshape(q.shape)
                # per random-event mean over window, then mean across events
                import warnings
                with np.errstate(invalid="ignore"), warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    ev_mean = np.nanmean(vals, axis=1)
                perm_means[p] = np.nanmean(ev_mean) if np.isfinite(ev_mean).any() else np.nan
            h1b_null = float(np.nanmean(perm_means))

    trial_out = {
        "file_name": fn, "end_loc": end_loc, "in_pooled": in_pooled,
        "duration": duration, "dt": dt, "n_frames": Nh,
        "sweep_count": sweep_count, "sweep_rate": sweep_rate,
        "sweep_count_bframe": int(pk_b.size),
        "sweep_rate_bframe": float(pk_b.size / duration) if duration > 0 else 0.0,
        "binding_frac": F["binding_frac"],
        "n_body_dejump_removed": F["n_body_dejump_removed"], "n_body_box_kept": F["n_body_box_kept"],
        "n_head_dejump_removed": F["n_head_dejump_removed"], "n_head_box_kept": F["n_head_box_kept"],
        "med_vnose": med_vnose, "med_vcom": med_vcom,
        "f_sweep": f_sweep, "f_occ": f_occ,
        "h3_null_mean": h3_null_mean, "h3_stat": h3_stat,
        "h2_during_vcom_Rset": h2_during_Rset,
        "h2_during_vcom_bframe": h2_during_bframe,
        "h2_baseline_vcom": h2_baseline_vcom,
        "h2_edge_baseline_Rset": h2_edge_baseline_Rset,
        "h1b_observed": h1b_observed, "h1b_null": h1b_null,
        "fallback_used": fallback_used,
    }

    frames = {
        "head_c": head_c, "body_h": body_h, "head_t": head_t,
        "R": R, "v_com": v_com, "v_nose": v_nose, "eth_bs_h": eth_bs_h,
        "sweep_times_R": sweep_times_R, "sweep_times_bframe": sweep_times_bframe,
    }
    return trial_out, sweeps, frames


# --------------------------------------------------------------------------- #
#  Stats helpers
# --------------------------------------------------------------------------- #
def wilcoxon_safe(a, b, alternative):
    """Paired Wilcoxon signed-rank; returns (stat, p, n_used). Drops NaN pairs."""
    from scipy.stats import wilcoxon
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    n = int(m.sum())
    if n < 1 or np.all(a - b == 0):
        return np.nan, np.nan, n
    try:
        res = wilcoxon(a, b, alternative=alternative, zero_method="wilcox")
        return float(res.statistic), float(res.pvalue), n
    except Exception as e:  # noqa: BLE001
        logger.warning("wilcoxon failed: %s", e)
        return np.nan, np.nan, n


def spearman_boot_trials(x, y, trial_ids, n_boot=N_BOOT, seed=SEED):
    """Spearman rho over pooled points, 95% CI by bootstrap over TRIALS."""
    from scipy.stats import spearmanr
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    trial_ids = np.asarray(trial_ids)
    m = np.isfinite(x) & np.isfinite(y)
    x, y, trial_ids = x[m], y[m], trial_ids[m]
    if x.size < 3:
        return np.nan, np.nan, (np.nan, np.nan), int(x.size)
    rho, p = spearmanr(x, y)
    # bootstrap over trials
    uniq = np.unique(trial_ids)
    idx_by_trial = {t: np.nonzero(trial_ids == t)[0] for t in uniq}
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=uniq.size, replace=True)
        sel = np.concatenate([idx_by_trial[t] for t in pick])
        if sel.size < 3:
            continue
        rb, _ = spearmanr(x[sel], y[sel])
        if np.isfinite(rb):
            boots.append(rb)
    if boots:
        lo, hi = np.percentile(boots, [2.5, 97.5])
    else:
        lo, hi = np.nan, np.nan
    return float(rho), float(p), (float(lo), float(hi)), int(x.size)


def peri_curve(sig_by_trial, event_times_by_trial, t_by_trial, window, grid_dt,
               n_boot=N_BOOT, seed=SEED):
    """Peri-event mean curve + 95% CI bootstrap over trials.
    Returns grid, mean, lo, hi, n_sweeps, n_trials. One curve per trial = mean of
    that trial's sweep-aligned rows; bootstrap resamples trials."""
    grid = np.arange(window[0], window[1] + 1e-9, grid_dt)
    per_trial_curves = []
    n_sweeps = 0
    n_trials = 0
    for sig, ev, t in zip(sig_by_trial, event_times_by_trial, t_by_trial):
        if ev.size == 0:
            continue
        _, M = rc.peri_event_matrix(sig, t, ev, window=window, grid_dt=grid_dt)
        with np.errstate(invalid="ignore"):
            c = np.nanmean(M, axis=0)
        if np.isfinite(c).any():
            per_trial_curves.append(c)
            n_sweeps += ev.size
            n_trials += 1
    if not per_trial_curves:
        nanrow = np.full(grid.size, np.nan)
        return grid, nanrow, nanrow, nanrow, 0, 0
    C = np.vstack(per_trial_curves)  # (n_trials, n_grid)
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(C, axis=0)
    rng = np.random.default_rng(seed)
    nt = C.shape[0]
    boots = np.empty((n_boot, grid.size), float)
    for b in range(n_boot):
        pick = rng.integers(0, nt, size=nt)
        with np.errstate(invalid="ignore"):
            boots[b] = np.nanmean(C[pick], axis=0)
    lo = np.nanpercentile(boots, 2.5, axis=0)
    hi = np.nanpercentile(boots, 97.5, axis=0)
    return grid, mean, lo, hi, int(n_sweeps), int(n_trials)


# --------------------------------------------------------------------------- #
#  HDF5 writer
# --------------------------------------------------------------------------- #
def _ds(g, name, data):
    """Create a dataset, gzip4+shuffle on numeric arrays >=256 elems."""
    import h5py  # noqa: F401
    arr = np.asarray(data)
    kw = {}
    if arr.dtype.kind in "fiu" and arr.size >= 256:
        kw = dict(compression="gzip", compression_opts=4, shuffle=True)
    g.create_dataset(name, data=arr, **kw)


def write_h5(path, meta, sweep_cols, trials_out, frames_by_idx):
    import h5py
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with h5py.File(tmp, "w") as f:
        f.attrs["seed"] = SEED
        f.attrs["v_floor"] = meta["v_floor"]
        f.attrs["cutoff"] = ODOR_CUTOFF
        f.attrs["source_aggregate"] = AGG_PATH
        f.attrs["odor_fields_path"] = rc.ODOR_FIELDS_H5
        f.attrs["VERSION"] = VERSION
        f.attrs["created_utc"] = meta["created_utc"]
        f.attrs["README"] = (
            "Nose-Sweeps saved objects. /sweeps = per-sweep table (columns as arrays). "
            "/trials/<idx> = per-frame arrays for figures + per-trial attrs. "
            "See stats.json for inferential results. build_complete=1 written LAST."
        )
        f.attrs["build_complete"] = 0

        # /sweeps group -- per-sweep columns
        sg = f.create_group("sweeps")
        for name, col in sweep_cols.items():
            arr = np.asarray(col)
            if arr.dtype.kind == "U" or arr.dtype == object:
                arr = np.asarray([str(x) for x in col], dtype=h5py.string_dtype("utf-8"))
                sg.create_dataset(name, data=arr)
            else:
                _ds(sg, name, arr)

        # /trials/<idx> per-frame arrays
        tg = f.create_group("trials")
        for idx in sorted(frames_by_idx.keys()):
            fr = frames_by_idx[idx]
            to = trials_out[idx]
            grp = tg.create_group(f"{idx:03d}")
            _ds(grp, "head_c", fr["head_c"])
            _ds(grp, "body_h", fr["body_h"])
            _ds(grp, "head_t", fr["head_t"])
            _ds(grp, "R", fr["R"])
            _ds(grp, "v_com", fr["v_com"])
            _ds(grp, "v_nose", fr["v_nose"])
            _ds(grp, "eth_bs_h", fr["eth_bs_h"])
            _ds(grp, "sweep_times_R", fr["sweep_times_R"])
            _ds(grp, "sweep_times_bframe", fr["sweep_times_bframe"])
            grp.attrs["file_name"] = to["file_name"]
            grp.attrs["end_loc"] = to["end_loc"]
            grp.attrs["in_pooled"] = int(bool(to["in_pooled"]))
            grp.attrs["sweep_count"] = to["sweep_count"]
            grp.attrs["sweep_rate"] = to["sweep_rate"]
            grp.attrs["binding_frac"] = to["binding_frac"]
            grp.attrs["f_sweep"] = _nan(to["f_sweep"])
            grp.attrs["f_occ"] = _nan(to["f_occ"])
            grp.attrs["h2_during_vcom_Rset"] = _nan(to["h2_during_vcom_Rset"])
            grp.attrs["h2_during_vcom_bframe"] = _nan(to["h2_during_vcom_bframe"])
            grp.attrs["h2_baseline_vcom"] = _nan(to["h2_baseline_vcom"])

        f.attrs["build_complete"] = 1  # LAST
    os.replace(tmp, path)
    logger.info("wrote %s (build_complete=1)", path)


def _nan(v):
    return float(v) if v is not None and np.isfinite(v) else float("nan")


# --------------------------------------------------------------------------- #
#  JSON-safe conversion
# --------------------------------------------------------------------------- #
def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, float):
        return o if np.isfinite(o) else None
    return o


def dump_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_jsonable(obj), fh, indent=2)
    os.replace(tmp, path)
    logger.info("wrote %s", path)


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main(limit=None):
    t_start = time.time()
    logger.info("=== build_sweeps start (seed=%d, VERSION=%s) ===", SEED, VERSION)
    self_check()

    agg = Aggregate(AGG_PATH)
    trials = agg.behavior(lighting="infrared")
    agg.close()
    logger.info("loaded %d infrared trials", len(trials))
    assert len(trials) == 114, f"expected 114 trials, got {len(trials)}"

    # global de-jump thresholds (pooled)
    Q_body = rc.pooled_dejump_Q(trials, track="body")
    Q_head = rc.pooled_dejump_Q(trials, track="head")
    logger.info("dejump Q body=%.4f head=%.4f px", Q_body, Q_head)

    # PASS 1: v_floor
    v_floor, pooled_vcom = pass1_v_floor(trials, Q_body, Q_head)

    if limit is not None:
        trials = trials[:limit]
        logger.info("SLICE MODE: processing first %d trials", len(trials))

    # PASS 2
    odor_cache = {}
    trials_out = {}
    frames_by_idx = {}
    all_sweeps = []  # list of dict with trial_index & file_name & fields
    body_dj_removed_total = head_dj_removed_total = 0
    body_box_total = head_box_total = 0
    binding_fracs = []
    pooled_vnose_frames = []
    pooled_vcom_frames = []
    pooled_bframe_frames = []

    for k, tr in enumerate(trials):
        fn = tr.get("file_name", "?")
        try:
            to, sweeps, frames = process_trial(tr, Q_body, Q_head, v_floor, odor_cache)
        except Exception as e:  # noqa: BLE001
            logger.warning("PASS2 skip trial %d %s: %s", k, fn, e)
            continue
        trials_out[k] = to
        frames_by_idx[k] = frames
        binding_fracs.append(to["binding_frac"])
        body_dj_removed_total += to["n_body_dejump_removed"]
        head_dj_removed_total += to["n_head_dejump_removed"]
        body_box_total += to["n_body_box_kept"]
        head_box_total += to["n_head_box_kept"]
        pooled_vnose_frames.append(frames["v_nose"][np.isfinite(frames["v_nose"])])
        pooled_vcom_frames.append(frames["v_com"][np.isfinite(frames["v_com"])])
        # bframe not in frames dict; recompute pooled from R? we stored via to; skip magnitude for bframe pooled
        for s in sweeps:
            s2 = dict(s)
            s2["trial_index"] = k
            s2["file_name"] = to["file_name"]
            s2["end_loc"] = to["end_loc"]
            s2["in_pooled"] = to["in_pooled"]
            all_sweeps.append(s2)
        logger.debug("trial %d %s: sweeps=%d rate=%.3f/s binding=%.3f f_sweep=%s f_occ=%.3f",
                     k, fn, to["sweep_count"], to["sweep_rate"], to["binding_frac"],
                     to["f_sweep"], to["f_occ"])

    n_processed = len(trials_out)
    logger.info("PASS2: processed %d/%d trials, %d total sweeps",
                n_processed, len(trials), len(all_sweeps))

    # slice-mode assertions (sanity)
    if limit is not None:
        vn = np.concatenate(pooled_vnose_frames)
        assert np.nanmedian(vn) > 1 and np.nanmedian(vn) < 500, "v_nose insane"
        assert all(np.isfinite(frames_by_idx[k]["R"]).all() for k in frames_by_idx), "R not finite"
        assert len(all_sweeps) > 0, "no sweeps found in slice"
        assert all(isinstance(s["in_odor"], bool) for s in all_sweeps), "in_odor not bool"
        logger.info("SLICE self-asserts PASS (v_nose med=%.2f, sweeps=%d)",
                    np.nanmedian(vn), len(all_sweeps))
        logger.info("=== slice done in %.1fs ===", time.time() - t_start)
        return

    # ---------------- build per-sweep column arrays ----------------
    def col(key, dtype=float):
        return np.array([s[key] for s in all_sweeps], dtype=dtype)

    sweep_cols = {
        "trial_index": col("trial_index", int),
        "file_name": np.array([s["file_name"] for s in all_sweeps], object),
        "end_loc": np.array([s["end_loc"] for s in all_sweeps], object),
        "in_pooled": col("in_pooled", bool),
        "peak_time": col("peak_time"),
        "R": col("R"),
        "v_nose": col("v_nose"),
        "v_com": col("v_com"),
        "nose_driven": col("nose_driven", bool),
        "com_dropout": col("com_dropout", bool),
        "summed_eth": col("summed_eth"),
        "mean_eth": col("mean_eth"),
        "in_odor": col("in_odor", bool),
    }

    # pooled masks (Loc1-6)
    pooled_mask = sweep_cols["in_pooled"]
    pooled_trials = [k for k in trials_out if trials_out[k]["in_pooled"]]
    logger.info("pooled trials (Loc1-6): %d; pooled sweeps: %d",
                len(pooled_trials), int(pooled_mask.sum()))

    created_utc = _utc()
    meta_h5 = {"v_floor": v_floor, "created_utc": created_utc}

    # ================= STATS =================
    stats = build_stats(all_sweeps, trials_out, pooled_trials, frames_by_idx,
                        v_floor, binding_fracs, pooled_vcom,
                        pooled_vnose_frames, pooled_vcom_frames,
                        body_dj_removed_total, body_box_total,
                        head_dj_removed_total, head_box_total, created_utc)

    # ================= SAVE =================
    write_h5(os.path.join(DATA_DIR, "sweeps.h5"), meta_h5, sweep_cols,
             trials_out, frames_by_idx)

    # sweeps.json = per-sweep + per-trial tables (no big per-frame arrays)
    sweeps_json = {
        "meta": {"seed": SEED, "VERSION": VERSION, "v_floor": v_floor,
                 "created_utc": created_utc, "n_sweeps": len(all_sweeps),
                 "n_trials": n_processed},
        "sweeps": [{k: v for k, v in s.items()} for s in all_sweeps],
        "trials": [trials_out[k] for k in sorted(trials_out)],
    }
    dump_json(os.path.join(DATA_DIR, "sweeps.json"), sweeps_json)
    dump_json(os.path.join(DATA_DIR, "stats.json"), stats)

    logger.info("=== build_sweeps DONE in %.1fs ===", time.time() - t_start)
    _print_summary(stats)


# --------------------------------------------------------------------------- #
#  Build all stats
# --------------------------------------------------------------------------- #
def build_stats(all_sweeps, trials_out, pooled_trials, frames_by_idx,
                v_floor, binding_fracs, pooled_vcom,
                pooled_vnose_frames, pooled_vcom_frames,
                body_dj_removed_total, body_box_total,
                head_dj_removed_total, head_box_total, created_utc):
    stats = {}

    pooled_set = set(pooled_trials)
    pooled_sweeps = [s for s in all_sweeps if s["trial_index"] in pooled_set]

    vn_all = np.concatenate(pooled_vnose_frames) if pooled_vnose_frames else np.array([])
    vc_all = np.concatenate(pooled_vcom_frames) if pooled_vcom_frames else np.array([])

    stats["meta"] = {
        "seed": SEED, "VERSION": VERSION,
        "v_floor": v_floor,
        "v_floor_binding_frac_pooled_mean": float(np.mean(binding_fracs)) if binding_fracs else None,
        "dejump_removed_frac_body": float(body_dj_removed_total / body_box_total) if body_box_total else None,
        "dejump_removed_frac_head": float(head_dj_removed_total / head_box_total) if head_box_total else None,
        "n_trials_processed": len(trials_out),
        "n_trials_pooled": len(pooled_trials),
        "n_sweeps_total": len(all_sweeps),
        "n_sweeps_pooled": len(pooled_sweeps),
        "velocity_pct": {
            "v_nose_px_s": {p: float(np.percentile(vn_all, p)) for p in (1, 50, 90, 99)} if vn_all.size else None,
            "v_com_px_s": {p: float(np.percentile(vc_all, p)) for p in (1, 50, 90, 99)} if vc_all.size else None,
            "pooled_vcom_all_px_s": {p: float(np.percentile(pooled_vcom, p)) for p in (1, 10, 50, 90, 99)},
        },
        "created_utc": created_utc,
        "n_permutations": N_PERM, "n_bootstrap": N_BOOT,
        "windows": {"peri": PERI_WIN, "eth_sum": ETH_SUM_WIN, "h2_during": H2_WIN,
                    "grid_dt": PERI_GRID_DT},
        "multiple_comparisons": "per-test CIs; no family-wise correction across H1-H3",
    }

    # ---- prevalence (H1a) ----
    counts = np.array([trials_out[k]["sweep_count"] for k in pooled_trials], float)
    rates = np.array([trials_out[k]["sweep_rate"] for k in pooled_trials], float)
    stats["H1a_prevalence"] = {
        "note": "LEAD with RATE (per s); counts are duration-driven. Many sweeps are routine nose motion.",
        "sweep_rate_per_s": {"min": float(np.min(rates)), "median": float(np.median(rates)),
                             "max": float(np.max(rates)), "mean": float(np.mean(rates))},
        "sweep_count_per_trial": {"min": float(np.min(counts)), "median": float(np.median(counts)),
                                  "max": float(np.max(counts)), "mean": float(np.mean(counts))},
        "total_sweeps_pooled": int(counts.sum()),
        "median_sweeps_per_trial": float(np.median(counts)),
        "n_trials": len(pooled_trials),
    }

    # ---- H1b peri-sweep odor enrichment (paired Wilcoxon observed vs null) ----
    obs = np.array([trials_out[k]["h1b_observed"] for k in pooled_trials], float)
    nul = np.array([trials_out[k]["h1b_null"] for k in pooled_trials], float)
    stat, p, n_used = wilcoxon_safe(obs, nul, alternative="greater")
    stats["H1b_peri_sweep_odor"] = {
        "test": "paired Wilcoxon (observed > matched-count random-time null), per trial",
        "statistic": stat, "p_value": p, "n_trials": n_used,
        "median_observed": float(np.nanmedian(obs)),
        "median_null": float(np.nanmedian(nul)),
        "direction": "observed>null" if np.nanmedian(obs) > np.nanmedian(nul) else "observed<=null",
    }

    # ---- H1c Spearman rho(R@peak, summed peri eth) pooled ----
    R_peak = np.array([s["R"] for s in pooled_sweeps], float)
    summed = np.array([s["summed_eth"] for s in pooled_sweeps], float)
    tid = np.array([s["trial_index"] for s in pooled_sweeps])
    rho, pc, (lo, hi), n_pts = spearman_boot_trials(R_peak, summed, tid)
    stats["H1c_spearman"] = {
        "test": "Spearman rho(R@peak, summed eth_bs [-0.5,+0.5]s), one point/sweep, pooled Loc1-6; CI bootstrap over trials",
        "rho": rho, "p_value": pc, "ci95": [lo, hi], "n_sweeps": n_pts,
        "direction": "positive" if (np.isfinite(rho) and rho > 0) else "non-positive",
        "ci_excludes_0": bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0)),
    }

    # ---- H1 amplitude check (rule 9) ----
    mean_eth = np.array([s["mean_eth"] for s in pooled_sweeps], float)
    mean_eth_f = mean_eth[np.isfinite(mean_eth)]
    # peak eth per sweep: use peri matrix max? approximate with summed/n? Use per-sweep peak via frames
    peak_eth = _peri_peak_eth(pooled_sweeps, trials_out, frames_by_idx)
    peak_eth_f = peak_eth[np.isfinite(peak_eth)]
    frac_gt = float(np.mean(mean_eth_f > 0.01)) if mean_eth_f.size else None
    stats["H1_amplitude_check"] = {
        "note": "Compare peri-sweep eth_bs to real range (~0.14) and deconv noise floor (~4e-4).",
        "real_range_ref": 0.14, "noise_floor_ref": 4e-4,
        "peri_eth_mean": {"median": float(np.median(mean_eth_f)) if mean_eth_f.size else None,
                          "mean": float(np.mean(mean_eth_f)) if mean_eth_f.size else None,
                          "p90": float(np.percentile(mean_eth_f, 90)) if mean_eth_f.size else None},
        "peri_eth_peak": {"median": float(np.median(peak_eth_f)) if peak_eth_f.size else None,
                          "p90": float(np.percentile(peak_eth_f, 90)) if peak_eth_f.size else None},
        "frac_sweeps_peri_eth_mean_gt_0.01": frac_gt,
        "above_noise_floor": bool(mean_eth_f.size and np.median(mean_eth_f) > 4e-4),
    }

    # ---- H2 primary (R-set) + numerator-only (bframe) ----
    h2d_R = np.array([trials_out[k]["h2_during_vcom_Rset"] for k in pooled_trials], float)
    h2d_b = np.array([trials_out[k]["h2_during_vcom_bframe"] for k in pooled_trials], float)
    h2_base = np.array([trials_out[k]["h2_baseline_vcom"] for k in pooled_trials], float)
    h2_edge = np.array([trials_out[k]["h2_edge_baseline_Rset"] for k in pooled_trials], float)

    sR, pR, nR = wilcoxon_safe(h2d_R, h2_base, alternative="less")
    sRe, pRe, nRe = wilcoxon_safe(h2d_R, h2_edge, alternative="less")
    sB, pB, nB = wilcoxon_safe(h2d_b, h2_base, alternative="less")

    nose_driven = np.array([s["nose_driven"] for s in pooled_sweeps], bool)
    com_dropout = np.array([s["com_dropout"] for s in pooled_sweeps], bool)
    per_trial_split = []
    for k in pooled_trials:
        ss = [s for s in pooled_sweeps if s["trial_index"] == k]
        if ss:
            per_trial_split.append({
                "trial_index": k,
                "n_nose_driven": int(sum(s["nose_driven"] for s in ss)),
                "n_com_dropout": int(sum(s["com_dropout"] for s in ss)),
                "n_sweeps": len(ss)})

    bframe_survives = bool(np.isfinite(pB) and pB < 0.05 and np.nanmedian(h2d_b) < np.nanmedian(h2_base))
    stats["H2"] = {
        "primary_Rset_vs_median": {"test": "paired Wilcoxon during<baseline (trial median v_com)",
                                   "statistic": sR, "p_value": pR, "n_trials": nR,
                                   "median_during": float(np.nanmedian(h2d_R)),
                                   "median_baseline": float(np.nanmedian(h2_base))},
        "primary_Rset_vs_edge": {"test": "paired Wilcoxon during<baseline (+-1s window-edge)",
                                 "statistic": sRe, "p_value": pRe, "n_trials": nRe,
                                 "median_during": float(np.nanmedian(h2d_R)),
                                 "median_edge_baseline": float(np.nanmedian(h2_edge))},
        "HEADLINE_numerator_only_bframe": {
            "test": "paired Wilcoxon during<baseline on numerator-only (bframe) sweep set",
            "statistic": sB, "p_value": pB, "n_trials": nB,
            "median_during": float(np.nanmedian(h2d_b)),
            "median_baseline": float(np.nanmedian(h2_base)),
            "note": "This is the non-circular test; H2 acceptance rests on it (D6)."},
        "circularity_split_pooled": {
            "n_nose_driven": int(nose_driven.sum()),
            "n_com_dropout": int(com_dropout.sum()),
            "n_both": int((nose_driven & com_dropout).sum()),
            "n_sweeps": int(len(pooled_sweeps))},
        "circularity_split_per_trial": per_trial_split,
        "slowdown_survives_numerator_only": bframe_survives,
        "interpretation": ("behavioral (survives numerator-only)" if bframe_survives
                           else "definitional or absent (only R-set / not significant on bframe)"),
    }

    # ---- H3 spatial enrichment ----
    f_sweep = np.array([trials_out[k]["f_sweep"] for k in pooled_trials], float)
    f_occ = np.array([trials_out[k]["f_occ"] for k in pooled_trials], float)
    h3_stat = np.array([trials_out[k]["h3_stat"] for k in pooled_trials], float)
    s3a, p3a, n3a = wilcoxon_safe(f_sweep, f_occ, alternative="greater")
    # f_sweep - null > 0 : test h3_stat > 0 via wilcoxon vs zeros
    zeros = np.zeros_like(h3_stat)
    s3b, p3b, n3b = wilcoxon_safe(h3_stat, zeros, alternative="greater")
    m_valid = np.isfinite(f_sweep) & np.isfinite(f_occ)
    frac_enriched = float(np.mean(f_sweep[m_valid] > f_occ[m_valid])) if m_valid.any() else None
    stats["H3"] = {
        "test_f_sweep_gt_f_occ": {"test": "paired Wilcoxon f_sweep>f_occ",
                                  "statistic": s3a, "p_value": p3a, "n_trials": n3a},
        "test_f_sweep_gt_null": {"test": "Wilcoxon (f_sweep-mean(null))>0",
                                 "statistic": s3b, "p_value": p3b, "n_trials": n3b},
        "median_f_sweep": float(np.nanmedian(f_sweep)),
        "median_f_occ": float(np.nanmedian(f_occ)),
        "frac_trials_enriched": frac_enriched,
        "cutoff": ODOR_CUTOFF,
        "note": "odor-reached = valid(count>=3) bin with max-field>cutoff(0.001); mapped-bin ethanol above noise floor.",
    }

    # ---- F1A / F1B peri-sweep curves (pooled Loc1-6, R-set) ----
    sig_eth, sig_vcom, ev_list, t_list = [], [], [], []
    for k in pooled_trials:
        fr = frames_by_idx[k]
        sig_eth.append(fr["eth_bs_h"])
        sig_vcom.append(fr["v_com"])
        ev_list.append(fr["sweep_times_R"])
        t_list.append(fr["head_t"])
    g1, m1, lo1, hi1, ns1, nt1 = peri_curve(sig_eth, ev_list, t_list, PERI_WIN, PERI_GRID_DT)
    g2, m2, lo2, hi2, ns2, nt2 = peri_curve(sig_vcom, ev_list, t_list, PERI_WIN, PERI_GRID_DT)
    stats["F1A_peri_eth"] = {"grid_s": g1.tolist(), "mean": m1.tolist(),
                             "ci_lo": lo1.tolist(), "ci_hi": hi1.tolist(),
                             "n_sweeps": ns1, "n_trials": nt1}
    stats["F1B_peri_vcom"] = {"grid_s": g2.tolist(), "mean": m2.tolist(),
                              "ci_lo": lo2.tolist(), "ci_hi": hi2.tolist(),
                              "n_sweeps": ns2, "n_trials": nt2}

    # ---- F3 example: highest sweep RATE pooled trial (tie-break raw count) ----
    best_k, best = None, (-1.0, -1)
    for k in pooled_trials:
        key = (trials_out[k]["sweep_rate"], trials_out[k]["sweep_count"])
        if key > best:
            best, best_k = key, k
    stats["F3_example"] = {
        "trial_index": best_k,
        "file_name": trials_out[best_k]["file_name"],
        "sweep_rate": trials_out[best_k]["sweep_rate"],
        "sweep_count": trials_out[best_k]["sweep_count"],
        "end_loc": trials_out[best_k]["end_loc"],
    }

    # anotherLoc separate note
    aloc = [k for k in trials_out if trials_out[k]["end_loc"] == "anotherLoc"]
    stats["anotherLoc_separate"] = {
        "n_trials": len(aloc),
        "note": "Analysed separately; excluded from pooled stats/figures (D10).",
        "median_sweep_rate": float(np.median([trials_out[k]["sweep_rate"] for k in aloc])) if aloc else None,
    }

    return stats


def _peri_peak_eth(sweeps, trials_out, frames_by_idx):
    """Per-sweep peak eth_bs over [-0.5,+0.5]s (for amplitude check)."""
    out = []
    # group sweeps by trial to reuse the peri matrix
    by_trial = {}
    for s in sweeps:
        by_trial.setdefault(s["trial_index"], []).append(s)
    for k, ss in by_trial.items():
        fr = frames_by_idx[k]
        times = np.array([s["peak_time"] for s in ss], float)
        _, M = rc.peri_event_matrix(fr["eth_bs_h"], fr["head_t"], times,
                                    window=ETH_SUM_WIN, grid_dt=PERI_GRID_DT)
        import warnings
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            pk = np.nanmax(M, axis=1)
        out.extend(pk.tolist())
    return np.array(out, float)


def _print_summary(stats):
    m = stats["meta"]
    logger.info("---- SUMMARY ----")
    logger.info("v_floor=%.3f px/s, binding_frac(pooled mean)=%.4f",
                m["v_floor"], m["v_floor_binding_frac_pooled_mean"])
    h1a = stats["H1a_prevalence"]
    logger.info("sweep rate median=%.3f/s, total pooled sweeps=%d, median count/trial=%.0f",
                h1a["sweep_rate_per_s"]["median"], h1a["total_sweeps_pooled"],
                h1a["median_sweeps_per_trial"])
    h1b = stats["H1b_peri_sweep_odor"]
    logger.info("H1b Wilcoxon stat=%s p=%s | median obs=%.5f vs null=%.5f",
                h1b["statistic"], h1b["p_value"], h1b["median_observed"], h1b["median_null"])
    ac = stats["H1_amplitude_check"]
    logger.info("H1 amplitude: frac peri-eth mean>0.01=%s, above_floor=%s",
                ac["frac_sweeps_peri_eth_mean_gt_0.01"], ac["above_noise_floor"])
    h1c = stats["H1c_spearman"]
    logger.info("H1c Spearman rho=%.4f CI=[%.4f,%.4f] p=%s",
                h1c["rho"], h1c["ci95"][0], h1c["ci95"][1], h1c["p_value"])
    h2 = stats["H2"]
    logger.info("H2 R-set p=%s | bframe(headline) p=%s | survives=%s",
                h2["primary_Rset_vs_median"]["p_value"],
                h2["HEADLINE_numerator_only_bframe"]["p_value"],
                h2["slowdown_survives_numerator_only"])
    logger.info("H2 split: nose_driven=%d com_dropout=%d (of %d)",
                h2["circularity_split_pooled"]["n_nose_driven"],
                h2["circularity_split_pooled"]["n_com_dropout"],
                h2["circularity_split_pooled"]["n_sweeps"])
    h3 = stats["H3"]
    logger.info("H3 f_sweep>f_occ p=%s | median f_sweep=%.4f f_occ=%.4f | frac enriched=%s",
                h3["test_f_sweep_gt_f_occ"]["p_value"], h3["median_f_sweep"],
                h3["median_f_occ"], h3["frac_trials_enriched"])
    ex = stats["F3_example"]
    logger.info("F3 example: %s rate=%.3f/s count=%d",
                ex["file_name"], ex["sweep_rate"], ex["sweep_count"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="process only first N trials (slice mode)")
    args = ap.parse_args()
    main(limit=args.limit)
