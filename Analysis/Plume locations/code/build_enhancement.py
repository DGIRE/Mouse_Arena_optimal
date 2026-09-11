r"""build_enhancement.py -- Task 2 (Signal enhancement) DATA ANALYST script.

Per trial, operate on the RAW ethanol trace on the sensor clock (ethanol_time):
  1. Drift removal via rolling 10th-percentile baseline (window W, data-justified).
  2. Build a canonical matched-filter template from high-SNR NEAR-endpoint encounters.
  3. Enhance drift-corrected trace by normalized cross-correlation with the template.
  4. Detect encounters before (drift_corrected) / after (enhanced) at a MATCHED
     false-positive rate on a quiet far-from-source baseline (H5 guard: after<=before).
  5. Distal SNR gain per trial; rank -> top-10 Figure-A candidates.

Writes:
  data/enhanced_ethanol.h5      (exact per-trial contract)
  data/enhancement_stats.json   (per-trial + aggregate stats)
  logs/build_enhancement.log

Run:
  AR_PY="C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe"
  "$AR_PY" code/build_enhancement.py
Import-only shared helpers from plume_common (do not reimplement).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import h5py
from scipy import signal as sp_signal
from scipy import stats as sp_stats

# --- paths ------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # Analysis\Plume locations
DATA_DIR = os.path.join(ROOT, "data")
LOG_DIR = os.path.join(ROOT, "logs")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import plume_common as pc  # noqa: E402  (shared library; do NOT reimplement)

H5_OUT = os.path.join(DATA_DIR, "enhanced_ethanol.h5")
STATS_OUT = os.path.join(DATA_DIR, "enhancement_stats.json")
LOG_OUT = os.path.join(LOG_DIR, "build_enhancement.log")
GENERATOR = "build_enhancement.py/1.0"

# --- pre-registered parameters ---------------------------------------------
FS = 500.0                       # sensor Hz [verified]
DRIFT_W_S = 20.0                 # drift window seconds (plan default, in 10-30 s)
DRIFT_PCTILE = 10.0              # rolling low-percentile for baseline
TMPL_HALF_S = 0.3                # template half-window -> 301 samples @500Hz
TMPL_K = 5.0                     # k*MAD_quiet peak threshold for template peaks
NEAR_DIST_PCTILE = 20.0         # near-endpoint = distance < this pctile of covered
QUIET_VAR_FRAC = 0.20            # lowest-variance fraction for MAD_quiet segment
FAR_DIST_PCTILE = 80.0          # baseline: distance > this pctile
BASELINE_AMP_FRAC = 0.20        # baseline: lowest-amplitude fraction among far samples
REFRACTORY_S = 0.2              # detector refractory gap
# --- M1 recalibration (Gate-2 audit) ---------------------------------------
# BEFORE detector threshold = k * MAD of the quiet far-from-source baseline
# (drift-corrected). Choose the SMALLEST k in K_GRID whose measured quiet-baseline
# FPR is physically meaningful (<= TARGET_FPR_MAX, approaching 0). Then match the
# AFTER threshold to that SAME low baseline FPR (H5 guard: after <= before).
K_GRID = [5.0, 6.0, 8.0, 10.0]  # candidate k multipliers on baseline MAD
TARGET_FPR_MAX = 0.05           # physically meaningful quiet-baseline FPR (enc/s)
SNR_QUIET_HALF_S = 1.0          # +/-1s local quiet window for SNR noise estimate
TOP_N = 10                       # Figure-A candidates
DRIFT_VALIDATION_OUT = os.path.join(DATA_DIR, "drift_validation.json")
DRIFT_VALIDATION_TRIALS = 3      # number of example trials for m4 residual check


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _f64(a):
    return np.asarray(a, dtype=np.float64)


def rolling_low_percentile(x, w_samples, q):
    """Fast centered rolling q-th percentile baseline (min_periods=1)."""
    s = pd.Series(x)
    return s.rolling(window=int(w_samples), min_periods=1, center=True).quantile(q / 100.0).to_numpy()


def drift_timescale_1e(x, dt, max_lag_s=60.0):
    """Estimate drift timescale = lag where autocorrelation of x drops to 1/e.
    Uses mean-subtracted trace; returns seconds (NaN if never crosses)."""
    x = _f64(x)
    x = x[np.isfinite(x)]
    if x.size < 8:
        return float("nan")
    x = x - x.mean()
    n = x.size
    max_lag = min(int(max_lag_s / dt), n - 1)
    if max_lag < 2:
        return float("nan")
    # normalized autocorrelation via FFT
    var = np.dot(x, x)
    if var <= 0:
        return float("nan")
    f = np.fft.rfft(x, n=2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:max_lag + 1]
    ac = ac / var
    thr = 1.0 / np.e
    below = np.nonzero(ac < thr)[0]
    if below.size == 0:
        return float("nan")
    lag = int(below[0])
    return float(lag * dt)


def mad_quiet_segment(x, win_samples):
    """MAD of the lowest-variance window of length win_samples (non-overlapping)."""
    x = _f64(x)
    n = x.size
    win = int(max(3, min(win_samples, n)))
    if n <= win:
        return pc.mad(x)
    # scan non-overlapping windows, pick lowest variance
    nblk = n // win
    best_var = np.inf
    best = x[:win]
    for b in range(nblk):
        seg = x[b * win:(b + 1) * win]
        v = np.var(seg)
        if v < best_var:
            best_var = v
            best = seg
    return pc.mad(best)


def build_template_windows(drift_corr, ethanol_time, peaks, half_samps):
    """Extract +/- half_samps windows around each peak; return (n_win, L) matrix
    of only fully-in-bounds windows (peak-aligned)."""
    L = 2 * half_samps + 1
    n = drift_corr.size
    wins = []
    for p in peaks:
        lo = p - half_samps
        hi = p + half_samps + 1
        if lo < 0 or hi > n:
            continue
        seg = drift_corr[lo:hi]
        if seg.size == L and np.all(np.isfinite(seg)):
            wins.append(seg)
    if not wins:
        return np.empty((0, L))
    return np.vstack(wins)


def normalize_unit_energy(t):
    """Zero-mean, unit-energy normalization of a template vector."""
    t = _f64(t)
    t = t - np.mean(t)
    e = np.sqrt(np.dot(t, t))
    if e <= 0 or not np.isfinite(e):
        return t
    return t / e


def matched_filter(drift_corr, template):
    """Normalized cross-correlation (matched filter). template is zero-mean,
    unit-energy. Returns enhanced trace, SAME length as drift_corr.

    At each position we compute the dot product of the (zero-mean) local window
    with the unit-energy template, divided by the local window energy -> a
    correlation-like score in ~[-1,1]. NaNs in input handled by fill-with-mean
    for the sliding math, then re-masked.
    """
    x = _f64(drift_corr)
    finite = np.isfinite(x)
    if not finite.all():
        fill = np.nanmean(x) if finite.any() else 0.0
        x = np.where(finite, x, fill)
    L = template.size
    n = x.size
    if L > n:
        return np.zeros(n)
    ker = template[::-1]  # correlate == convolve with reversed kernel
    # numerator: dot of local window (mean-removed) with unit-energy template.
    # Because template is zero-mean, sum(template)=0, so
    #   sum((w - mean_w)*tmpl) = sum(w*tmpl).  -> plain cross-correlation.
    num = sp_signal.fftconvolve(x, ker, mode="same")
    # local energy for normalization: sqrt(sum((w-mean_w)^2)) over the L window
    ones = np.ones(L)
    s1 = sp_signal.fftconvolve(x, ones, mode="same")
    s2 = sp_signal.fftconvolve(x * x, ones, mode="same")
    local_energy = np.sqrt(np.maximum(s2 - (s1 * s1) / L, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        enhanced = np.where(local_energy > 0, num / local_energy, 0.0)
    enhanced[~np.isfinite(enhanced)] = 0.0
    return enhanced


def detection_rate_on_segments(seg_list, seg_times, thresh):
    """Total detected encounters / total duration across baseline segments."""
    total_n = 0
    total_dur = 0.0
    for sig, tt in zip(seg_list, seg_times):
        if sig.size < 3:
            continue
        pk = pc.detect_encounters(sig, tt, thresh=thresh,
                                  refractory_s=REFRACTORY_S, min_prominence=1e-12)
        total_n += int(pk.size)
        total_dur += float(tt[-1] - tt[0]) if tt.size >= 2 else 0.0
    if total_dur <= 0:
        return 0.0, 0, 0.0
    return total_n / total_dur, total_n, total_dur


def choose_threshold_for_rate(seg_list, seg_times, target_rate, thr_grid):
    """Smallest threshold on thr_grid whose pooled baseline rate <= target_rate.
    thr_grid ascending. Returns (thresh, achieved_rate)."""
    best_thr = thr_grid[-1]
    best_rate = 0.0
    for thr in thr_grid:
        rate, _, _ = detection_rate_on_segments(seg_list, seg_times, thr)
        if rate <= target_rate:
            return float(thr), float(rate)
        best_thr = float(thr)
        best_rate = float(rate)
    return best_thr, best_rate  # none satisfied -> strictest available


def snr_of_peaks(sig, peaks, half_samps):
    """SNR = |peak_amp| / MAD(local +/- window minus a small exclusion). Returns
    array aligned to peaks."""
    n = sig.size
    out = np.full(peaks.shape, np.nan, float)
    for i, p in enumerate(peaks):
        lo = max(0, p - half_samps)
        hi = min(n, p + half_samps + 1)
        local = sig[lo:hi]
        noise = pc.mad(local)
        if noise is None or not np.isfinite(noise) or noise <= 0:
            # fall back to std of local window
            fin = local[np.isfinite(local)]
            noise = float(np.std(fin)) if fin.size else np.nan
        if noise and np.isfinite(noise) and noise > 0:
            out[i] = float(abs(sig[p]) / noise)
    return out


# --------------------------------------------------------------------------- #
# per-trial processing
# --------------------------------------------------------------------------- #
def process_trial(tr, Q, log):
    """Return a dict of everything needed for stats + h5, or raise on failure."""
    raw = _f64(tr["ethanol"])
    et = _f64(tr["ethanol_time"])
    head = _f64(tr["head"])
    head_time = _f64(tr["head_time"])
    body = _f64(tr["body"])
    endpoint = pc.endpoint_of(tr)
    n = raw.size
    dt = float(np.median(np.diff(et))) if et.size > 1 else 1.0 / FS

    # ---- 1. drift removal --------------------------------------------------
    W_samples = int(round(DRIFT_W_S * FS))
    W_samples = int(min(max(W_samples, 3), n))
    baseline = rolling_low_percentile(raw, W_samples, DRIFT_PCTILE)
    drift_corr = raw - baseline
    drift_ts = drift_timescale_1e(raw, dt)

    # ---- distances on the sensor clock ------------------------------------
    # interpolate head x and y onto the sensor clock, NaN outside coverage,
    # then Euclidean distance to endpoint.
    hx = pc.align_signal(et, head_time, head[:, 0])
    hy = pc.align_signal(et, head_time, head[:, 1])
    dist_sensor = np.hypot(hx - endpoint[0], hy - endpoint[1])  # NaN outside coverage
    covered = np.isfinite(dist_sensor)

    # ---- quiet MAD (lowest-variance 20% window) ---------------------------
    quiet_win = int(max(3, round(QUIET_VAR_FRAC * n)))
    mad_quiet = mad_quiet_segment(drift_corr, quiet_win)
    if not np.isfinite(mad_quiet) or mad_quiet <= 0:
        mad_quiet = pc.mad(drift_corr)
    if not np.isfinite(mad_quiet) or mad_quiet <= 0:
        mad_quiet = 1e-9

    # ---- 2. template contribution (near-endpoint high-SNR peaks) ----------
    half_samps = int(round(TMPL_HALF_S * FS))  # 150 -> L=301
    tmpl_thresh = TMPL_K * mad_quiet
    cand = pc.detect_encounters(drift_corr, et, thresh=tmpl_thresh,
                                refractory_s=REFRACTORY_S, min_prominence=tmpl_thresh)
    near_peaks = np.array([], int)
    if covered.any() and cand.size:
        near_cut = np.percentile(dist_sensor[covered], NEAR_DIST_PCTILE)
        keep = [p for p in cand if covered[p] and dist_sensor[p] < near_cut]
        near_peaks = np.asarray(keep, int)
    tmpl_windows = build_template_windows(drift_corr, et, near_peaks, half_samps)
    contribution = tmpl_windows.mean(axis=0) if tmpl_windows.shape[0] > 0 else None

    return {
        "trial_index": int(tr["trial_index"]),
        "file_name": tr["file_name"],
        "group": pc.group_of(tr["file_name"]),
        "raw": raw, "et": et, "dt": dt, "n": n,
        "baseline": baseline, "drift_corr": drift_corr,
        "drift_ts": drift_ts, "W_used": W_samples,
        "head": head, "head_time": head_time, "body": body, "endpoint": endpoint,
        "dist_sensor": dist_sensor, "covered": covered,
        "mad_quiet": float(mad_quiet), "half_samps": half_samps,
        "near_peaks": near_peaks,
        "tmpl_windows": tmpl_windows,
        "contribution": contribution,
    }


def finalize_trial(pt, template, thr_before, thr_after, log):
    """Given the pooled template + calibrated thresholds, compute enhanced trace,
    before/after contacts, distal splits, SNR gain. Mutates/returns a result dict."""
    drift_corr = pt["drift_corr"]
    et = pt["et"]
    dist_sensor = pt["dist_sensor"]
    covered = pt["covered"]
    half = pt["half_samps"]
    snr_half = int(round(SNR_QUIET_HALF_S * FS))

    enhanced = matched_filter(drift_corr, template)
    assert enhanced.size == drift_corr.size, "enhanced length mismatch"

    # ---- detection before/after -------------------------------------------
    pk_before = pc.detect_encounters(drift_corr, et, thresh=thr_before,
                                     refractory_s=REFRACTORY_S, min_prominence=1e-12)
    pk_after = pc.detect_encounters(enhanced, et, thresh=thr_after,
                                    refractory_s=REFRACTORY_S, min_prominence=1e-12)

    # ---- distal split (distance > per-trial MEDIAN) -----------------------
    if covered.any():
        med_dist = float(np.median(dist_sensor[covered]))
    else:
        med_dist = float("nan")

    def is_distal(p):
        d = dist_sensor[p]
        return np.isfinite(d) and d > med_dist

    def is_prox(p):
        d = dist_sensor[p]
        return np.isfinite(d) and d <= med_dist

    n_before = int(pk_before.size)
    n_after = int(pk_after.size)
    n_before_distal = int(sum(is_distal(p) for p in pk_before))
    n_after_distal = int(sum(is_distal(p) for p in pk_after))
    n_before_prox = int(sum(is_prox(p) for p in pk_before))
    n_after_prox = int(sum(is_prox(p) for p in pk_after))

    # ---- SNR (identical def before/after) on distal encounters ------------
    snr_before = snr_of_peaks(drift_corr, pk_before, snr_half)
    snr_after = snr_of_peaks(enhanced, pk_after, snr_half)
    distal_before_snr = np.array([snr_before[i] for i, p in enumerate(pk_before) if is_distal(p)], float)
    distal_after_snr = np.array([snr_after[i] for i, p in enumerate(pk_after) if is_distal(p)], float)
    mb = float(np.nanmean(distal_before_snr)) if distal_before_snr.size and np.isfinite(np.nanmean(distal_before_snr)) else np.nan
    ma = float(np.nanmean(distal_after_snr)) if distal_after_snr.size and np.isfinite(np.nanmean(distal_after_snr)) else np.nan
    if np.isfinite(ma) and np.isfinite(mb):
        distal_snr_gain = ma - mb
    elif np.isfinite(ma) and not np.isfinite(mb):
        distal_snr_gain = ma  # recovered distal encounters where none before
    else:
        distal_snr_gain = 0.0

    # ---- contacts amplitudes on their native trace ------------------------
    amp_before = drift_corr[pk_before] if pk_before.size else np.array([], float)
    amp_after = enhanced[pk_after] if pk_after.size else np.array([], float)

    return {
        "enhanced": enhanced,
        "pk_before": pk_before, "pk_after": pk_after,
        "amp_before": amp_before, "amp_after": amp_after,
        "n_before": n_before, "n_after": n_after,
        "n_before_distal": n_before_distal, "n_after_distal": n_after_distal,
        "n_before_prox": n_before_prox, "n_after_prox": n_after_prox,
        "med_dist": med_dist,
        "distal_snr_gain": float(distal_snr_gain),
    }


# --------------------------------------------------------------------------- #
# baseline segments (for FPR calibration)
# --------------------------------------------------------------------------- #
def baseline_segments(pt):
    """Return (before_seg, after_seg, seg_time) lists for this trial's quiet
    far-from-source baseline (distance > 80th pctile AND lowest-amplitude portion).
    We enhance the baseline segment with the SAME template later; here we return
    index masks -> caller builds enhanced-baseline consistently."""
    dist_sensor = pt["dist_sensor"]
    covered = pt["covered"]
    drift_corr = pt["drift_corr"]
    if not covered.any():
        return None
    far_cut = np.percentile(dist_sensor[covered], FAR_DIST_PCTILE)
    far_mask = covered & (dist_sensor > far_cut)
    if far_mask.sum() < 5:
        return None
    # lowest-amplitude portion among far samples: use |drift_corr|
    amp = np.abs(drift_corr)
    far_idx = np.nonzero(far_mask)[0]
    amp_thr = np.percentile(amp[far_idx], BASELINE_AMP_FRAC * 100.0)
    quiet_far_idx = far_idx[amp[far_idx] <= amp_thr]
    if quiet_far_idx.size < 5:
        quiet_far_idx = far_idx  # fall back to all far samples
    return quiet_far_idx


def contiguous_runs(idx):
    """Split sorted index array into contiguous runs (list of (start,stop_inclusive))."""
    if idx.size == 0:
        return []
    runs = []
    start = prev = idx[0]
    for i in idx[1:]:
        if i == prev + 1:
            prev = i
        else:
            runs.append((start, prev))
            start = prev = i
    runs.append((start, prev))
    return runs


# --------------------------------------------------------------------------- #
# m4: drift-window residual validation
# --------------------------------------------------------------------------- #
def _slow_trend_slope(x, t, w_samples):
    """OLS slope (per second) of a heavily-smoothed (rolling-mean over the drift
    window) version of x vs t -> the SLOW trend only. Robust to fast transients."""
    x = _f64(x)
    t = _f64(t)
    fin = np.isfinite(x) & np.isfinite(t)
    x = x[fin]
    t = t[fin]
    if x.size < 3:
        return float("nan")
    w = int(max(3, min(w_samples, x.size)))
    smooth = pd.Series(x).rolling(window=w, min_periods=1, center=True).mean().to_numpy()
    # OLS slope of smooth vs t
    tc = t - t.mean()
    denom = float(np.dot(tc, tc))
    if denom <= 0:
        return float("nan")
    return float(np.dot(tc, smooth - smooth.mean()) / denom)


def _encounter_band_var(x, dt):
    """Variance of the fast/encounter-band component (high-pass: x minus a
    ~1s rolling mean), i.e. energy retained in fast transients."""
    x = _f64(x)
    fin = np.isfinite(x)
    x = x[fin]
    if x.size < 3:
        return float("nan")
    w = int(max(3, min(round(1.0 * FS), x.size)))
    lowfreq = pd.Series(x).rolling(window=w, min_periods=1, center=True).mean().to_numpy()
    fast = x - lowfreq
    return float(np.var(fast))


def write_drift_validation(pts, log, n_examples=DRIFT_VALIDATION_TRIALS):
    """m4: for 2-3 example trials, show the W=20s rolling-10th-pctile baseline
    tracks slow drift and the residual (drift-corrected) has near-zero slow trend
    but retains fast transients. Saves data/drift_validation.json."""
    examples = []
    for pt in pts[:n_examples]:
        raw = pt["raw"]
        dc = pt["drift_corr"]
        et = pt["et"]
        w = int(pt["W_used"])
        slope_raw = _slow_trend_slope(raw, et, w)
        slope_dc = _slow_trend_slope(dc, et, w)
        var_fast_raw = _encounter_band_var(raw, pt["dt"])
        var_fast_dc = _encounter_band_var(dc, pt["dt"])
        ratio = (var_fast_dc / var_fast_raw) if (np.isfinite(var_fast_raw) and var_fast_raw > 0) else float("nan")
        examples.append({
            "trial_index": int(pt["trial_index"]),
            "group": pt["group"],
            "file_name": pt["file_name"],
            "W_used_samples": w,
            "W_used_s": w / FS,
            "drift_percentile": DRIFT_PCTILE,
            "slow_trend_slope_per_s_before": slope_raw,
            "slow_trend_slope_per_s_after": slope_dc,
            "slow_trend_slope_abs_reduction_factor": (abs(slope_raw) / abs(slope_dc))
                if (np.isfinite(slope_raw) and np.isfinite(slope_dc) and abs(slope_dc) > 0) else None,
            "encounter_band_var_before": var_fast_raw,
            "encounter_band_var_after": var_fast_dc,
            "encounter_band_var_retained_frac": ratio,
        })
        log.info("drift-val trial %d: slow-slope raw=%.4g -> dc=%.4g (|reduce|); "
                 "fast-band var raw=%.4g dc=%.4g (retained=%.3f)",
                 pt["trial_index"], slope_raw, slope_dc, var_fast_raw, var_fast_dc, ratio)
    artifact = {
        "generator": GENERATOR,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "description": (
            "m4 drift-window residual validation. The W=20s rolling-10th-percentile "
            "baseline is subtracted from raw ethanol. 'before' = raw, 'after' = "
            "drift-corrected. slow_trend_slope = OLS slope (per s) of the drift-window "
            "smoothed trace vs time (slow trend); it should collapse toward ~0 after "
            "baseline subtraction. encounter_band_var = variance of the fast (high-pass) "
            "component; it should be preserved (retained_frac ~1) after subtraction."
        ),
        "drift_window_s": DRIFT_W_S,
        "drift_percentile": DRIFT_PCTILE,
        "examples": examples,
    }
    tmp = DRIFT_VALIDATION_OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2, allow_nan=True)
    os.replace(tmp, DRIFT_VALIDATION_OUT)
    log.info("wrote %s (%d example trials)", DRIFT_VALIDATION_OUT, len(examples))
    return artifact


# --------------------------------------------------------------------------- #
# h5 writer
# --------------------------------------------------------------------------- #
def _pad_id(ti):
    return f"{ti:03d}"


def _create_ds(grp, name, arr):
    arr = np.asarray(arr)
    kwargs = {}
    if arr.dtype.kind == "f":
        arr = arr.astype(np.float32)
    elif arr.dtype.kind in "iu":
        arr = arr.astype(np.int64)
    if arr.size >= 256:
        kwargs = dict(compression="gzip", compression_opts=4, shuffle=True)
    grp.create_dataset(name, data=arr, **kwargs)


def write_h5(results, params, agg_meta, log):
    tmp = H5_OUT + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with h5py.File(tmp, "w") as f:
        # root attrs (method + ALL params)
        f.attrs["method"] = "drift(rolling low-pctile) -> pooled matched-filter template -> normalized cross-correlation enhancement; matched-FPR before/after detection"
        f.attrs["generator"] = GENERATOR
        f.attrs["plume_common_version"] = pc.VERSION
        f.attrs["source_aggregate_path"] = agg_meta.get("aggregate_path", "")
        f.attrs["created_utc"] = datetime.now(timezone.utc).isoformat()
        f.attrs["seed"] = int(pc.SEED)
        f.attrs["Fs_hz"] = FS
        f.attrs["drift_window_s"] = DRIFT_W_S
        f.attrs["drift_percentile"] = DRIFT_PCTILE
        f.attrs["template_half_window_s"] = TMPL_HALF_S
        f.attrs["template_len_samples"] = int(2 * round(TMPL_HALF_S * FS) + 1)
        f.attrs["template_k_mad"] = TMPL_K
        f.attrs["near_dist_pctile"] = NEAR_DIST_PCTILE
        f.attrs["refractory_s"] = REFRACTORY_S
        f.attrs["target_fpr_max_per_s"] = TARGET_FPR_MAX
        f.attrs["before_thresh_k_mad"] = float(params["k_used"])
        f.attrs["baseline_mad"] = float(params["baseline_mad"])
        f.attrs["distal_rule"] = "head-endpoint distance (sensor clock) > per-trial MEDIAN"
        f.attrs["snr_def"] = "peak_amp / plume_common.mad(local +/-1s quiet window of SAME trace); dimensionless, identical before/after"
        f.attrs["thresh_before_global"] = params["thr_before"]
        f.attrs["thresh_after_global"] = params["thr_after"]
        f.attrs["baseline_fpr_before"] = params["baseline_fpr_before"]
        f.attrs["baseline_fpr_after"] = params["baseline_fpr_after"]
        f.attrs["README"] = (
            "Task-2 signal enhancement. Per-trial group /trials/<ttt> (ttt = 0-padded "
            "trial_index). Datasets: enhanced (matched-filter score, same length as raw "
            "ethanol on sensor clock), time (=ethanol_time), baseline (rolling 10th-pctile "
            "drift), contacts_before_* (detected on drift-corrected raw), contacts_after_* "
            "(detected on enhanced), head/head_time (99Hz), body, endpoint. All thresholds "
            "calibrated to a matched false-positive rate on quiet far-from-source baseline "
            "segments (H5 guard: after FPR <= before FPR). See root attrs for all params."
        )
        f.attrs["build_complete"] = 0

        tg = f.create_group("trials")
        for r in results:
            gid = _pad_id(r["trial_index"])
            g = tg.create_group(gid)
            _create_ds(g, "enhanced", r["enhanced"])
            _create_ds(g, "time", r["et"])
            _create_ds(g, "baseline", r["baseline"])
            _create_ds(g, "drift_corrected", r["drift_corr"])
            _create_ds(g, "contacts_before_idx", r["pk_before"])
            _create_ds(g, "contacts_before_time", r["et"][r["pk_before"]] if r["pk_before"].size else np.array([], float))
            _create_ds(g, "contacts_before_amp", r["amp_before"])
            _create_ds(g, "contacts_after_idx", r["pk_after"])
            _create_ds(g, "contacts_after_time", r["et"][r["pk_after"]] if r["pk_after"].size else np.array([], float))
            _create_ds(g, "contacts_after_amp", r["amp_after"])
            _create_ds(g, "head", r["head"])
            _create_ds(g, "head_time", r["head_time"])
            _create_ds(g, "body", r["body"])
            _create_ds(g, "endpoint", r["endpoint"])
            g.attrs["n_before"] = int(r["n_before"])
            g.attrs["n_after"] = int(r["n_after"])
            g.attrs["distal_snr_gain"] = float(r["distal_snr_gain"])
            g.attrs["thresh_before"] = float(params["thr_before"])
            g.attrs["thresh_after"] = float(params["thr_after"])
            g.attrs["file_name"] = r["file_name"]
            g.attrs["group"] = r["group"]
            g.attrs["W_used"] = int(r["W_used"])
            g.attrs["drift_timescale_s"] = float(r["drift_ts"]) if np.isfinite(r["drift_ts"]) else -1.0
        # set build_complete last
        f.attrs["build_complete"] = 1
    os.replace(tmp, H5_OUT)
    log.info("wrote %s (%d trial groups)", H5_OUT, len(results))


# --------------------------------------------------------------------------- #
# self-check (before full loop)
# --------------------------------------------------------------------------- #
def self_check(log):
    rng = np.random.default_rng(pc.SEED)
    # synthetic trace: drift + a couple of gaussian bumps + noise
    fs = FS
    T = 10.0
    t = np.arange(int(T * fs)) / fs
    drift = 0.3 * np.sin(2 * np.pi * t / 8.0) + 0.5
    bump = np.exp(-0.5 * ((t - 3.0) / 0.05) ** 2) + np.exp(-0.5 * ((t - 6.0) / 0.05) ** 2)
    x = drift + 0.4 * bump + 0.01 * rng.standard_normal(t.size)
    W = int(min(round(DRIFT_W_S * fs), x.size))
    base = rolling_low_percentile(x, W, DRIFT_PCTILE)
    dc = x - base
    assert dc.size == x.size, "drift length mismatch"
    # template: unit energy, finite
    half = int(round(TMPL_HALF_S * fs))
    tmpl = normalize_unit_energy(np.exp(-0.5 * ((np.arange(-half, half + 1)) / (0.05 * fs)) ** 2))
    assert np.all(np.isfinite(tmpl)), "template not finite"
    assert abs(np.dot(tmpl, tmpl) - 1.0) < 1e-6, "template not unit energy"
    assert abs(np.mean(tmpl)) < 1e-6, "template not zero mean"
    enh = matched_filter(dc, tmpl)
    assert enh.size == dc.size, "enhanced length != trace length"
    assert np.all(np.isfinite(enh)), "enhanced not finite"
    # matched filter should peak near the true bumps
    assert enh.max() > 0.3, "matched filter response too weak"
    ts = drift_timescale_1e(x, 1.0 / fs)
    assert np.isfinite(ts) and ts > 0, "drift timescale invalid"
    log.info("self-check PASS (drift_ts=%.3fs, enh_max=%.3f)", ts, float(enh.max()))
    print(f"self-check PASS (drift_ts={ts:.3f}s, enh_max={enh.max():.3f})")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    limit = None
    for a in argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])

    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    log = logging.getLogger("build_enhancement")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fh = logging.FileHandler(LOG_OUT, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    log.info("start %s  limit=%s", GENERATOR, limit)

    np.random.seed(pc.SEED)

    # ---- self-check --------------------------------------------------------
    self_check(log)

    # ---- load --------------------------------------------------------------
    trials, agg_meta = pc.load_trials()
    log.info("loaded %d trials", len(trials))
    Q = pc.pooled_dejump_Q(trials, "head")
    log.info("pooled de-jump Q(head) = %.3f px", Q)

    if limit is not None:
        trials = trials[:limit]
        log.info("SLICE: processing first %d trials", len(trials))

    # ---- PASS 1: per-trial drift + template contribution -------------------
    pts = []
    contributions = []
    contributions_by_group = {}
    for tr in trials:
        ti = int(tr["trial_index"])
        try:
            pt = process_trial(tr, Q, log)
            pts.append(pt)
            if pt["contribution"] is not None:
                contributions.append(pt["contribution"])
                contributions_by_group.setdefault(pt["group"], []).append(pt["contribution"])
            log.info("trial %d: n=%d W=%d drift_ts=%.2fs mad_quiet=%.4g near_peaks=%d tmpl_wins=%d",
                     ti, pt["n"], pt["W_used"], pt["drift_ts"], pt["mad_quiet"],
                     pt["near_peaks"].size, pt["tmpl_windows"].shape[0])
        except Exception as e:  # noqa: BLE001
            log.exception("trial %d SKIPPED in pass1: %s", ti, e)

    if not pts:
        log.error("no trials processed; abort")
        print("ERROR: no trials processed")
        return 2

    # ---- pooled canonical template ----------------------------------------
    half = int(round(TMPL_HALF_S * FS))
    L = 2 * half + 1
    if contributions:
        pooled = np.vstack(contributions).mean(axis=0)
    else:
        # degenerate: no near peaks anywhere -> symmetric positive bump fallback
        log.warning("no template contributions found; using gaussian fallback template")
        pooled = np.exp(-0.5 * ((np.arange(-half, half + 1)) / (0.05 * FS)) ** 2)
    template = normalize_unit_energy(pooled)
    assert template.size == L and np.all(np.isfinite(template))
    log.info("pooled template from %d trial contributions; L=%d unit-energy=%.4f",
             len(contributions), template.size, float(np.dot(template, template)))

    # per-location templates (report only)
    per_loc_templates = {}
    for g, lst in contributions_by_group.items():
        per_loc_templates[g] = normalize_unit_energy(np.vstack(lst).mean(axis=0)).tolist()

    # ---- FPR calibration ---------------------------------------------------
    # Build pooled baseline segments on BEFORE (drift_corr) and AFTER (enhanced).
    # First compute enhanced trace per trial (needed for after baseline).
    for pt in pts:
        pt["enhanced_full"] = matched_filter(pt["drift_corr"], template)

    before_segs, before_times, after_segs, after_times = [], [], [], []
    for pt in pts:
        qidx = baseline_segments(pt)
        if qidx is None:
            continue
        for (a, b) in contiguous_runs(np.sort(qidx)):
            if b - a + 1 < 3:
                continue
            before_segs.append(pt["drift_corr"][a:b + 1])
            before_times.append(pt["et"][a:b + 1])
            after_segs.append(pt["enhanced_full"][a:b + 1])
            after_times.append(pt["et"][a:b + 1])
    total_base_dur = float(sum((tt[-1] - tt[0]) for tt in before_times if tt.size >= 2))
    log.info("baseline: %d segments, total %.1fs", len(before_segs), total_base_dur)

    # ---- M1: BEFORE threshold = k * MAD(quiet far-from-source baseline) ----
    # Estimate the baseline noise (MAD) on the pooled quiet far-from-source,
    # drift-corrected baseline samples, then pick the SMALLEST k in K_GRID whose
    # measured quiet-baseline FPR is physically meaningful (<= TARGET_FPR_MAX).
    b_all = np.concatenate([s[np.isfinite(s)] for s in before_segs]) if before_segs else np.array([0.0])
    if b_all.size == 0:
        b_all = np.array([0.0, 1.0])
    baseline_mad = pc.mad(b_all)
    if not np.isfinite(baseline_mad) or baseline_mad <= 0:
        baseline_mad = float(np.std(b_all)) if b_all.size else 1e-9
        if not np.isfinite(baseline_mad) or baseline_mad <= 0:
            baseline_mad = 1e-9
    k_used = None
    thr_before = None
    fpr_before = None
    k_scan = []
    for k in K_GRID:
        thr_k = float(k * baseline_mad)
        rate_k, nk, _ = detection_rate_on_segments(before_segs, before_times, thr_k)
        k_scan.append({"k": float(k), "thr": thr_k, "fpr_per_s": float(rate_k), "n_det": int(nk)})
        log.info("k-scan: k=%.1f thr_before=%.6g quiet-FPR=%.5f/s (n=%d)", k, thr_k, rate_k, nk)
        if k_used is None and rate_k <= TARGET_FPR_MAX:
            k_used = float(k)
            thr_before = thr_k
            fpr_before = float(rate_k)
    if k_used is None:
        # none reached target: use the strictest (largest) k available
        k_used = float(K_GRID[-1])
        thr_before = float(K_GRID[-1] * baseline_mad)
        fpr_before, _, _ = detection_rate_on_segments(before_segs, before_times, thr_before)
        log.warning("no k in %s met FPR<=%.3f; using strictest k=%.1f (FPR=%.5f)",
                    K_GRID, TARGET_FPR_MAX, k_used, fpr_before)

    # ---- AFTER threshold: match the SAME low baseline FPR (H5 guard) --------
    # enhanced is a normalized cross-correlation score in ~[-1,1]; choose the
    # smallest threshold whose after-baseline rate <= before-baseline FPR.
    a_all = np.concatenate([s[np.isfinite(s)] for s in after_segs]) if after_segs else np.array([0.0])
    if a_all.size == 0:
        a_all = np.array([0.0, 1.0])
    a_grid = np.linspace(max(0.0, np.percentile(a_all, 1)),
                         max(np.percentile(a_all, 99.99), 1.0), 400)
    thr_after, _ = choose_threshold_for_rate(after_segs, after_times, fpr_before, a_grid)
    fpr_after, na_base, _ = detection_rate_on_segments(after_segs, after_times, thr_after)

    log.info("calibration: k=%.1f baseline_MAD=%.6g thr_before=%.6g fpr_before=%.5f/s | "
             "thr_after=%.6g fpr_after=%.5f/s",
             k_used, baseline_mad, thr_before, fpr_before, thr_after, fpr_after)

    # H5 guard
    h5_guard_ok = fpr_after <= fpr_before + 1e-9
    if not h5_guard_ok:
        # try to make AFTER strictly stricter by pushing threshold up to max grid
        log.error("H5 GUARD VIOLATED before calib retry: after %.4f > before %.4f", fpr_after, fpr_before)
        # last resort: raise threshold to the value giving zero detections
        thr_after = float(a_grid[-1])
        fpr_after, na_base, _ = detection_rate_on_segments(after_segs, after_times, thr_after)
        h5_guard_ok = fpr_after <= fpr_before + 1e-9
        log.info("H5 retry: thr_after=%.5f fpr_after=%.4f", thr_after, fpr_after)

    params = {
        "thr_before": float(thr_before),
        "thr_after": float(thr_after),
        "baseline_fpr_before": float(fpr_before),
        "baseline_fpr_after": float(fpr_after),
        "k_used": float(k_used),
        "baseline_mad": float(baseline_mad),
        "k_scan": k_scan,
    }

    # ---- PASS 2: finalize each trial with calibrated thresholds ------------
    results = []
    for pt in pts:
        ti = pt["trial_index"]
        try:
            fin = finalize_trial(pt, template, thr_before, thr_after, log)
            r = {
                "trial_index": ti, "file_name": pt["file_name"], "group": pt["group"],
                "et": pt["et"], "baseline": pt["baseline"], "drift_corr": pt["drift_corr"],
                "head": pt["head"], "head_time": pt["head_time"],
                "body": pt["body"], "endpoint": pt["endpoint"],
                "W_used": pt["W_used"], "drift_ts": pt["drift_ts"],
                **fin,
            }
            results.append(r)
            log.info("trial %d final: n_before=%d n_after=%d distal(b/a)=%d/%d prox(b/a)=%d/%d snr_gain=%.3f",
                     ti, fin["n_before"], fin["n_after"], fin["n_before_distal"],
                     fin["n_after_distal"], fin["n_before_prox"], fin["n_after_prox"],
                     fin["distal_snr_gain"])
        except Exception as e:  # noqa: BLE001
            log.exception("trial %d SKIPPED in pass2: %s", ti, e)

    if not results:
        log.error("no results in pass2; abort")
        print("ERROR: no results")
        return 2

    # ---- aggregates: Wilcoxon + gain/lose/tie -----------------------------
    nb = np.array([r["n_before"] for r in results], float)
    na = np.array([r["n_after"] for r in results], float)
    nbd = np.array([r["n_before_distal"] for r in results], float)
    nad = np.array([r["n_after_distal"] for r in results], float)
    nbp = np.array([r["n_before_prox"] for r in results], float)
    nap = np.array([r["n_after_prox"] for r in results], float)

    def wilcox(before, after):
        d = after - before
        if np.all(d == 0):
            return {"statistic": None, "pvalue": None, "note": "all differences zero"}
        try:
            res = sp_stats.wilcoxon(after, before, zero_method="wilcox", alternative="two-sided")
            return {"statistic": float(res.statistic), "pvalue": float(res.pvalue)}
        except Exception as e:  # noqa: BLE001
            return {"statistic": None, "pvalue": None, "note": str(e)}

    wil_overall = wilcox(nb, na)
    wil_distal = wilcox(nbd, nad)
    wil_prox = wilcox(nbp, nap)

    gain = int(np.sum(na > nb))
    lose = int(np.sum(na < nb))
    tie = int(np.sum(na == nb))

    # ---- top-10 Figure-A candidates (by distal SNR gain) ------------------
    gains = np.array([r["distal_snr_gain"] for r in results], float)
    order = np.argsort(-gains)
    top10_idx = [int(results[i]["trial_index"]) for i in order[:TOP_N]]
    top10_gain = [float(results[i]["distal_snr_gain"]) for i in order[:TOP_N]]

    # ---- M2: honest distal-SNR-gain accounting (do not massage) -----------
    finite_gains = gains[np.isfinite(gains)]
    n_pos_gain = int(np.sum(finite_gains > 0))
    n_neg_gain = int(np.sum(finite_gains < 0))
    n_zero_gain = int(np.sum(finite_gains == 0))
    gain_min = float(np.min(finite_gains)) if finite_gains.size else None
    gain_median = float(np.median(finite_gains)) if finite_gains.size else None
    gain_max = float(np.max(finite_gains)) if finite_gains.size else None
    log.info("distal SNR gain: pos=%d neg=%d zero=%d  min=%s median=%s max=%s",
             n_pos_gain, n_neg_gain, n_zero_gain, gain_min, gain_median, gain_max)

    # ---- m4: drift-window residual validation artifact --------------------
    write_drift_validation(pts, log)

    # ---- write h5 ----------------------------------------------------------
    write_h5(results, params, agg_meta, log)

    # ---- write stats json --------------------------------------------------
    drift_ts_list = [r["drift_ts"] for r in results if np.isfinite(r["drift_ts"])]
    stats = {
        "generator": GENERATOR,
        "plume_common_version": pc.VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_aggregate_path": agg_meta.get("aggregate_path", ""),
        "seed": int(pc.SEED),
        "n_trials_processed": len(results),
        "params": {
            "Fs_hz": FS, "drift_window_s": DRIFT_W_S, "drift_percentile": DRIFT_PCTILE,
            "template_half_window_s": TMPL_HALF_S, "template_len_samples": L,
            "template_k_mad": TMPL_K, "near_dist_pctile": NEAR_DIST_PCTILE,
            "refractory_s": REFRACTORY_S,
            "target_fpr_max_per_s": TARGET_FPR_MAX, "k_grid": K_GRID,
            "before_thresh_rule": "k_used * MAD(quiet far-from-source drift-corrected baseline)",
            "distal_rule": "head-endpoint distance (sensor clock) > per-trial MEDIAN",
            "snr_def": "peak_amp / plume_common.mad(local +/-1s quiet window of SAME trace); dimensionless, identical before/after",
            "far_dist_pctile": FAR_DIST_PCTILE, "baseline_amp_frac": BASELINE_AMP_FRAC,
        },
        "calibration": {
            "k_used": params["k_used"],
            "baseline_mad": params["baseline_mad"],
            "k_scan": params["k_scan"],
        },
        "thresholds": {"before": params["thr_before"], "after": params["thr_after"]},
        "pooled_baseline_fpr_before": params["baseline_fpr_before"],
        "pooled_baseline_fpr_after": params["baseline_fpr_after"],
        "H5_guard_after_le_before": bool(params["baseline_fpr_after"] <= params["baseline_fpr_before"] + 1e-9),
        "n_baseline_segments": len(before_segs),
        "baseline_total_duration_s": total_base_dur,
        "wilcoxon": {"overall": wil_overall, "distal_only": wil_distal, "proximal_only": wil_prox},
        "counts": {
            "trials_gaining": gain, "trials_losing": lose, "trials_tying": tie,
            "total_before": int(nb.sum()), "total_after": int(na.sum()),
            "total_before_distal": int(nbd.sum()), "total_after_distal": int(nad.sum()),
            "total_before_prox": int(nbp.sum()), "total_after_prox": int(nap.sum()),
        },
        "distal_snr_gain_summary": {
            "n_trials_positive_gain": n_pos_gain,
            "n_trials_negative_gain": n_neg_gain,
            "n_trials_zero_gain": n_zero_gain,
            "gain_min": gain_min,
            "gain_median": gain_median,
            "gain_max": gain_max,
        },
        "top10_figureA_trial_indices": top10_idx,
        "top10_figureA_distal_snr_gain": top10_gain,
        "template": {
            "pooled_unit_energy": template.tolist(),
            "n_contributing_trials": len(contributions),
            "per_location": per_loc_templates,
        },
        "median_drift_timescale_s": float(np.median(drift_ts_list)) if drift_ts_list else None,
        "per_trial": [
            {
                "trial_index": r["trial_index"], "group": r["group"], "file_name": r["file_name"],
                "n_before": r["n_before"], "n_after": r["n_after"],
                "n_before_distal": r["n_before_distal"], "n_after_distal": r["n_after_distal"],
                "n_before_prox": r["n_before_prox"], "n_after_prox": r["n_after_prox"],
                "distal_snr_gain": r["distal_snr_gain"],
                "thresholds_before": params["thr_before"], "thresholds_after": params["thr_after"],
                "baseline_fpr_before": params["baseline_fpr_before"],
                "baseline_fpr_after": params["baseline_fpr_after"],
                "W_used": r["W_used"],
                "drift_timescale_s": float(r["drift_ts"]) if np.isfinite(r["drift_ts"]) else None,
                "median_dist_px": r["med_dist"] if np.isfinite(r["med_dist"]) else None,
            }
            for r in results
        ],
    }
    tmp = STATS_OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2, allow_nan=True)
    os.replace(tmp, STATS_OUT)
    log.info("wrote %s", STATS_OUT)

    # ---- short summary -----------------------------------------------------
    print(f"processed {len(results)} trials")
    print(f"k_used={params['k_used']:.1f}  baseline_MAD={params['baseline_mad']:.6g}")
    print(f"H5 guard (after<=before): {stats['H5_guard_after_le_before']}  "
          f"fpr_before={params['baseline_fpr_before']:.5f}/s fpr_after={params['baseline_fpr_after']:.5f}/s")
    print(f"thr_before={params['thr_before']:.6g} thr_after={params['thr_after']:.6g}")
    print(f"per-trial n_before: min={int(nb.min())} median={int(np.median(nb))} max={int(nb.max())}")
    print(f"per-trial n_after:  min={int(na.min())} median={int(np.median(na))} max={int(na.max())}")
    print(f"Wilcoxon overall: stat={wil_overall.get('statistic')} p={wil_overall.get('pvalue')}")
    print(f"Wilcoxon distal:  stat={wil_distal.get('statistic')} p={wil_distal.get('pvalue')}")
    print(f"gain/lose/tie = {gain}/{lose}/{tie}   total before={int(nb.sum())} after={int(na.sum())}")
    print(f"distal before/after totals = {int(nbd.sum())}/{int(nad.sum())}")
    print(f"distal SNR gain: pos={n_pos_gain} neg={n_neg_gain} zero={n_zero_gain}  "
          f"min={gain_min} median={gain_median} max={gain_max}")
    print(f"top10 Figure-A trial indices: {top10_idx}")
    md = stats["median_drift_timescale_s"]
    print(f"median drift timescale = {md:.2f}s   W_used(samples)={results[0]['W_used']}")
    log.info("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
