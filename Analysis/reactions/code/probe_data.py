"""Reactions analysis — pre-planning probe. Confirms request premises + gathers
velocity/R/sweep sanity numbers. Read-only. Writes data/_probe.json. Run with "$AR_PY".
"""
import sys, os, json
import numpy as np
from scipy.signal import savgol_filter, find_peaks

sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import plume_common as pc

OUT_DIR = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions\data"
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "_probe.json")

SG_WIN, SG_POLY = 7, 2
R_HEIGHT, R_PROM, REFRACTORY_S = 1.5, 0.5, 0.30


def speed_savgol(xy, dt):
    if xy.shape[0] < SG_WIN:
        return np.full(xy.shape[0], np.nan)
    vx = savgol_filter(xy[:, 0], SG_WIN, SG_POLY, deriv=1, delta=dt)
    vy = savgol_filter(xy[:, 1], SG_WIN, SG_POLY, deriv=1, delta=dt)
    return np.hypot(vx, vy)


def main():
    trials, meta = pc.load_trials()
    # accessor gives all 114; confirm lighting via accessor behavior filter
    trials_ir = pc.load_trials()[0]  # same; lighting filter not needed (all infrared)
    rep = {"n_trials": len(trials), "schema_version": meta["schema_version"], "Fs": meta["Fs"]}

    groups = pc.group_trials(trials)
    ginfo = pc.validate_groups(groups)
    rep["groups"] = {g: int(v["n"]) for g, v in ginfo.items()}
    rep["loc_sum_1_6"] = int(sum(v["n"] for g, v in ginfo.items() if g.startswith("Loc")))

    Qb = pc.pooled_dejump_Q(trials, "body")
    Qh = pc.pooled_dejump_Q(trials, "head")
    rep["dejump_Q_body_px"] = float(Qb)
    rep["dejump_Q_head_px"] = float(Qh)

    v_com_all, v_nose_all, R_all, bframe_all = [], [], [], []
    dt_head = []
    sweep_counts, sweep_rates, body_removed, head_removed = [], [], [], []
    eth_min, eth_max, ethd_min, ethd_max = [], [], [], []

    for tr in trials:
        ht = np.asarray(tr["head_time"], float)
        bt = np.asarray(tr["body_time"], float)
        eth = np.asarray(tr["ethanol"], float); ethd = np.asarray(tr["ethdeconv"], float)
        eth_min.append(np.nanmin(eth)); eth_max.append(np.nanmax(eth))
        ethd_min.append(np.nanmin(ethd)); ethd_max.append(np.nanmax(ethd))

        idx_h, head_c, ht_c = pc.clean_track(np.asarray(tr["head"], float), ht, Qh)
        idx_b, body_c, bt_c = pc.clean_track(np.asarray(tr["body"], float), bt, Qb)
        _, nhbox, nhkeep = pc.clean_counts(np.asarray(tr["head"], float), ht, Qh)
        _, nbbox, nbkeep = pc.clean_counts(np.asarray(tr["body"], float), bt, Qb)
        if nhbox: head_removed.append(1 - nhkeep / nhbox)
        if nbbox: body_removed.append(1 - nbkeep / nbbox)
        if head_c.shape[0] < SG_WIN + 2:
            continue
        dt = float(np.median(np.diff(ht_c)))
        dt_head.append(dt)
        # body onto head clock (cleaned)
        body_h = np.column_stack([np.interp(ht_c, bt_c, body_c[:, 0]),
                                  np.interp(ht_c, bt_c, body_c[:, 1])])
        v_nose = speed_savgol(head_c, dt)
        v_com = speed_savgol(body_h, dt)
        bframe = speed_savgol(head_c - body_h, dt)   # body-frame nose speed (D7)
        v_com_all.append(v_com); v_nose_all.append(v_nose); bframe_all.append(bframe)

    # pool
    v_com_pool = np.concatenate(v_com_all); v_nose_pool = np.concatenate(v_nose_all)
    v_floor = float(np.nanpercentile(v_com_pool, 10))
    rep["v_floor_px_s"] = v_floor

    # second pass: R with v_floor + sweeps
    binding = []
    for v_nose, v_com in zip(v_nose_all, v_com_all):
        denom = np.maximum(v_com, v_floor)
        R = v_nose / denom
        R_all.append(R)
        binding.append(np.mean(v_com < v_floor))
        dt = np.median(dt_head)
        dist = max(1, int(round(REFRACTORY_S / dt)))
        Rc = np.where(np.isfinite(R), R, 0.0)
        pk, _ = find_peaks(Rc, height=R_HEIGHT, prominence=R_PROM, distance=dist)
        sweep_counts.append(len(pk))
        # rate: peaks / trial duration on head clock

    def pct(a, ps=(1, 50, 90, 99)):
        a = np.asarray(a, float); a = a[np.isfinite(a)]
        return {str(p): float(np.percentile(a, p)) for p in ps}

    rep["v_com_px_s_pct"] = pct(v_com_pool)
    rep["v_nose_px_s_pct"] = pct(v_nose_pool)
    rep["bframe_nose_px_s_pct"] = pct(np.concatenate(bframe_all))
    rep["R_pct"] = pct(np.concatenate(R_all))
    rep["v_floor_binding_frac_mean"] = float(np.mean(binding))
    rep["sweep_count_per_trial"] = {"min": int(np.min(sweep_counts)),
                                    "median": float(np.median(sweep_counts)),
                                    "max": int(np.max(sweep_counts))}
    rep["median_dt_head_s"] = float(np.median(dt_head))
    rep["body_dejump_removed_frac_mean"] = float(np.mean(body_removed))
    rep["head_dejump_removed_frac_mean"] = float(np.mean(head_removed))
    rep["ethanol_range"] = [float(np.min(eth_min)), float(np.max(eth_max))]
    rep["ethdeconv_range"] = [float(np.min(ethd_min)), float(np.max(ethd_max))]
    rep["loc_attr_all_nan"] = bool(np.all([np.isnan(tr["loc"]) for tr in trials]))
    rep["odor_fields_h5_present"] = os.path.exists(
        r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5")
    rep["odor_reached_cutoff"] = 0.001

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
