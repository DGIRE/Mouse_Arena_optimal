r"""build_odor_fields.py -- Task 1 DATA ANALYST script.

Builds per-location spatial odor fields (max/mean/min/count over square bins) from
deconvolved ethanol (`ethdeconv`) sampled along the cleaned HEAD trajectory, plus
sparseness / distance-dependence / trajectory statistics, per the pre-registered PLAN.

Outputs (under Analysis\Plume locations\):
  data\odor_fields.h5          -- HDF5 field maps (exact contract)
  data\odor_field_stats.json   -- every number the report needs
  logs\build_odor_fields.log   -- verbose log

Signal = ethdeconv aligned to the HEAD clock via align_signal. Head cleaned with a
single global Q = pooled_dejump_Q(trials,'head'). NaN aligned samples (outside sensor
coverage) excluded. anotherLoc reported separately, excluded from the six-field pool.

Run:  "$AR_PY" code\build_odor_fields.py            (full run)
      "$AR_PY" code\build_odor_fields.py --slice    (2-location smoke test)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

import numpy as np

# ----- locate plume_common (same dir as this script) ------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import plume_common as pc  # noqa: E402

# scipy / statsmodels
from scipy.optimize import curve_fit  # noqa: E402
from scipy.stats import t as t_dist  # noqa: E402
from scipy.stats import spearmanr, norm as norm_dist  # noqa: E402

# ----- paths ----------------------------------------------------------------
_ANALYSIS_ROOT = os.path.dirname(_HERE)  # ...\Plume locations
DATA_DIR = os.path.join(_ANALYSIS_ROOT, "data")
LOGS_DIR = os.path.join(_ANALYSIS_ROOT, "logs")
H5_OUT = os.path.join(DATA_DIR, "odor_fields.h5")
STATS_OUT = os.path.join(DATA_DIR, "odor_field_stats.json")
LOG_OUT = os.path.join(LOGS_DIR, "build_odor_fields.log")

GENERATOR = "build_odor_fields.py"
SCHEMA_VERSION = "1.0"
L_SCAN = [40, 30, 25, 20, 15, 10]  # descending
COVERAGE_TARGET = 0.60
MIN_TRIALS = 3
SMALL_FLOOR = 1e-3
# arena diagonal in px: sqrt(580^2 + 280^2) ~= 644. An exp-decay lambda that
# exceeds this (or is <=0, or has a non-finite/absurd SE) is non-physical (the
# curve is effectively flat over the arena) -> flag degenerate, store null.
ARENA_DIAG_PX = float(np.hypot(pc.ARENA[1] - pc.ARENA[0], pc.ARENA[3] - pc.ARENA[2]))
LOC_ORDER = ["Loc1", "Loc2", "Loc3", "Loc4", "Loc5", "Loc6", "anotherLoc"]
POOLED_LOCS = ["Loc1", "Loc2", "Loc3", "Loc4", "Loc5", "Loc6"]

log = logging.getLogger("build_odor_fields")


# =========================================================================== #
#  Small numeric helpers                                                       #
# =========================================================================== #
def _jsonable(obj):
    """Recursively convert numpy types / arrays to JSON-serializable python."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, float):
        return obj if np.isfinite(obj) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def grid_edges(L):
    """Bin edges tiling ARENA (0..580, 0..280) with square bins of edge L px."""
    xmin, xmax, ymin, ymax = pc.ARENA
    nx = int(np.ceil((xmax - xmin) / L))
    ny = int(np.ceil((ymax - ymin) / L))
    x_edges = xmin + L * np.arange(nx + 1)
    y_edges = ymin + L * np.arange(ny + 1)
    return x_edges, y_edges, nx, ny


def bin_indices(xy, x_edges, y_edges):
    """Return (row=y-bin, col=x-bin) integer indices for each sample; clip to grid.
    Samples are already in-box (0..580, 0..280) after cleaning."""
    x = xy[:, 0]
    y = xy[:, 1]
    nx = x_edges.size - 1
    ny = y_edges.size - 1
    col = np.clip(np.searchsorted(x_edges, x, side="right") - 1, 0, nx - 1)
    row = np.clip(np.searchsorted(y_edges, y, side="right") - 1, 0, ny - 1)
    return row.astype(np.int64), col.astype(np.int64)


def bin_center_grid(x_edges, y_edges):
    """Return (yc, xc) center coordinate arrays broadcastable to (ny, nx)."""
    xc = 0.5 * (x_edges[:-1] + x_edges[1:])
    yc = 0.5 * (y_edges[:-1] + y_edges[1:])
    return yc, xc


