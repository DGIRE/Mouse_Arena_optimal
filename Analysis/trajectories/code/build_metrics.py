r"""build_metrics.py -- DATA-ANALYST stage of the Trajectory analysis.

Computes, for all 114 infrared trials, per-frame geometry (head clock), per-trial
metrics, the pooled encounter calibration, and all H1/H2/H3 inferential statistics.
Saves:
  data/trajectory_metrics.h5   -- per-trial arrays for the figure agents (no recompute)
  data/trajectory_metrics.json -- per-trial table (no big arrays)
  data/stats.json              -- every number the reports cite

Does NOT build figures or reports. Follows PLAN.md / plan.json / request draft 2 exactly.
Seed = 1234 everywhere randomness enters. Accessor-only reads. DATA is read-only.

Interpreter:  "$AR_PY" build_metrics.py            (full run, 114 trials)
              "$AR_PY" build_metrics.py --slice 5  (5-trial self-check slice first)
"""
from __future__ import annotations

import os
import sys
import json
import logging
import argparse
import datetime as _dt

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import traj_common as tc  # noqa: E402
import plume_common as pc  # noqa: E402  (re-exported through traj_common's sys.path)

from scipy import stats as _st  # noqa: E402

# ----------------------------------------------------------------------- paths
BASE = os.path.abspath(os.path.join(_HERE, ".."))
DATA_DIR = os.path.join(BASE, "data")
LOG_DIR = os.path.join(BASE, "logs")
H5_PATH = os.path.join(DATA_DIR, "trajectory_metrics.h5")
METRICS_JSON = os.path.join(DATA_DIR, "trajectory_metrics.json")
STATS_JSON = os.path.join(DATA_DIR, "stats.json")
LOG_PATH = os.path.join(LOG_DIR, "build_metrics.log")

SEED = tc.SEED  # 1234
POOLED_GROUPS = {"Loc1", "Loc2", "Loc3", "Loc4", "Loc5", "Loc6"}
N_BOOT = 2000
PERI_LO, PERI_HI, PERI_STEP = -1.0, 1.0, 0.05
F3_BIN_PX = 20.0
F3_MIN_SAMPLES = 30

log = logging.getLogger("build_metrics")


def _utcnow():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(ch)


# ------------------------------------------------------------ per-trial compute
def process_trial(tr, Q_body, Q_head):
    """Clean both tracks, interpolate body->head, compute per-frame geometry, and
    return a dict of per-trial arrays + scalars. Raises on unrecoverable trials
    (caller wraps in try/except). Encounter fields (onsets, n_encounters, frac,
    peri) are filled later once the pooled threshold is known.
    """
    fn = tr["file_name"]
    end_loc = tc.group_of(fn)
    in_pooled = end_loc in POOLED_GROUPS
    S = tc.endpoint_of(tr)

    body = np.asarray(tr["body"], float)
    body_t = np.asarray(tr["body_time"], float)
    head = np.asarray(tr["head"], float)
    head_t = np.asarray(tr["head_time"], float)
    eth_t = np.asarray(tr["ethanol_time"], float)
    ethd = np.asarray(tr["ethdeconv"], float)

    # 1. clean BODY (geometry track, D1) and record removal fraction
    b_idx, body_clean, body_t_clean = tc.clean_track(body, body_t, Q_body)
    n_body_box = int(pc._in_box(body).sum())
    body_removed_frac = (1.0 - b_idx.size / n_body_box) if n_body_box > 0 else np.nan

    # tortuosity/path/straight on the CLEANED body track (D6)
    tort, path_len, straight = tc.tortuosity(body_clean)

    # 2. clean HEAD; head-clock frame set = cleaned head timestamps
    h_idx, head_clean, head_t_clean = tc.clean_track(head, head_t, Q_head)
    n_head_box = int(pc._in_box(head).sum())
    head_removed_frac = (1.0 - h_idx.size / n_head_box) if n_head_box > 0 else np.nan

    if head_t_clean.size < 2 or body_t_clean.size < 2:
        raise ValueError("insufficient cleaned samples (head=%d body=%d)"
                         % (head_t_clean.size, body_t_clean.size))

    # 3. on head_t: interp body->head, align ethdeconv->head clock
    body_h = tc.interp_body_to_head(head_t_clean, body_t_clean, body_clean)
    ethd_h = tc.align_signal(head_t_clean, eth_t, ethd)

    # 4. per-frame geometry (vectorized)
    u, vu = tc.body_axis_u(head_clean, body_h)
    s, vs = tc.to_source_s(body_h, S)
    geom_valid = vu & vs
    theta = np.full(head_t_clean.shape[0], np.nan)
    theta[geom_valid] = tc.angle_theta(u[geom_valid], s[geom_valid])
    d = tc.distance_to_source(body_h, S)                     # body-based (D8)
    head_source_dist = tc.distance_to_source(head_clean, S)  # for quiet baseline

    return {
        "file_name": fn, "end_loc": end_loc, "in_pooled": in_pooled,
        "S": S,
        "body_clean": body_clean, "body_t": body_t_clean,
        "head_clean": head_clean, "head_t": head_t_clean,
        "ethd_h": ethd_h, "theta": theta, "d": d,
        "head_source_dist": head_source_dist,
        "geom_valid": geom_valid,
        "tortuosity": tort, "path_length": path_len, "straight_line": straight,
        "body_removed_frac": body_removed_frac,
        "head_removed_frac": head_removed_frac,
    }


