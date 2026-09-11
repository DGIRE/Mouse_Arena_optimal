"""reactions_2 pre-planning probe. Confirms premises + estimates the sampling-bout
kinematics (omega, v_com percentiles) and the bout RATE at D-defaults so the plan
knows whether the D6 rarity gate passes. Read-only. Writes data/_probe.json.

Uses a lightweight inline bout detector for the rate estimate only; the real detector
lives in reactions2_common (built after planning). Run with "$AR_PY".
"""
import sys, os, json
import numpy as np
from scipy.signal import savgol_filter

sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import plume_common as pc
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\reactions\code")
import reactions_common as rc  # reuse speed_savgol, interp_xy_to_head

OUT_DIR = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2\data"
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "_probe.json")

SG_WIN, SG_POLY = 7, 2
TAU_PAUSE, DPHI_MIN, T_MERGE = 0.30, 40.0, 0.50


def bearing_omega(head_c, body_h, dt):
    d = head_c - body_h
    phi = np.degrees(np.unwrap(np.arctan2(d[:, 1], d[:, 0])))
    if phi.size < SG_WIN:
        return phi, np.full(phi.size, np.nan)
    w = SG_WIN if SG_WIN % 2 == 1 else SG_WIN + 1
    omega = np.abs(savgol_filter(phi, w, SG_POLY, deriv=1, delta=dt))
    return phi, omega


def runs_below(mask):
    """Yield (start,end_exclusive) index runs where mask is True."""
    idx = np.nonzero(mask)[0]
    if idx.size == 0:
        return []
    splits = np.nonzero(np.diff(idx) > 1)[0]
    starts = np.r_[idx[0], idx[splits + 1]]
    ends = np.r_[idx[splits], idx[-1]] + 1
    return list(zip(starts.tolist(), ends.tolist()))


def main():
    trials, meta = pc.load_trials()
    rep = {"n_trials": len(trials), "schema_version": meta["schema_version"], "Fs": meta["Fs"]}
    groups = pc.group_trials(trials)
    ginfo = pc.validate_groups(groups)
    rep["groups"] = {g: int(v["n"]) for g, v in ginfo.items()}
    rep["loc_sum_1_6"] = int(sum(v["n"] for g, v in ginfo.items() if g.startswith("Loc")))

    Qb = pc.pooled_dejump_Q(trials, "body"); Qh = pc.pooled_dejump_Q(trials, "head")

    # pass 1: pool v_com, omega
    per = []  # (v_com, omega, phi, dt, dur, head_c)
    v_com_pool, omega_pool = [], []
    dt_head = []
    body_removed, head_removed = [], []
    eth_min, eth_max = [], []
    for tr in trials:
        ht = np.asarray(tr["head_time"], float); bt = np.asarray(tr["body_time"], float)
        eth = np.asarray(tr["ethanol"], float); eth_min.append(np.nanmin(eth)); eth_max.append(np.nanmax(eth))
        idx_h, head_c, ht_c = pc.clean_track(np.asarray(tr["head"], float), ht, Qh)
        idx_b, body_c, bt_c = pc.clean_track(np.asarray(tr["body"], float), bt, Qb)
        _, nhb, nhk = pc.clean_counts(np.asarray(tr["head"], float), ht, Qh)
        _, nbb, nbk = pc.clean_counts(np.asarray(tr["body"], float), bt, Qb)
        if nhb: head_removed.append(1 - nhk / nhb)
        if nbb: body_removed.append(1 - nbk / nbb)
        if head_c.shape[0] < SG_WIN + 2:
            per.append(None); continue
        dt = float(np.median(np.diff(ht_c))); dt_head.append(dt)
        body_h = rc.interp_xy_to_head(ht_c, bt_c, body_c)
        v_com = rc.speed_savgol(body_h, dt)
        phi, omega = bearing_omega(head_c, body_h, dt)
        v_com_pool.append(v_com); omega_pool.append(omega[np.isfinite(omega)])
        dur = float(ht_c[-1] - ht_c[0]) if ht_c.size > 1 else 0.0
        per.append((v_com, omega, phi, dt, dur))

    v_com_pool = np.concatenate(v_com_pool); omega_pool = np.concatenate(omega_pool)
    v_pause = float(np.nanpercentile(v_com_pool, 25))
    omega_min = float(np.nanpercentile(omega_pool, 90))
    rep["v_pause_px_s_25pct"] = v_pause
    rep["omega_min_deg_s_90pct"] = omega_min
    rep["v_com_med_px_s"] = float(np.nanmedian(v_com_pool))
    rep["omega_med_deg_s"] = float(np.nanmedian(omega_pool))
    rep["omega_p99_deg_s"] = float(np.nanpercentile(omega_pool, 99))

    # pass 2: rough bout detection at defaults -> rate
    rates, counts = [], []
    for item in per:
        if item is None:
            continue
        v_com, omega, phi, dt, dur = item
        if dur <= 0:
            continue
        min_len = max(1, int(round(TAU_PAUSE / dt)))
        pause_mask = v_com < v_pause
        bout_times = []
        for (s, e) in runs_below(pause_mask):
            if (e - s) < min_len:
                continue
            seg_phi = phi[s:e]; seg_om = omega[s:e]
            cum = float(np.nansum(np.abs(np.diff(seg_phi)))) if seg_phi.size > 1 else 0.0
            peak = float(np.nanmax(seg_om)) if seg_om.size else 0.0
            if cum >= DPHI_MIN and peak >= omega_min:
                bout_times.append(s * dt)  # onset approx
        # merge < t_merge
        merged = 0; last = -1e9
        for bt0 in sorted(bout_times):
            if bt0 - last >= T_MERGE:
                merged += 1; last = bt0
        counts.append(merged); rates.append(merged / dur)

    rep["default_bout_count_per_trial"] = {"min": int(np.min(counts)), "median": float(np.median(counts)), "max": int(np.max(counts))}
    rep["default_bout_rate_per_s"] = {"min": float(np.min(rates)), "median": float(np.median(rates)), "max": float(np.max(rates))}
    rep["frac_trials_ge1_bout_default"] = float(np.mean([c >= 1 for c in counts]))
    rep["frac_trials_0_bout_default"] = float(np.mean([c == 0 for c in counts]))
    rep["rarity_gate_target"] = "median <= 0.3/s; tighten if >0.5/s (D6)"
    rep["v1_baseline_rate_per_s"] = 1.7
    rep["median_dt_head_s"] = float(np.median(dt_head))
    rep["body_dejump_removed_frac_mean"] = float(np.mean(body_removed))
    rep["head_dejump_removed_frac_mean"] = float(np.mean(head_removed))
    rep["ethanol_range"] = [float(np.min(eth_min)), float(np.max(eth_max))]
    rep["loc_attr_all_nan"] = bool(np.all([np.isnan(tr["loc"]) for tr in trials]))
    rep["odor_fields_h5_present"] = os.path.exists(r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