def slope_ci_ols(x, y, alpha=0.05):
    """OLS y ~ a + b*x with t-based 95% CI on slope. Returns dict or None if <3 pts."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    n = x.size
    if n < 3 or np.ptp(x) == 0:
        return None
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = n - 2
    if dof <= 0:
        return None
    sigma2 = float(resid @ resid) / dof
    XtX_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(sigma2 * XtX_inv))
    tcrit = float(t_dist.ppf(1 - alpha / 2, dof))
    slope = float(beta[1])
    se_slope = float(se[1])
    return {
        "intercept": float(beta[0]),
        "slope": slope,
        "slope_se": se_slope,
        "slope_ci95": [slope - tcrit * se_slope, slope + tcrit * se_slope],
        "n": int(n),
        "dof": int(dof),
    }


def exp_decay_fit(d, y):
    """Fit y = a*exp(-d/lambda)+c; return lambda + 95% CI from covariance."""
    d = np.asarray(d, float)
    y = np.asarray(y, float)
    m = np.isfinite(d) & np.isfinite(y)
    d, y = d[m], y[m]
    n = d.size
    if n < 4 or np.ptp(d) == 0:
        return None

    def model(dd, a, lam, c):
        return a * np.exp(-dd / lam) + c

    # data-driven initial guesses
    a0 = float(np.nanmax(y) - np.nanmin(y))
    if a0 <= 0:
        a0 = float(np.nanmax(np.abs(y))) or 1.0
    lam0 = max(float(np.ptp(d)) / 3.0, 1.0)
    c0 = float(np.nanmin(y))
    try:
        popt, pcov = curve_fit(
            model, d, y, p0=[a0, lam0, c0],
            bounds=([-np.inf, 1e-3, -np.inf], [np.inf, np.inf, np.inf]),
            maxfev=20000,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"curve_fit failed: {e}", "n": int(n)}
    perr = np.sqrt(np.diag(pcov)) if np.all(np.isfinite(pcov)) else np.full(3, np.nan)
    lam = float(popt[1])
    lam_se = float(perr[1])
    dof = n - 3
    tcrit = float(t_dist.ppf(0.975, dof)) if dof > 0 else np.nan
    lam_ci = [lam - tcrit * lam_se, lam + tcrit * lam_se] if np.isfinite(lam_se) and np.isfinite(tcrit) else [None, None]
    # m3: suppress non-physical / degenerate fits. lambda beyond the arena diagonal
    # means the exponential is effectively flat over the arena (no resolvable decay);
    # a non-positive lambda or a non-finite SE is likewise uninformative.
    degenerate = (
        (not np.isfinite(lam))
        or (lam <= 0.0)
        or (lam > ARENA_DIAG_PX)
        or (not np.isfinite(lam_se))
    )
    if degenerate:
        reason = (
            "non-finite lambda" if not np.isfinite(lam)
            else "lambda<=0" if lam <= 0.0
            else "lambda>arena_diagonal(%.0fpx)" % ARENA_DIAG_PX if lam > ARENA_DIAG_PX
            else "non-finite lambda_se"
        )
        return {
            "a": float(popt[0]),
            "lambda": None,
            "lambda_se": None,
            "lambda_ci95": [None, None],
            "c": float(popt[2]),
            "n": int(n),
            "degenerate": True,
            "degenerate_reason": reason,
            "lambda_raw": lam if np.isfinite(lam) else None,
        }
    return {
        "a": float(popt[0]),
        "lambda": lam,
        "lambda_se": lam_se,
        "lambda_ci95": lam_ci,
        "c": float(popt[2]),
        "n": int(n),
        "degenerate": False,
    }


def spearman_ci(x, y, alpha=0.05):
    """Spearman rho + 95% CI via Fisher z transform. Returns dict or None."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    n = x.size
    if n < 4 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return {"rho": None, "pvalue": None, "ci95": [None, None], "n": int(n)}
    rho, p = spearmanr(x, y)
    rho = float(rho)
    # Fisher z CI (standard approximation for Spearman)
    if abs(rho) >= 1.0:
        return {"rho": rho, "pvalue": float(p), "ci95": [rho, rho], "n": int(n)}
    z = np.arctanh(rho)
    se = 1.0 / np.sqrt(n - 3)
    zcrit = float(norm_dist.ppf(1 - alpha / 2))
    lo = np.tanh(z - zcrit * se)
    hi = np.tanh(z + zcrit * se)
    return {"rho": rho, "pvalue": float(p), "ci95": [float(lo), float(hi)], "n": int(n)}


def pearson_nan(a, b):
    """NaN-aware Pearson r over positions valid in BOTH maps."""
    a = np.asarray(a, float).ravel()
    b = np.asarray(b, float).ravel()
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return None, int(m.sum())
    aa = a[m]
    bb = b[m]
    if np.std(aa) == 0 or np.std(bb) == 0:
        return None, int(m.sum())
    r = float(np.corrcoef(aa, bb)[0, 1])
    return r, int(m.sum())


# =========================================================================== #
#  Per-trial cleaned samples (head + body) with aligned ethdeconv             #
# =========================================================================== #
def trial_head_samples(tr, Q):
    """Clean HEAD track, align ethdeconv to head clock, drop NaN(coverage) samples.
    Returns dict with xy (n,2), t (n,), eth (n,), and cleaning counts, or None."""
    head = np.asarray(tr["head"], float)
    ht = np.asarray(tr["head_time"], float)
    n_total, n_after_box, n_after_dejump = pc.clean_counts(head, ht, Q)
    idx, xy_clean, t_clean = pc.clean_track(head, ht, Q)
    if idx.size == 0:
        return None
    eth = pc.align_signal(t_clean, np.asarray(tr["ethanol_time"], float),
                          np.asarray(tr["ethdeconv"], float))
    cov = np.isfinite(eth)
    return {
        "xy": xy_clean[cov],
        "t": t_clean[cov],
        "eth": eth[cov],
        "n_total": int(n_total),
        "n_after_box": int(n_after_box),
        "n_after_dejump": int(n_after_dejump),
        "n_after_coverage": int(cov.sum()),
        # keep un-coverage-masked cleaned arrays for trajectory path length
        "xy_cleaned_all": xy_clean,
        "eth_cleaned_all": eth,  # may contain NaN outside coverage
        "t_cleaned_all": t_clean,
    }