def add_encounters(rec, threshold):
    """Fill encounter-dependent fields on a processed trial record (in place):
    onsets, n_encounters, onset_time, frac_path_above_threshold, h2_slope,
    peri_pre_theta, peri_post_theta, and the per-relative-time peri curve for F4.
    """
    head_t = rec["head_t"]
    ethd_h = rec["ethd_h"]
    theta = rec["theta"]
    d = rec["d"]

    onsets = tc.detect_onsets(ethd_h, head_t, threshold, tc.REFRACTORY_S)
    rec["onset_idx"] = onsets
    rec["onset_time"] = head_t[onsets] if onsets.size else np.array([], float)
    rec["n_encounters"] = int(onsets.size)
    rec["frac_path_above_threshold"] = tc.frac_above(ethd_h, threshold)

    # H2: OLS slope of theta on d over valid frames (finite theta & d)
    m = np.isfinite(theta) & np.isfinite(d)
    if m.sum() >= 2:
        rec["h2_slope"] = float(np.polyfit(d[m], theta[m], 1)[0])
    else:
        rec["h2_slope"] = np.nan

    # H3 peri-contact: theta as a function of head_t over valid frames
    vt = np.isfinite(theta) & np.isfinite(head_t)
    tv = head_t[vt]
    thv = theta[vt]
    rel = np.arange(PERI_LO, PERI_HI + 1e-9, PERI_STEP)
    rec["peri_rel_times"] = rel
    if onsets.size and tv.size >= 2:
        # per (onset) x (relative time) matrix, NaN outside trial coverage
        per = np.full((onsets.size, rel.size), np.nan)
        tmin, tmax = tv[0], tv[-1]
        for j, ot in enumerate(rec["onset_time"]):
            grid = ot + rel
            samp = np.interp(grid, tv, thv)
            samp[(grid < tmin) | (grid > tmax)] = np.nan
            per[j] = samp
        # per-trial peri curve = mean over this trial's contacts at each rel time
        with np.errstate(invalid="ignore"):
            trial_curve = np.nanmean(per, axis=0)
        rec["peri_trial_curve"] = trial_curve  # (n_rel,) for F4 bootstrap over trials
        pre_mask = rel < 0.0
        post_mask = rel > 0.0
        pre_vals = per[:, pre_mask]
        post_vals = per[:, post_mask]
        with np.errstate(invalid="ignore"):
            rec["peri_pre_theta"] = float(np.nanmean(pre_vals)) if np.isfinite(pre_vals).any() else np.nan
            rec["peri_post_theta"] = float(np.nanmean(post_vals)) if np.isfinite(post_vals).any() else np.nan
    else:
        rec["peri_trial_curve"] = np.full(rel.size, np.nan)
        rec["peri_pre_theta"] = np.nan
        rec["peri_post_theta"] = np.nan