def trial_body_samples(tr, Q):
    """Clean BODY track, align ethdeconv to BODY clock, drop NaN samples."""
    body = np.asarray(tr["body"], float)
    bt = np.asarray(tr["body_time"], float)
    idx, xy_clean, t_clean = pc.clean_track(body, bt, Q)
    if idx.size == 0:
        return None
    eth = pc.align_signal(t_clean, np.asarray(tr["ethanol_time"], float),
                          np.asarray(tr["ethdeconv"], float))
    cov = np.isfinite(eth)
    return {"xy": xy_clean[cov], "eth": eth[cov]}


# =========================================================================== #
#  Grid binning: per-bin pooled max/mean/min + distinct-trial count           #
# =========================================================================== #
def build_field(samples_list, x_edges, y_edges):
    """samples_list: list of (xy, eth) per trial. Vectorized accumulation.
    Returns dict with max_map, mean_map, min_map (NaN where <MIN_TRIALS trials),
    count_map (true # distinct trials), and raw sums/n for pooling if needed."""
    nx = x_edges.size - 1
    ny = y_edges.size - 1
    shape = (ny, nx)
    sum_map = np.zeros(shape, float)
    n_map = np.zeros(shape, np.int64)          # sample count
    max_map = np.full(shape, -np.inf)
    min_map = np.full(shape, np.inf)
    count_map = np.zeros(shape, np.int64)       # distinct trials

    for xy, eth in samples_list:
        if xy.shape[0] == 0:
            continue
        row, col = bin_indices(xy, x_edges, y_edges)
        flat = row * nx + col
        # per-sample accumulation (vectorized)
        np.add.at(sum_map.ravel(), flat, eth)
        np.add.at(n_map.ravel(), flat, 1)
        np.maximum.at(max_map.ravel(), flat, eth)
        np.minimum.at(min_map.ravel(), flat, eth)
        # distinct-trial contribution: 1 per unique bin this trial touched
        uniq = np.unique(flat)
        np.add.at(count_map.ravel(), uniq, 1)

    with np.errstate(invalid="ignore", divide="ignore"):
        mean_map = np.where(n_map > 0, sum_map / np.maximum(n_map, 1), np.nan)
    max_map = np.where(n_map > 0, max_map, np.nan)
    min_map = np.where(n_map > 0, min_map, np.nan)
    # mask <MIN_TRIALS in max/mean/min (keep true count map)
    mask = count_map < MIN_TRIALS
    mean_masked = mean_map.copy()
    max_masked = max_map.copy()
    min_masked = min_map.copy()
    mean_masked[mask] = np.nan
    max_masked[mask] = np.nan
    min_masked[mask] = np.nan

    visited = n_map > 0
    return {
        "max": max_masked,
        "mean": mean_masked,
        "min": min_masked,
        "count": count_map,
        "sum_raw": sum_map,
        "n_samples": n_map,
        "visited": visited,
        "samples_total": int(n_map.sum()),
        "n_visited_bins": int(visited.sum()),
    }


def choose_L(samples_list):
    """Scan L over L_SCAN; pick the SMALLEST (finest) L for which >=60% of visited
    bins have >=3 contributing trials. Fallback L=40 (noted) only if none reach the
    target. Records the full L_scan coverage table. Returns (L, coverage_frac,
    fallback, scan_table)."""
    scan = []
    passing = []  # (L, frac) among candidates meeting the target
    for L in L_SCAN:
        x_edges, y_edges, nx, ny = grid_edges(L)
        # compute count map + visited quickly
        shape = (ny, nx)
        n_map = np.zeros(shape, np.int64)
        count_map = np.zeros(shape, np.int64)
        for xy, _eth in samples_list:
            if xy.shape[0] == 0:
                continue
            row, col = bin_indices(xy, x_edges, y_edges)
            flat = row * nx + col
            np.add.at(n_map.ravel(), flat, 1)
            uniq = np.unique(flat)
            np.add.at(count_map.ravel(), uniq, 1)
        visited = n_map > 0
        nvis = int(visited.sum())
        if nvis == 0:
            frac = 0.0
        else:
            frac = float((count_map[visited] >= MIN_TRIALS).sum()) / nvis
        scan.append({"L": L, "n_visited_bins": nvis, "coverage_frac": frac})
        if frac >= COVERAGE_TARGET:
            passing.append((L, frac))
    if passing:
        # smallest passing L (finest grid the data support)
        L_min, frac_min = min(passing, key=lambda t: t[0])
        return L_min, frac_min, False, scan
    # fallback: L=40, report its coverage
    frac40 = next(s["coverage_frac"] for s in scan if s["L"] == 40)
    return 40, frac40, True, scan


# =========================================================================== #
#  Sparseness / distance / trajectory stats                                   #
# =========================================================================== #
def gini_mc_null(vals, n_samples_per_bin, n_draws=2000, seed=pc.SEED):
    """Monte-Carlo null distribution for the mean-map Gini.

    Concrete, defensible redistribution (H0 = 'no spatial structure', i.e. the odor
    field is spatially uniform, so every SAMPLE has equal expected contribution
    regardless of which bin it fell in): hold each valid bin's real sample count
    n_i fixed, pool the observed total odor MASS across the N valid bins, then in
    each draw distribute that pooled mass over the pooled samples via a multinomial
    with equal per-sample probability (1/sum(n_i)). Each bin's synthetic per-sample
    MEAN = (its allocated mass) / n_i. Because bins with more samples average more
    draws, their synthetic means have lower variance -> realistic sampling noise.
    Recompute Gini on the synthetic mean map each draw -> null distribution.

    Returns dict: null_gini_mean, null_gini_ci95 (2.5/97.5 pctile), null_gini_std,
    pvalue (fraction of null Gini >= observed Gini), n_draws, note.
    Returns None if <2 valid bins or non-positive total mass.
    """
    vals = np.asarray(vals, float)
    n_i = np.asarray(n_samples_per_bin, float)
    m = np.isfinite(vals) & np.isfinite(n_i) & (n_i > 0)
    vals = vals[m]
    n_i = n_i[m]
    nb = vals.size
    if nb < 2:
        return None
    # observed total odor mass across valid bins (per-bin mean * per-bin sample count
    # = per-bin summed odor); floor negatives to 0 so mass is non-negative (Gini needs
    # non-negative and this matches the top5pct mass convention).
    mass_i = np.clip(vals, 0.0, None) * n_i
    total_mass = float(mass_i.sum())
    N_total = float(n_i.sum())
    if total_mass <= 0.0 or N_total <= 0.0:
        return None
    obs_gini = pc.gini(vals)
    rng = np.random.default_rng(seed)
    # per-sample odor contribution under H0: total mass spread over all samples
    per_sample = total_mass / N_total
    probs = n_i / N_total  # equal per-sample prob -> per-bin prob proportional to n_i
    N_int = int(round(N_total))
    null = np.empty(n_draws, float)
    for d in range(n_draws):
        alloc_counts = rng.multinomial(N_int, probs)  # samples landing in each bin
        syn_mass = alloc_counts.astype(float) * per_sample
        syn_mean = syn_mass / n_i  # synthetic per-bin mean
        null[d] = pc.gini(syn_mean)
    lo, hi = np.percentile(null, [2.5, 97.5])
    pval = float((null >= obs_gini).mean())
    return {
        "observed_gini": float(obs_gini),
        "null_gini_mean": float(np.mean(null)),
        "null_gini_std": float(np.std(null)),
        "null_gini_ci95": [float(lo), float(hi)],
        "pvalue": pval,
        "n_draws": int(n_draws),
        "seed": int(seed),
        "note": (
            "Monte-Carlo null (H0=spatially uniform field): per-bin sample counts held "
            "fixed; observed total odor mass (sum of clip(mean,0)*n_samples over valid "
            "bins) redistributed each draw via a multinomial over the pooled samples with "
            "equal per-sample probability, giving each bin a synthetic mean = allocated "
            "mass / its sample count; Gini recomputed per draw. p = fraction(null Gini >= "
            "observed Gini)."
        ),
    }


def sparseness_stats(mean_map, count_map, cutoff_1x, cutoff_3x, cutoff_5x, cutoff,
                     n_samples_map=None):
    """Compute sparseness stats on valid (>=MIN_TRIALS) bins of the mean map."""
    valid = (count_map >= MIN_TRIALS) & np.isfinite(mean_map)
    vals = mean_map[valid]
    n_valid = int(valid.sum())
    out = {
        "n_valid_bins": n_valid,
        "cutoff": float(cutoff),
        "frac_above_1xMAD": None,
        "frac_above_3xMAD": None,
        "frac_above_5xMAD": None,
        "top5pct_mass_share": None,
        "gini": None,
        "normalized_entropy": None,
        "gini_uniform_null": None,
        "gini_uniform_null_note": (
            "Analytic floor only: Gini of a same-N constant field is 0 by construction "
            "(no sampling variability). Kept for reference; significance comes from the "
            "Monte-Carlo null below."
        ),
        "gini_mc_null": None,
    }
    if n_valid == 0:
        return out
    out["frac_above_1xMAD"] = float((vals > cutoff_1x).mean())
    out["frac_above_3xMAD"] = float((vals > cutoff_3x).mean())
    out["frac_above_5xMAD"] = float((vals > cutoff_5x).mean())
    # top-5% bins share of total mean-odor mass (floor negatives to 0 for mass)
    mass = np.clip(vals, 0, None)
    total = mass.sum()
    if total > 0:
        k = max(1, int(np.ceil(0.05 * n_valid)))
        top = np.sort(mass)[::-1][:k]
        out["top5pct_mass_share"] = float(top.sum() / total)
    else:
        out["top5pct_mass_share"] = 0.0
    out["gini"] = pc.gini(vals)
    out["normalized_entropy"] = pc.normalized_entropy(vals)
    # analytic floor (kept, labeled): same n bins, equal values -> gini 0 by construction
    out["gini_uniform_null"] = pc.gini(np.ones(n_valid))
    # M3: proper Monte-Carlo null with realistic per-bin sampling noise
    if n_samples_map is not None:
        out["gini_mc_null"] = gini_mc_null(vals, n_samples_map[valid])
    return out