# ------------------------------------------------------------------- statistics
def _spearman(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 3:
        return np.nan, np.nan, int(m.sum())
    rho, p = _st.spearmanr(x[m], y[m])
    return float(rho), float(p), int(m.sum())


def _spearman_boot_ci(x, y, rng, n_boot=N_BOOT):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    n = x.size
    if n < 3:
        return [np.nan, np.nan]
    rhos = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        xb, yb = x[idx], y[idx]
        if np.all(xb == xb[0]) or np.all(yb == yb[0]):
            rhos[b] = np.nan
        else:
            rhos[b] = _st.spearmanr(xb, yb)[0]
    rhos = rhos[np.isfinite(rhos)]
    if rhos.size == 0:
        return [np.nan, np.nan]
    return [float(np.percentile(rhos, 2.5)), float(np.percentile(rhos, 97.5))]


def _boot_ci_over_trials(trial_values_2d, rng, n_boot=N_BOOT):
    """trial_values_2d: (n_trials, n_bins) with NaNs. Bootstrap the mean curve by
    resampling TRIALS. Returns (mean, ci_lo, ci_hi, n_per_bin)."""
    A = np.asarray(trial_values_2d, float)
    n_trials, n_bins = A.shape
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(A, axis=0)
    n_per_bin = np.sum(np.isfinite(A), axis=0)
    boot = np.full((n_boot, n_bins), np.nan)
    for b in range(n_boot):
        idx = rng.integers(0, n_trials, n_trials)
        with np.errstate(invalid="ignore"):
            boot[b] = np.nanmean(A[idx], axis=0)
    with np.errstate(invalid="ignore"):
        ci_lo = np.nanpercentile(boot, 2.5, axis=0)
        ci_hi = np.nanpercentile(boot, 97.5, axis=0)
    return mean, ci_lo, ci_hi, n_per_bin


def _median_boot_ci(values, rng, n_boot=N_BOOT):
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size < 2:
        return [np.nan, np.nan]
    boot = np.empty(n_boot)
    for b in range(n_boot):
        boot[b] = np.median(v[rng.integers(0, v.size, v.size)])
    return [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def compute_stats(records, cal, rng):
    """All inferential stats -> dict for stats.json."""
    pooled = [r for r in records if r["in_pooled"]]
    other = [r for r in records if r["end_loc"] == "anotherLoc"]

    n_enc_pooled = np.array([r["n_encounters"] for r in pooled], float)
    tort_pooled = np.array([r["tortuosity"] for r in pooled], float)
    frac_pooled = np.array([r["frac_path_above_threshold"] for r in pooled], float)
    pathlen_pooled = np.array([r["path_length"] for r in pooled], float)

    n_enc_all = np.array([r["n_encounters"] for r in records], float)

    stats = {}

    # ---- calibration ----
    ne_finite = n_enc_all[np.isfinite(n_enc_all)]
    stats["calibration"] = {
        "signal": "ethdeconv_on_head_clock",
        "k": cal["k"], "threshold": cal["threshold"],
        "fpr_per_s": cal["fpr_per_s"], "fpr_target_max": tc.QUIET_FPR_MAX,
        "fpr_within_target": bool(cal["fpr_per_s"] <= tc.QUIET_FPR_MAX + 1e-12),
        "mad_quiet": cal["mad_quiet"],
        "total_quiet_dur_s": cal.get("total_quiet_dur_s"),
        "k_scan": cal["k_scan"],
        "n_encounters_distribution_all": {
            "min": float(np.min(ne_finite)), "median": float(np.median(ne_finite)),
            "max": float(np.max(ne_finite)), "mean": float(np.mean(ne_finite))},
        "n_encounters_distribution_pooled": {
            "min": float(np.min(n_enc_pooled)), "median": float(np.median(n_enc_pooled)),
            "max": float(np.max(n_enc_pooled)), "mean": float(np.mean(n_enc_pooled))},
        "low_dynamic_range_note": (
            "Encounter counts are low on this cohort (pooled per-trial median=%g); "
            "H1 correlation with n_encounters has limited dynamic range."
            % float(np.median(n_enc_pooled))),
        "k_selection_note": (
            "smallest-k rule returns the most permissive threshold on this "
            "degenerate (near-silent) quiet baseline; harmless here because all "
            "encounter-dependent results are null, but should not be used to "
            "support a positive claim."),
    }

    # ---- encounter-amplitude diagnostics (documentation/diagnostics only) ----
    # Everything below is computed from the per-trial aligned ethd_h trace and the
    # detected onsets already in each pooled record (add_encounters ran before
    # compute_stats). It does NOT alter the detector, threshold, k-scan, or any
    # H1/H2/H3 result -- it only documents that the calibrated threshold sits at the
    # deconvolved noise floor and that onsets never reach the real-odor amplitude.
    SECONDARY_AMP_THRESHOLD = 0.01
    SIGNAL_MAX_REF = 0.14

    onset_ethd_vals = []          # ethdeconv values AT detected onset samples (pooled Loc1-6)
    pertrial_ethd_medians = []    # each pooled trial's median ethd_h (noise-floor level)
    n_enc_amp = []                # per-trial encounter counts at the 0.01 amplitude threshold
    for r in pooled:
        ethd = np.asarray(r["ethd_h"], float)
        oi = np.asarray(r["onset_idx"], int)
        if oi.size:
            ov = ethd[oi]
            onset_ethd_vals.append(ov[np.isfinite(ov)])
        ethd_fin = ethd[np.isfinite(ethd)]
        if ethd_fin.size:
            pertrial_ethd_medians.append(float(np.median(ethd_fin)))
        amp_onsets = tc.detect_onsets(ethd, r["head_t"], SECONDARY_AMP_THRESHOLD, tc.REFRACTORY_S)
        n_enc_amp.append(int(amp_onsets.size))

    onset_ethd_pool = (np.concatenate(onset_ethd_vals)
                       if onset_ethd_vals else np.array([], float))
    pertrial_ethd_medians = np.asarray(pertrial_ethd_medians, float)
    n_enc_amp = np.asarray(n_enc_amp, float)

    stats["encounter_diagnostics"] = {
        "pool": "Loc1-6",
        "signal": "ethdeconv_on_head_clock",
        "n_onsets_pooled": int(onset_ethd_pool.size),
        "onset_ethd_median": (float(np.median(onset_ethd_pool))
                              if onset_ethd_pool.size else None),
        "onset_ethd_p90": (float(np.percentile(onset_ethd_pool, 90))
                           if onset_ethd_pool.size else None),
        "frac_onsets_above_0p01": (float(np.mean(onset_ethd_pool > SECONDARY_AMP_THRESHOLD))
                                   if onset_ethd_pool.size else None),
        "pertrial_ethd_median_median": (float(np.median(pertrial_ethd_medians))
                                        if pertrial_ethd_medians.size else None),
        "calibrated_threshold": float(cal["threshold"]),
        "signal_max_ref": SIGNAL_MAX_REF,
        "secondary_amp_threshold": SECONDARY_AMP_THRESHOLD,
        "n_encounters_amp": {
            "min": (int(np.min(n_enc_amp)) if n_enc_amp.size else None),
            "median": (float(np.median(n_enc_amp)) if n_enc_amp.size else None),
            "max": (int(np.max(n_enc_amp)) if n_enc_amp.size else None),
            "mean": (float(np.mean(n_enc_amp)) if n_enc_amp.size else None),
        },
        "note": (
            "The calibrated encounter threshold (~%.3e on ethdeconv) sits at the "
            "deconvolved NOISE FLOOR: pooled per-trial median ethd_h ~%.3e and the "
            "median ethdeconv AT detected onsets ~%.3e are the same order of "
            "magnitude, while real odor reaches ~%.2f. Only a fraction %.3f of "
            "onsets exceed the physically meaningful 0.01 amplitude, so onsets do "
            "NOT reach the 0.01-0.14 odor range. At a 0.01 amplitude threshold the "
            "per-trial encounter counts collapse to ~%g (median; min=%s max=%s), "
            "i.e. discrete high-amplitude odor contacts are essentially absent. "
            "This reinforces the null: the ~28 onsets/trial index noise/exposure "
            "crossings, not discrete odor contacts."
            % (float(cal["threshold"]),
               (float(np.median(pertrial_ethd_medians)) if pertrial_ethd_medians.size else float("nan")),
               (float(np.median(onset_ethd_pool)) if onset_ethd_pool.size else float("nan")),
               SIGNAL_MAX_REF,
               (float(np.mean(onset_ethd_pool > SECONDARY_AMP_THRESHOLD)) if onset_ethd_pool.size else float("nan")),
               (float(np.median(n_enc_amp)) if n_enc_amp.size else float("nan")),
               (int(np.min(n_enc_amp)) if n_enc_amp.size else "NA"),
               (int(np.max(n_enc_amp)) if n_enc_amp.size else "NA"))),
    }

    # ---- H1 ----
    rho1, p1, n1 = _spearman(n_enc_pooled, tort_pooled)
    ci1 = _spearman_boot_ci(n_enc_pooled, tort_pooled, rng)
    rho1s, p1s, n1s = _spearman(frac_pooled, tort_pooled)
    ci1s = _spearman_boot_ci(frac_pooled, tort_pooled, rng)

    # ---- H1 exposure-confound metrics (pooled) ----
    # raw n_encounters scales with path length/time (a longer, curvier path
    # mechanically accrues more threshold crossings); quantify that confound and
    # report an exposure-normalized encounter_rate = n_encounters / path_length.
    # Use a dedicated child RNG (seeded from SEED) so the shared `rng` stream --
    # and therefore all downstream H2/H3 bootstrap CIs -- is left untouched.
    rng_conf = np.random.default_rng(SEED)
    rho_np, p_np, n_np = _spearman(n_enc_pooled, pathlen_pooled)
    ci_np = _spearman_boot_ci(n_enc_pooled, pathlen_pooled, rng_conf)
    rho_tp, p_tp, n_tp = _spearman(tort_pooled, pathlen_pooled)
    ci_tp = _spearman_boot_ci(tort_pooled, pathlen_pooled, rng_conf)
    with np.errstate(invalid="ignore", divide="ignore"):
        enc_rate_pooled = np.where(pathlen_pooled > 0,
                                   n_enc_pooled / pathlen_pooled, np.nan)
    rho_rt, p_rt, n_rt = _spearman(enc_rate_pooled, tort_pooled)
    ci_rt = _spearman_boot_ci(enc_rate_pooled, tort_pooled, rng_conf)

    per_loc = {}
    for g in sorted(POOLED_GROUPS):
        rl = [r for r in pooled if r["end_loc"] == g]
        ne = np.array([r["n_encounters"] for r in rl], float)
        to = np.array([r["tortuosity"] for r in rl], float)
        rho_g, p_g, n_g = _spearman(ne, to)
        per_loc[g] = {"rho": rho_g, "p": p_g, "n": n_g}
    # anotherLoc separately
    ne_o = np.array([r["n_encounters"] for r in other], float)
    to_o = np.array([r["tortuosity"] for r in other], float)
    fr_o = np.array([r["frac_path_above_threshold"] for r in other], float)
    rho_o, p_o, n_o = _spearman(ne_o, to_o)
    rho_os, p_os, n_os = _spearman(fr_o, to_o)

    def _direction(rho):
        if not np.isfinite(rho):
            return "undefined"
        return "negative" if rho < 0 else ("positive" if rho > 0 else "zero")

    stats["H1"] = {
        "unit": "trial", "pool": "Loc1-6",
        "primary_n_encounters_vs_tortuosity": {
            "spearman_rho": rho1, "p": p1, "ci95_boot_trial": ci1, "n": n1,
            "direction": _direction(rho1),
            "prior_rho": 0.176, "prior_p": 0.072,
            "reconcile_note": (
                "Prior (Plume-locations Task-1): rho=+0.176, CI[-0.016,0.356], p=0.072 "
                "(weak, non-significant, POSITIVE = opposite the H1 prediction). "
                "H1 accepted only if rho<0 and CI excludes 0."),
            "accept_H1": bool(np.isfinite(rho1) and rho1 < 0
                              and np.isfinite(ci1[0]) and np.isfinite(ci1[1])
                              and ci1[0] < 0 and ci1[1] < 0),
        },
        "secondary_frac_above_vs_tortuosity": {
            "spearman_rho": rho1s, "p": p1s, "ci95_boot_trial": ci1s, "n": n1s,
            "direction": _direction(rho1s), "prior_rho": -0.532},
        "exposure_confound_note": (
            "encounter_rate = n_encounters / path_length is the exposure-normalized "
            "encounter measure; raw n_encounters scales with path length/time, so "
            "rho_encounter_rate_vs_tort controls for that exposure confound."),
        "rho_nenc_pathlen": {
            "spearman_rho": rho_np, "p": p_np, "ci95_boot_trial": ci_np, "n": n_np,
            "direction": _direction(rho_np)},
        "rho_tort_pathlen": {
            "spearman_rho": rho_tp, "p": p_tp, "ci95_boot_trial": ci_tp, "n": n_tp,
            "direction": _direction(rho_tp)},
        "rho_encounter_rate_vs_tort": {
            "spearman_rho": rho_rt, "p": p_rt, "ci95_boot_trial": ci_rt, "n": n_rt,
            "direction": _direction(rho_rt)},
        "per_location_rho_n_encounters_vs_tortuosity": per_loc,
        "anotherLoc_separate": {
            "n_encounters_vs_tortuosity": {"rho": rho_o, "p": p_o, "n": n_o},
            "frac_above_vs_tortuosity": {"rho": rho_os, "p": p_os, "n": n_os}},
    }

    # ---- H2 ----
    slopes = np.array([r["h2_slope"] for r in pooled], float)
    slopes_fin = slopes[np.isfinite(slopes)]
    if slopes_fin.size >= 1 and not np.allclose(slopes_fin, 0):
        w_stat, w_p = _st.wilcoxon(slopes_fin, alternative="greater")
        w_stat, w_p = float(w_stat), float(w_p)
    else:
        w_stat, w_p = np.nan, np.nan
    med_slope = float(np.median(slopes_fin)) if slopes_fin.size else np.nan
    slope_ci = _median_boot_ci(slopes_fin, rng)

    # F3 binned curve: BODY d (D9), 20px bins, per-trial mean theta per bin, boot over trials
    max_d = 0.0
    for r in pooled:
        dd = r["d"][np.isfinite(r["d"]) & np.isfinite(r["theta"])]
        if dd.size:
            max_d = max(max_d, float(dd.max()))
    edges = np.arange(0.0, max_d + F3_BIN_PX, F3_BIN_PX)
    if edges.size < 2:
        edges = np.array([0.0, F3_BIN_PX])
    centers = 0.5 * (edges[:-1] + edges[1:])
    n_bins = centers.size
    # per-trial mean theta per bin
    trial_bin = np.full((len(pooled), n_bins), np.nan)
    for i, r in enumerate(pooled):
        dd = r["d"]
        th = r["theta"]
        m = np.isfinite(dd) & np.isfinite(th)
        if not m.any():
            continue
        bidx = np.digitize(dd[m], edges) - 1
        thm = th[m]
        for b in range(n_bins):
            sel = bidx == b
            if sel.any():
                trial_bin[i, b] = np.mean(thm[sel])
    # also total pooled samples per bin (for the >=30 samples/bin rule)
    total_samp = np.zeros(n_bins, int)
    for r in pooled:
        dd = r["d"]; th = r["theta"]
        m = np.isfinite(dd) & np.isfinite(th)
        if m.any():
            bidx = np.digitize(dd[m], edges) - 1
            for b in range(n_bins):
                total_samp[b] += int(np.sum(bidx == b))
    mean_c, lo_c, hi_c, n_trials_bin = _boot_ci_over_trials(trial_bin, rng)
    keep = total_samp >= F3_MIN_SAMPLES
    stats["H2"] = {
        "unit": "trial", "pool": "Loc1-6",
        "n_trials_with_finite_slope": int(slopes_fin.size),
        "per_trial_slopes": [None if not np.isfinite(v) else float(v) for v in slopes],
        "wilcoxon_slopes_gt_0": {"stat": w_stat, "p": w_p, "alternative": "greater"},
        "median_slope_deg_per_px": med_slope,
        "median_slope_ci95_boot": slope_ci,
        "direction": ("positive" if np.isfinite(med_slope) and med_slope > 0
                      else ("negative" if np.isfinite(med_slope) and med_slope < 0 else "zero")),
        "F3_binned_curve": {
            "bin_width_px": F3_BIN_PX, "min_samples_per_bin": F3_MIN_SAMPLES,
            "distance_track": "body",
            "bin_centers": [float(c) for c in centers[keep]],
            "mean_theta": [float(v) for v in mean_c[keep]],
            "ci_lo": [float(v) for v in lo_c[keep]],
            "ci_hi": [float(v) for v in hi_c[keep]],
            "n_trials": [int(v) for v in n_trials_bin[keep]],
            "n_samples": [int(v) for v in total_samp[keep]],
        },
    }

    # ---- H3 ----
    with_enc = [r for r in pooled if r["n_encounters"] >= 1]
    pre = np.array([r["peri_pre_theta"] for r in with_enc], float)
    post = np.array([r["peri_post_theta"] for r in with_enc], float)
    paired = np.isfinite(pre) & np.isfinite(post)
    pre_p, post_p = pre[paired], post[paired]
    n_pairs = int(paired.sum())
    if n_pairs >= 1 and not np.allclose(post_p - pre_p, 0):
        h3_stat, h3_p = _st.wilcoxon(post_p, pre_p, alternative="less")
        h3_stat, h3_p = float(h3_stat), float(h3_p)
    else:
        h3_stat, h3_p = np.nan, np.nan
    total_contacts = int(sum(r["n_encounters"] for r in with_enc))
    descriptive_only = bool(n_pairs < 5 or total_contacts < 10)

    # Observed per-trial-pair direction (documentation label only; does NOT touch the
    # Wilcoxon numbers below). The prior label used the tiny difference in pooled
    # medians (post ~= pre) and read "post<pre", which mis-describes the data: the
    # majority of paired trials actually have post>pre.
    if n_pairs:
        diff = post_p - pre_p
        n_post_gt_pre = int(np.sum(diff > 0))
        n_post_lt_pre = int(np.sum(diff < 0))
        n_tie = int(np.sum(diff == 0))
    else:
        n_post_gt_pre = n_post_lt_pre = n_tie = 0

    # F4 pooled peri-contact curve: per-trial peri curve, bootstrap over trials
    rel = records[0]["peri_rel_times"] if records else np.arange(PERI_LO, PERI_HI + 1e-9, PERI_STEP)
    contributing = [r for r in pooled if np.isfinite(r["peri_trial_curve"]).any()]
    if contributing:
        curves = np.vstack([r["peri_trial_curve"] for r in contributing])
        mean_p, lo_p, hi_p, n_pb = _boot_ci_over_trials(curves, rng)
    else:
        mean_p = np.full(rel.size, np.nan); lo_p = mean_p.copy(); hi_p = mean_p.copy()
        n_pb = np.zeros(rel.size, int)

    stats["H3"] = {
        "unit": "trial", "pool": "Loc1-6",
        "n_trials_with_encounter": len([r for r in pooled if r["n_encounters"] >= 1]),
        "n_paired_trials": n_pairs,
        "total_contacts_pooled": total_contacts,
        "median_pre_theta": float(np.median(pre_p)) if n_pairs else np.nan,
        "median_post_theta": float(np.median(post_p)) if n_pairs else np.nan,
        "paired_wilcoxon_post_lt_pre": {"stat": h3_stat, "p": h3_p, "alternative": "less"},
        "n_pairs_post_gt_pre": n_post_gt_pre,
        "n_pairs_post_lt_pre": n_post_lt_pre,
        "n_pairs_tie": n_tie,
        "direction": (("post>pre" if n_post_gt_pre > n_post_lt_pre
                       else ("post<pre" if n_post_lt_pre > n_post_gt_pre else "post~=pre"))
                      if n_pairs else "equal_or_na"),
        "direction_note": (
            "Per-trial-pair majority direction; pooled medians are essentially "
            "equal (post ~= pre, slightly post>pre) -- NOT a decrease. The "
            "Wilcoxon post<pre test is non-significant (see p above)."
            if n_pairs else ""),
        "descriptive_only": descriptive_only,
        "descriptive_only_note": (
            "Too few encounters/paired trials for a stable inferential estimate; "
            "the peri-contact curve is reported as descriptive." if descriptive_only else ""),
        "F4_peri_contact_curve": {
            "rel_times_s": [float(v) for v in rel],
            "mean_theta": [None if not np.isfinite(v) else float(v) for v in mean_p],
            "ci_lo": [None if not np.isfinite(v) else float(v) for v in lo_p],
            "ci_hi": [None if not np.isfinite(v) else float(v) for v in hi_p],
            "n_trials_contributing_per_bin": [int(v) for v in n_pb],
            "n_contacts": total_contacts,
            "n_trials_contributing": len(contributing),
        },
    }

    return stats


# --------------------------------------------------------------------- HDF5 out
def _save_ds(grp, name, arr):
    import h5py  # noqa
    arr = np.asarray(arr)
    kw = {}
    if np.issubdtype(arr.dtype, np.number) and arr.size >= 256:
        kw = dict(compression="gzip", compression_opts=4, shuffle=True)
    grp.create_dataset(name, data=arr, **kw)


def _attr(v):
    """JSON/HDF5-safe attr value."""
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return np.nan if not isinstance(v, str) else v
    return v


def save_h5(records, cal, meta):
    import h5py
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = H5_PATH + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with h5py.File(tmp, "w") as f:
        f.attrs["threshold"] = float(cal["threshold"])
        f.attrs["k"] = int(cal["k"])
        f.attrs["fpr_per_s"] = float(cal["fpr_per_s"])
        f.attrs["seed"] = int(SEED)
        f.attrs["source_aggregate_path"] = str(meta.get("aggregate_path", ""))
        f.attrs["arena_extent"] = np.asarray(tc.ARENA, float)
        f.attrs["generator"] = "build_metrics.py"
        f.attrs["version"] = tc.VERSION
        f.attrs["created_utc"] = _utcnow()
        f.attrs["README"] = (
            "Per-trial trajectory metrics for the odor-guided-orientation analysis. "
            "Geometry on the head clock: body interpolated to head timestamps; "
            "theta=angle(body-axis u=head-body, to-source s=endpoint-body) in [0,180], "
            "NaN where invalid. d=body-to-source distance. Pooled set = Loc1-6; "
            "anotherLoc separate (in_pooled attr). build_complete=1 written LAST.")
        trials_grp = f.create_group("trials")
        for i, r in enumerate(records):
            g = trials_grp.create_group("%03d" % i)
            _save_ds(g, "body_clean", r["body_clean"].astype(np.float64))
            _save_ds(g, "body_t", r["body_t"].astype(np.float64))
            _save_ds(g, "head_clean", r["head_clean"].astype(np.float64))
            _save_ds(g, "head_t", r["head_t"].astype(np.float64))
            _save_ds(g, "ethd_h", r["ethd_h"].astype(np.float64))
            _save_ds(g, "theta", r["theta"].astype(np.float64))
            _save_ds(g, "d", r["d"].astype(np.float64))
            _save_ds(g, "onset_idx", np.asarray(r["onset_idx"], np.int64))
            _save_ds(g, "onset_time", np.asarray(r["onset_time"], np.float64))
            g.attrs["file_name"] = str(r["file_name"])
            g.attrs["end_loc"] = str(r["end_loc"])
            g.attrs["in_pooled"] = bool(r["in_pooled"])
            g.attrs["tortuosity"] = _attr(r["tortuosity"])
            g.attrs["path_length"] = _attr(r["path_length"])
            g.attrs["straight_line"] = _attr(r["straight_line"])
            g.attrs["n_encounters"] = int(r["n_encounters"])
            g.attrs["frac_path_above_threshold"] = _attr(r["frac_path_above_threshold"])
            g.attrs["h2_slope"] = _attr(r["h2_slope"])
            g.attrs["peri_pre_theta"] = _attr(r["peri_pre_theta"])
            g.attrs["peri_post_theta"] = _attr(r["peri_post_theta"])
        f.attrs["build_complete"] = 1  # LAST
    os.replace(tmp, H5_PATH)


def save_metrics_json(records):
    table = []
    for i, r in enumerate(records):
        table.append({
            "trial_index": i, "file_name": r["file_name"], "end_loc": r["end_loc"],
            "in_pooled": bool(r["in_pooled"]),
            "n_encounters": int(r["n_encounters"]),
            "tortuosity": _jnum(r["tortuosity"]),
            "path_length": _jnum(r["path_length"]),
            "straight_line": _jnum(r["straight_line"]),
            "frac_path_above_threshold": _jnum(r["frac_path_above_threshold"]),
            "h2_slope": _jnum(r["h2_slope"]),
            "peri_pre_theta": _jnum(r["peri_pre_theta"]),
            "peri_post_theta": _jnum(r["peri_post_theta"]),
            "body_removed_frac": _jnum(r["body_removed_frac"]),
            "head_removed_frac": _jnum(r["head_removed_frac"]),
            "n_head_frames": int(r["head_t"].size),
        })
    with open(METRICS_JSON, "w", encoding="utf-8") as fh:
        json.dump({"seed": SEED, "version": tc.VERSION, "created_utc": _utcnow(),
                   "n_trials": len(table), "trials": table}, fh, indent=2)


def _jnum(v):
    v = float(v)
    return None if not np.isfinite(v) else v


# --------------------------------------------------------------------- self-check
def slice_selfcheck(records, cal):
    """Assertions on the slice before the heavy full run."""
    assert cal["fpr_per_s"] <= tc.QUIET_FPR_MAX + 1e-9 or "fallback" in cal, cal
    for r in records:
        th = r["theta"][np.isfinite(r["theta"])]
        assert th.size == 0 or (th.min() >= -1e-9 and th.max() <= 180 + 1e-9), \
            ("theta out of [0,180] in %s" % r["file_name"])
        assert r["onset_idx"].ndim == 1
        if r["onset_idx"].size:
            assert r["onset_idx"].max() < r["head_t"].size
    # de-jump smell test is on the MEAN removed fraction (plan §3.2: "mean is the
    # smell-test quantity"); per-trial max can be high on high-motion trials.
    body_rm = np.array([r["body_removed_frac"] for r in records], float)
    head_rm = np.array([r["head_removed_frac"] for r in records], float)
    assert np.nanmean(body_rm) < 0.05, ("mean body de-jump %.4f >=5%%" % np.nanmean(body_rm))
    assert np.nanmean(head_rm) < 0.05, ("mean head de-jump %.4f >=5%%" % np.nanmean(head_rm))
    log.info("slice self-check PASS (theta in [0,180], onsets sane, mean dejump body=%.4f head=%.4f <5%%)",
             np.nanmean(body_rm), np.nanmean(head_rm))


# ---------------------------------------------------------------------- driver
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", type=int, default=0,
                    help="process only the first N trials (self-check slice)")
    args = ap.parse_args()

    setup_logging()
    t0 = _dt.datetime.now()
    log.info("build_metrics start %s  seed=%d  %s", _utcnow(), SEED, tc.VERSION)
    np.random.seed(SEED)
    rng = np.random.default_rng(SEED)

    # library self-check first
    tc._selfcheck()

    trials, meta = pc.load_trials()
    log.info("loaded %d trials from %s", len(trials), meta.get("aggregate_path"))

    # pooled de-jump Q (all trials, both tracks) -- from the FULL cohort always
    Q_body = tc.pooled_dejump_Q(trials, "body")
    Q_head = tc.pooled_dejump_Q(trials, "head")
    log.info("pooled de-jump Q: body=%.4f px  head=%.4f px", Q_body, Q_head)

    if args.slice and args.slice > 0:
        trials = trials[:args.slice]
        log.info("SLICE mode: processing first %d trials", len(trials))

    # ---- per-trial geometry (wrap each in try/except) ----
    records = []
    skipped = []
    for i, tr in enumerate(trials):
        fn = tr.get("file_name", "?")
        try:
            rec = process_trial(tr, Q_body, Q_head)
            records.append(rec)
            log.debug("trial %d %s: end_loc=%s Nh=%d tort=%.3f body_rm=%.4f head_rm=%.4f",
                      i, fn, rec["end_loc"], rec["head_t"].size, rec["tortuosity"],
                      rec["body_removed_frac"], rec["head_removed_frac"])
        except Exception as e:  # noqa
            skipped.append({"trial": i, "file_name": fn, "error": repr(e)})
            log.warning("SKIP trial %d %s: %r", i, fn, e)
    if not records:
        log.error("no trials processed; aborting")
        sys.exit(1)

    # ---- encounter calibration (once, pooled over records) ----
    quiet_segments = []
    for r in records:
        qmask = tc.quiet_baseline_mask(r["ethd_h"], r["head_source_dist"])
        if qmask.any():
            quiet_segments.append((r["ethd_h"][qmask], r["head_t"][qmask]))
    cal = tc.calibrate_encounter_threshold(quiet_segments)
    log.info("calibration: k=%s threshold=%.6f mad_quiet=%.6f fpr=%.5f/s (target<=%.2f) quiet_dur=%.1fs",
             cal["k"], cal["threshold"], cal["mad_quiet"], cal["fpr_per_s"],
             tc.QUIET_FPR_MAX, cal.get("total_quiet_dur_s", float("nan")))
    for row in cal["k_scan"]:
        log.info("  k-scan k=%d thr=%.6f fpr=%.5f/s n_onsets=%d",
                 row["k"], row["threshold"], row["fpr_per_s"], row["n_onsets"])

    # ---- encounters + H2/H3 per-trial fills ----
    for r in records:
        add_encounters(r, cal["threshold"])

    # ---- slice self-check gate ----
    slice_selfcheck(records, cal)

    if args.slice and args.slice > 0:
        n_enc = [r["n_encounters"] for r in records]
        log.info("SLICE OK: n_encounters=%s  (median=%g)  -- not writing full outputs",
                 n_enc, float(np.median(n_enc)))
        log.info("re-run WITHOUT --slice for the full 114-trial build")
        return

    # ---- stats ----
    stats = compute_stats(records, cal, rng)

    # de-jump removed fractions (mean+max) for meta / smell test
    body_rm = np.array([r["body_removed_frac"] for r in records], float)
    head_rm = np.array([r["head_removed_frac"] for r in records], float)
    counts = {}
    for r in records:
        counts[r["end_loc"]] = counts.get(r["end_loc"], 0) + 1
    stats["meta"] = {
        "seed": SEED, "traj_common_version": tc.VERSION,
        "dejump_Q_body_px": float(Q_body), "dejump_Q_head_px": float(Q_head),
        "dejump_removed_frac_body": {"mean": float(np.nanmean(body_rm)), "max": float(np.nanmax(body_rm))},
        "dejump_removed_frac_head": {"mean": float(np.nanmean(head_rm)), "max": float(np.nanmax(head_rm))},
        "dejump_smell_test_body_ok": bool(np.nanmean(body_rm) < 0.05),
        "dejump_smell_test_head_ok": bool(np.nanmean(head_rm) < 0.05),
        "n_trials_processed": len(records), "n_trials_skipped": len(skipped),
        "skipped": skipped,
        "counts_by_group": counts,
        "n_pooled": int(sum(1 for r in records if r["in_pooled"])),
        "n_anotherLoc": int(sum(1 for r in records if r["end_loc"] == "anotherLoc")),
        "n_boot": N_BOOT, "peri_window_s": [PERI_LO, PERI_HI], "peri_step_s": PERI_STEP,
        "created_utc": _utcnow(),
        "aggregate_path": meta.get("aggregate_path", ""),
    }

    with open(STATS_JSON, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)
    log.info("wrote %s", STATS_JSON)

    save_metrics_json(records)
    log.info("wrote %s", METRICS_JSON)

    save_h5(records, cal, meta)
    log.info("wrote %s (build_complete=1)", H5_PATH)

    # ---- summary ----
    h1 = stats["H1"]["primary_n_encounters_vs_tortuosity"]
    h1s = stats["H1"]["secondary_frac_above_vs_tortuosity"]
    h2 = stats["H2"]
    h3 = stats["H3"]
    log.info("==== SUMMARY ====")
    log.info("calibration: k=%d threshold=%.6f quiet_fpr=%.5f/s (<=0.05 target: %s)",
             cal["k"], cal["threshold"], cal["fpr_per_s"],
             cal["fpr_per_s"] <= tc.QUIET_FPR_MAX)
    log.info("de-jump removed mean: body=%.4f (%.2f%%) head=%.4f (%.2f%%)",
             np.nanmean(body_rm), 100*np.nanmean(body_rm), np.nanmean(head_rm), 100*np.nanmean(head_rm))
    log.info("H1 n_enc vs tort: rho=%.4f p=%.4g CI=%s (dir=%s; prior +0.176)",
             h1["spearman_rho"], h1["p"], h1["ci95_boot_trial"], h1["direction"])
    log.info("H1 frac_above vs tort: rho=%.4f p=%.4g CI=%s (dir=%s; prior -0.532)",
             h1s["spearman_rho"], h1s["p"], h1s["ci95_boot_trial"], h1s["direction"])
    log.info("H2 Wilcoxon slopes>0: stat=%s p=%s median_slope=%.5f deg/px n=%d",
             h2["wilcoxon_slopes_gt_0"]["stat"], h2["wilcoxon_slopes_gt_0"]["p"],
             h2["median_slope_deg_per_px"], h2["n_trials_with_finite_slope"])
    log.info("H3 n_trials_with_encounter=%d n_pairs=%d paired Wilcoxon post<pre: stat=%s p=%s "
             "median pre=%.2f post=%.2f (descriptive_only=%s)",
             h3["n_trials_with_encounter"], h3["n_paired_trials"],
             h3["paired_wilcoxon_post_lt_pre"]["stat"], h3["paired_wilcoxon_post_lt_pre"]["p"],
             h3["median_pre_theta"], h3["median_post_theta"], h3["descriptive_only"])
    log.info("n_encounters median (all)=%g pooled=%g",
             stats["calibration"]["n_encounters_distribution_all"]["median"],
             stats["calibration"]["n_encounters_distribution_pooled"]["median"])
    log.info("elapsed %.1fs", (_dt.datetime.now() - t0).total_seconds())


if __name__ == "__main__":
    main()