def distance_stats(field_map, count_map, endpoint, x_edges, y_edges, cutoff, label):
    """OLS log(odor)~distance (odor>cutoff) + exp-decay fit, for a given map."""
    valid = (count_map >= MIN_TRIALS) & np.isfinite(field_map)
    yc, xc = bin_center_grid(x_edges, y_edges)
    XC, YC = np.meshgrid(xc, yc)  # shape (ny, nx)
    dist = np.hypot(XC - endpoint[0], YC - endpoint[1])
    d_all = dist[valid]
    v_all = field_map[valid]

    out = {"label": label}
    # (a) OLS of log(mean) on distance over bins with value > cutoff
    pos = v_all > cutoff
    d_pos = d_all[pos]
    v_pos = v_all[pos]
    if v_pos.size >= 3 and np.all(v_pos > 0):
        ols = slope_ci_ols(d_pos, np.log(v_pos))
    elif v_pos.size >= 3:
        # guard: only strictly positive values can be logged
        ok = v_pos > 0
        ols = slope_ci_ols(d_pos[ok], np.log(v_pos[ok])) if ok.sum() >= 3 else None
    else:
        ols = None
    out["ols_log"] = ols
    out["ols_n_bins"] = int(v_pos.size)
    # (b) exponential decay fit over ALL valid bins (uses value directly)
    out["exp_decay"] = exp_decay_fit(d_all, v_all)
    out["exp_n_bins"] = int(v_all.size)
    return out


def trajectory_metrics(tr, samp, cutoff, group, animal):
    """Per-trial trajectory metrics using cleaned head samples."""
    xy_all = samp["xy_cleaned_all"]
    eth_all = samp["eth_cleaned_all"]
    t_all = samp["t_cleaned_all"]
    endpoint = pc.endpoint_of(tr)

    # path length: sum of cleaned head step sizes
    if xy_all.shape[0] >= 2:
        steps = np.linalg.norm(np.diff(xy_all, axis=0), axis=1)
        path_length = float(steps.sum())
    else:
        path_length = 0.0
    # straight-line start -> endpoint distance
    start = xy_all[0] if xy_all.shape[0] > 0 else np.array([np.nan, np.nan])
    straight = float(np.hypot(start[0] - endpoint[0], start[1] - endpoint[1]))
    tort = float(path_length / straight) if straight > 1e-9 else np.nan

    # coverage-masked signal for encounters + frac above threshold
    cov = np.isfinite(eth_all)
    eth_cov = eth_all[cov]
    t_cov = t_all[cov]
    if t_cov.size >= 3:
        pk = pc.detect_encounters(eth_cov, t_cov, thresh=cutoff,
                                  refractory_s=0.2, min_prominence=cutoff)
        n_enc = int(pk.size)
    else:
        n_enc = 0
    frac_above = float((eth_cov > cutoff).mean()) if eth_cov.size > 0 else np.nan

    return {
        "trial_index": int(tr["trial_index"]),
        "file_name": tr["file_name"],
        "group": group,
        "animal": animal,
        "path_length_px": path_length,
        "straight_line_px": straight,
        "tortuosity": tort,
        "n_encounters": n_enc,
        "frac_path_above_threshold": frac_above,
        "n_samples": int(eth_cov.size),
    }


def summarize_median_iqr(values):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], float)
    if v.size == 0:
        return {"median": None, "q1": None, "q3": None, "iqr": None, "n": 0}
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    return {"median": float(med), "q1": float(q1), "q3": float(q3),
            "iqr": float(q3 - q1), "n": int(v.size)}


# =========================================================================== #
#  HDF5 writer (exact contract)                                               #
# =========================================================================== #
def write_h5(fields, meta, global_Q, created_utc):
    import h5py

    def _ds(grp, name, arr, dtype=None):
        arr = np.asarray(arr)
        if dtype is not None:
            arr = arr.astype(dtype)
        kw = {}
        if arr.size >= 256 and np.issubdtype(arr.dtype, np.number):
            kw = dict(compression="gzip", compression_opts=4, shuffle=True)
        grp.create_dataset(name, data=arr, **kw)

    tmp = H5_OUT + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with h5py.File(tmp, "w") as f:
        f.attrs["source_aggregate_path"] = meta["aggregate_path"]
        f.attrs["schema_version"] = SCHEMA_VERSION
        f.attrs["arena_extent"] = np.asarray(pc.ARENA, float)  # [xmin,xmax,ymin,ymax]
        f.attrs["min_trials"] = MIN_TRIALS
        f.attrs["cleaning_global_Q"] = float(global_Q)
        f.attrs["cleaning_box"] = np.asarray(pc.ARENA, float)
        f.attrs["created_utc"] = created_utc
        f.attrs["generator"] = GENERATOR
        f.attrs["plume_common_version"] = pc.VERSION
        f.attrs["README"] = (
            "Odor fields per end-location. Datasets max/mean/min are masked (NaN) "
            "where a bin has <min_trials distinct contributing trials; count holds "
            "true distinct-trial counts. Axis convention: row = y bin, col = x bin, "
            "0-based; x_edges/y_edges are bin edges in px tiling arena_extent. "
            "endpoint = (x,y) px. track=head, signal=ethdeconv aligned to head clock."
        )
        f.attrs["build_complete"] = 0

        for g in LOC_ORDER:
            if g not in fields:
                continue
            fd = fields[g]
            grp = f.create_group(g)
            _ds(grp, "max", fd["max"], float)
            _ds(grp, "mean", fd["mean"], float)
            _ds(grp, "min", fd["min"], float)
            _ds(grp, "count", fd["count"], np.int64)
            _ds(grp, "x_edges", fd["x_edges"], float)
            _ds(grp, "y_edges", fd["y_edges"], float)
            _ds(grp, "endpoint", fd["endpoint"], float)
            grp.attrs["bin_size_px"] = int(fd["chosen_L"])
            grp.attrs["coverage_frac"] = float(fd["coverage_frac"])
            grp.attrs["n_trials"] = int(fd["n_trials"])
            grp.attrs["trial_indices"] = np.asarray(fd["trial_indices"], np.int64)
            grp.attrs["samples_total"] = int(fd["samples_total"])
            grp.attrs["track"] = "head"
            grp.attrs["signal"] = "ethdeconv"

        f.attrs["build_complete"] = 1  # set last, inside successful write

    os.replace(tmp, H5_OUT)
    log.info("Wrote HDF5 -> %s", H5_OUT)


# =========================================================================== #
#  Self-check before heavy compute                                            #
# =========================================================================== #
def self_check():
    # grid shape sanity
    xe, ye, nx, ny = grid_edges(40)
    assert nx == int(np.ceil(580 / 40)) and ny == int(np.ceil(280 / 40)), (nx, ny)
    assert xe[0] == 0.0 and ye[0] == 0.0
    # build_field on a tiny synthetic set -> not all NaN, correct masking
    xy1 = np.array([[10, 10], [10, 10]], float)
    samples = [(xy1, np.array([0.1, 0.2]))] * 3  # 3 trials -> bin becomes valid
    fd = build_field(samples, xe, ye)
    assert fd["count"][0, 0] == 3, fd["count"][0, 0]
    assert np.isfinite(fd["mean"][0, 0]), "valid bin should not be NaN"
    assert not np.all(np.isnan(fd["mean"])), "field all-NaN"
    # a 2-trial bin must be masked NaN in mean but count=2
    fd2 = build_field([(xy1, np.array([0.1, 0.2]))] * 2, xe, ye)
    assert fd2["count"][0, 0] == 2 and np.isnan(fd2["mean"][0, 0])
    log.info("self_check: PASS")


# =========================================================================== #
#  Main                                                                        #
# =========================================================================== #
def process_location(group, trs, Q, cutoff, cutoff_1x, cutoff_3x, cutoff_5x):
    """Build field + stats for one location group. Returns (field_dict, stats_dict)."""
    endpoint = pc.endpoint_of(trs[0])
    # collect cleaned head samples per trial
    per_trial = []
    for tr in trs:
        s = trial_head_samples(tr, Q)
        if s is None or s["xy"].shape[0] == 0:
            continue
        per_trial.append((tr, s))
    samples_list = [(s["xy"], s["eth"]) for (_tr, s) in per_trial]

    L, cov_frac, fallback, scan = choose_L(samples_list)
    x_edges, y_edges, nx, ny = grid_edges(L)
    field = build_field(samples_list, x_edges, y_edges)

    trial_indices = [int(tr["trial_index"]) for (tr, _s) in per_trial]

    fd = {
        "max": field["max"], "mean": field["mean"], "min": field["min"],
        "count": field["count"], "x_edges": x_edges, "y_edges": y_edges,
        "endpoint": endpoint, "chosen_L": L, "coverage_frac": cov_frac,
        "n_trials": len(per_trial), "trial_indices": trial_indices,
        "samples_total": field["samples_total"],
        "visited": field["visited"],
    }

    # ---- stats ----
    spars = sparseness_stats(field["mean"], field["count"],
                             cutoff_1x, cutoff_3x, cutoff_5x, cutoff,
                             n_samples_map=field["n_samples"])
    dist_mean = distance_stats(field["mean"], field["count"], endpoint,
                               x_edges, y_edges, cutoff, "mean")
    dist_max = distance_stats(field["max"], field["count"], endpoint,
                              x_edges, y_edges, cutoff, "max")

    # ---- trajectory per trial ----
    traj = []
    for (tr, s) in per_trial:
        animal = pc.animal_of(tr["file_name"])
        traj.append(trajectory_metrics(tr, s, cutoff, group, animal))
    tort = [m["tortuosity"] for m in traj]
    nenc = [m["n_encounters"] for m in traj]
    fabove = [m["frac_path_above_threshold"] for m in traj]

    traj_summary = {
        "path_length_px": summarize_median_iqr([m["path_length_px"] for m in traj]),
        "tortuosity": summarize_median_iqr(tort),
        "n_encounters": summarize_median_iqr(nenc),
        "frac_path_above_threshold": summarize_median_iqr(fabove),
        "spearman_tortuosity_vs_nencounters": spearman_ci(tort, nenc),
        "spearman_tortuosity_vs_frac_above": spearman_ci(tort, fabove),
    }

    # cleaning provenance per trial
    clean_prov = [
        {"trial_index": int(tr["trial_index"]),
         "n_total": s["n_total"], "n_after_box": s["n_after_box"],
         "n_after_dejump": s["n_after_dejump"], "n_after_coverage": s["n_after_coverage"]}
        for (tr, s) in per_trial
    ]

    stats = {
        "group": group,
        "n_trials": len(per_trial),
        "chosen_L": L,
        "L_fallback_used": bool(fallback),
        "coverage_frac": cov_frac,
        "L_scan": scan,
        "samples_total": field["samples_total"],
        "n_visited_bins": field["n_visited_bins"],
        "endpoint": endpoint.tolist(),
        "grid_shape": [int(ny), int(nx)],
        "sparseness": spars,
        "distance": {"mean": dist_mean, "max": dist_max},
        "trajectory_summary": traj_summary,
        "trajectory_per_trial": traj,
        "cleaning_provenance": clean_prov,
    }
    return fd, stats, per_trial


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    do_slice = "--slice" in argv

    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # logging: verbose -> file, short -> console
    for h in list(log.handlers):
        log.removeHandler(h)
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_OUT, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)

    np.random.seed(pc.SEED)
    log.info("=== build_odor_fields start (seed=%d, slice=%s) ===", pc.SEED, do_slice)

    # self-check BEFORE heavy compute
    self_check()

    # load + group + validate
    trials, meta = pc.load_trials()
    log.info("Loaded %d trials from %s", len(trials), meta["aggregate_path"])
    groups = pc.group_trials(trials)
    ginfo = pc.validate_groups(groups, warn=lambda m: log.warning(m))
    log.info("Groups: %s", {g: v["n"] for g, v in sorted(ginfo.items())})

    # global de-jump Q for HEAD (and one for BODY for the robustness check)
    Q_head = pc.pooled_dejump_Q(trials, "head")
    Q_body = pc.pooled_dejump_Q(trials, "body")
    log.info("Global dejump Q head=%.4f body=%.4f", Q_head, Q_body)

    # ---- pooled global MAD cutoff over ALL aligned ethdeconv samples ----
    all_eth = []
    for tr in trials:
        s = trial_head_samples(tr, Q_head)
        if s is not None and s["eth"].size:
            all_eth.append(s["eth"])
    all_eth = np.concatenate(all_eth) if all_eth else np.array([])
    global_mad = pc.mad(all_eth)
    cutoff_1x = global_mad
    cutoff_3x = 3.0 * global_mad
    cutoff_5x = 5.0 * global_mad
    cutoff = max(cutoff_3x, SMALL_FLOOR)
    log.info("Global MAD=%.6g  cutoff(=max(3MAD,%.g))=%.6g", global_mad, SMALL_FLOOR, cutoff)

    order = LOC_ORDER[:]
    if do_slice:
        order = ["Loc1", "Loc2"]
        log.info("SLICE mode: only %s", order)

    fields = {}
    stats_all = {"_meta": {
        "generator": GENERATOR, "plume_common_version": pc.VERSION,
        "schema_version": SCHEMA_VERSION,
        "aggregate_path": meta["aggregate_path"], "aggregate_schema": meta["schema_version"],
        "Fs": meta["Fs"], "seed": pc.SEED,
        "global_dejump_Q_head": float(Q_head), "global_dejump_Q_body": float(Q_body),
        "cleaning_box": list(pc.ARENA),
        "global_MAD_ethdeconv": float(global_mad),
        "cutoff": float(cutoff), "cutoff_1xMAD": float(cutoff_1x),
        "cutoff_3xMAD": float(cutoff_3x), "cutoff_5xMAD": float(cutoff_5x),
        "small_floor": SMALL_FLOOR, "min_trials": MIN_TRIALS,
        "L_scan_values": L_SCAN, "coverage_target": COVERAGE_TARGET,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "arena_extent": list(pc.ARENA),
    }, "locations": {}}

    # per-trial store for pooled trajectory + head/body robustness
    pooled_head_per_trial = []  # (tr, samp) for Loc1-6

    for g in order:
        if g not in groups:
            log.warning("group %s absent; skipping", g)
            continue
        try:
            log.info("--- processing %s (n=%d) ---", g, len(groups[g]))
            fd, st, per_trial = process_location(
                g, groups[g], Q_head, cutoff, cutoff_1x, cutoff_3x, cutoff_5x)
            fields[g] = fd
            stats_all["locations"][g] = st
            log.info("%s: L=%s cov=%.3f n=%d samples=%d visited=%d",
                     g, fd["chosen_L"], fd["coverage_frac"], fd["n_trials"],
                     fd["samples_total"], st["n_visited_bins"])
            if g in POOLED_LOCS:
                pooled_head_per_trial.extend(per_trial)
        except Exception as e:  # noqa: BLE001
            log.exception("FAILED processing %s: %s", g, e)
            continue

    # =================== POOLED (Loc1-6) ===================
    pooled_stats = None
    pooled_field_mean_head = None
    if not do_slice and pooled_head_per_trial:
        try:
            log.info("--- processing POOLED (Loc1-6) ---")
            # choose L over pooled samples; use pooled 'endpoint' = NaN (mixed),
            # so distance uses each bin center to... pooled has no single endpoint.
            # Per plan: distance dependence for pooled uses each bin->endpoint of its
            # own location is undefined when pooled. We follow: pooled distance uses
            # the nearest strategy? PLAN says "per location and pooled" distance fit.
            # For pooled we compute distance from each bin center to the *pooled*
            # centroid of the 6 endpoints (documented).
            samples_list = [(s["xy"], s["eth"]) for (_tr, s) in pooled_head_per_trial]
            L, cov_frac, fallback, scan = choose_L(samples_list)
            x_edges, y_edges, nx, ny = grid_edges(L)
            field = build_field(samples_list, x_edges, y_edges)
            pooled_field_mean_head = field["mean"]

            eps = np.array([pc.endpoint_of(tr) for (tr, _s) in pooled_head_per_trial])
            pooled_centroid = eps.mean(0)

            spars = sparseness_stats(field["mean"], field["count"],
                                     cutoff_1x, cutoff_3x, cutoff_5x, cutoff,
                                     n_samples_map=field["n_samples"])
            dist_mean = distance_stats(field["mean"], field["count"], pooled_centroid,
                                       x_edges, y_edges, cutoff, "mean")
            dist_max = distance_stats(field["max"], field["count"], pooled_centroid,
                                      x_edges, y_edges, cutoff, "max")

            traj = []
            for (tr, s) in pooled_head_per_trial:
                animal = pc.animal_of(tr["file_name"])
                traj.append(trajectory_metrics(tr, s, cutoff, pc.group_of(tr["file_name"]), animal))
            tort = [m["tortuosity"] for m in traj]
            nenc = [m["n_encounters"] for m in traj]
            fabove = [m["frac_path_above_threshold"] for m in traj]
            traj_summary = {
                "path_length_px": summarize_median_iqr([m["path_length_px"] for m in traj]),
                "tortuosity": summarize_median_iqr(tort),
                "n_encounters": summarize_median_iqr(nenc),
                "frac_path_above_threshold": summarize_median_iqr(fabove),
                "spearman_tortuosity_vs_nencounters": spearman_ci(tort, nenc),
                "spearman_tortuosity_vs_frac_above": spearman_ci(tort, fabove),
            }

            pooled_stats = {
                "group": "pooled_Loc1-6",
                "n_trials": len(pooled_head_per_trial),
                "chosen_L": L, "L_fallback_used": bool(fallback),
                "coverage_frac": cov_frac, "L_scan": scan,
                "samples_total": field["samples_total"],
                "n_visited_bins": field["n_visited_bins"],
                "endpoint_centroid": pooled_centroid.tolist(),
                "grid_shape": [int(ny), int(nx)],
                "sparseness": spars,
                "distance": {"mean": dist_mean, "max": dist_max,
                             "note": "distance measured to centroid of the 6 endpoints"},
                "trajectory_summary": traj_summary,
                "trajectory_per_trial": traj,
            }
            stats_all["pooled"] = pooled_stats
            log.info("POOLED: L=%s cov=%.3f n=%d samples=%d",
                     L, cov_frac, len(pooled_head_per_trial), field["samples_total"])

            # ---- robustness §3.2: body field on SAME grid, ethdeconv->BODY clock ----
            body_samples = []
            for (tr, _s) in pooled_head_per_trial:
                bs = trial_body_samples(tr, Q_body)
                if bs is not None and bs["xy"].shape[0] > 0:
                    body_samples.append((bs["xy"], bs["eth"]))
            body_field = build_field(body_samples, x_edges, y_edges)
            r, n_common = pearson_nan(pooled_field_mean_head, body_field["mean"])
            stats_all["robustness_head_vs_body"] = {
                "pearson_r": r, "n_common_valid_bins": n_common,
                "grid_L": L, "track_body_clock": "body_time",
                "note": ("Pooled Loc1-6 mean field, head track vs body track "
                         "(ethdeconv aligned to body clock), same grid; "
                         "nan-aware Pearson over bins valid in both."),
            }
            log.info("robustness head-vs-body Pearson r=%s (n=%d bins)", r, n_common)
        except Exception as e:  # noqa: BLE001
            log.exception("FAILED pooled/robustness: %s", e)

    # =================== write outputs ===================
    created_utc = stats_all["_meta"]["created_utc"]
    write_h5(fields, meta, Q_head, created_utc)

    # JSON stats (atomic)
    tmp_json = STATS_OUT + ".tmp"
    with open(tmp_json, "w", encoding="utf-8") as fjson:
        json.dump(_jsonable(stats_all), fjson, indent=2)
    os.replace(tmp_json, STATS_OUT)
    log.info("Wrote stats -> %s", STATS_OUT)

    # ---- short console summary ----
    print("build_odor_fields: DONE (slice=%s)" % do_slice)
    print("  h5   :", H5_OUT)
    print("  stats:", STATS_OUT)
    print("  log  :", LOG_OUT)
    print("  global MAD=%.6g  cutoff=%.6g  Q_head=%.3f" % (global_mad, cutoff, Q_head))
    for g in order:
        if g in stats_all["locations"]:
            s = stats_all["locations"][g]
            fb = " (FALLBACK)" if s["L_fallback_used"] else ""
            print("  %-11s L=%2d cov=%.3f n=%2d visited=%3d%s" %
                  (g, s["chosen_L"], s["coverage_frac"], s["n_trials"],
                   s["n_visited_bins"], fb))
    if pooled_stats is not None:
        print("  %-11s L=%2d cov=%.3f n=%2d" %
              ("pooled", pooled_stats["chosen_L"], pooled_stats["coverage_frac"],
               pooled_stats["n_trials"]))
    if "robustness_head_vs_body" in stats_all:
        print("  head-vs-body Pearson r =",
              stats_all["robustness_head_vs_body"]["pearson_r"])
    log.info("=== build_odor_fields done ===")


if __name__ == "__main__":
    main()
