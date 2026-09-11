"""Trajectory analysis — pre-planning probe. Confirms the request's asserted data
facts against the real aggregate and gathers a few planning numbers. Read-only.
Writes data/_probe.json and prints a summary. Run with "$AR_PY".
"""
import sys, os, json
import numpy as np

# reuse the validated Plume-locations shared library for load/group/clean/align/mad
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import plume_common as pc

OUT_DIR = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories\data"
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "_probe.json")


def main():
    trials, meta = pc.load_trials()
    rep = {"n_trials": len(trials), "schema_version": meta["schema_version"],
           "Fs": meta["Fs"]}

    # grouping
    groups = pc.group_trials(trials)
    ginfo = pc.validate_groups(groups)
    rep["groups"] = {g: int(v["n"]) for g, v in ginfo.items()}
    rep["loc_sum_1_6"] = int(sum(v["n"] for g, v in ginfo.items() if g.startswith("Loc")))
    rep["endpoints"] = {g: [round(float(x), 1) for x in v["endpoint"]]
                        for g, v in ginfo.items() if g.startswith("Loc")}

    # clocks + ranges
    dt_head, dt_body, dt_eth = [], [], []
    eth_min, eth_max, ethd_min, ethd_max, thr = [], [], [], [], []
    # de-jump removal fraction on BODY (D1 track) and HEAD, using advancing-ref rule
    Qb = pc.pooled_dejump_Q(trials, "body")
    Qh = pc.pooled_dejump_Q(trials, "head")
    body_removed, head_removed = [], []
    headbody_norm = []   # ||head-body|| after interpolating body onto head clock
    theta_sample = []    # sanity: theta distribution on a few trials
    cov_frac = []        # head-in-sensor-coverage

    for i, tr in enumerate(trials):
        ht = np.asarray(tr["head_time"], float)
        bt = np.asarray(tr["body_time"], float)
        et = np.asarray(tr["ethanol_time"], float)
        if len(ht) > 1: dt_head.append(np.median(np.diff(ht)))
        if len(bt) > 1: dt_body.append(np.median(np.diff(bt)))
        if len(et) > 1: dt_eth.append(np.median(np.diff(et)))
        eth = np.asarray(tr["ethanol"], float); ethd = np.asarray(tr["ethdeconv"], float)
        eth_min.append(np.nanmin(eth)); eth_max.append(np.nanmax(eth))
        ethd_min.append(np.nanmin(ethd)); ethd_max.append(np.nanmax(ethd))
        thr.append(tr["threshold"])

        # de-jump removal fractions
        n_b, nb_box, nb_keep = pc.clean_counts(np.asarray(tr["body"], float), bt, Qb)
        n_h, nh_box, nh_keep = pc.clean_counts(np.asarray(tr["head"], float), ht, Qh)
        if nb_box > 0: body_removed.append(1 - nb_keep / nb_box)
        if nh_box > 0: head_removed.append(1 - nh_keep / nh_box)

        # coverage
        cov = (ht >= et.min()) & (ht <= et.max())
        cov_frac.append(float(cov.mean()))

        # geometry sanity on first 6 trials: body interp onto head clock, u=head-body,
        # s=endpoint-body, theta; report median theta and median when close to source
        if i < 6:
            hb = np.column_stack([np.interp(ht, bt, np.asarray(tr["body"])[:, 0]),
                                  np.interp(ht, bt, np.asarray(tr["body"])[:, 1])])
            head = np.asarray(tr["head"], float)
            u = head - hb
            un = np.linalg.norm(u, axis=1)
            ok = un >= 1.0
            S = pc.endpoint_of(tr)
            s = S[None, :] - hb
            sn = np.linalg.norm(s, axis=1)
            ok &= sn >= 1.0
            uu = u[ok] / un[ok, None]; ss = s[ok] / sn[ok, None]
            dot = np.clip(np.sum(uu * ss, axis=1), -1, 1)
            th = np.degrees(np.arccos(dot))
            headbody_norm.append(float(np.median(un[np.isfinite(un)])))
            # theta when animal is in the nearest 20% of its distance-to-source
            d = sn[ok]
            near = d <= np.percentile(d, 20)
            theta_sample.append({"trial": i, "theta_median": float(np.median(th)),
                                 "theta_median_near": float(np.median(th[near])),
                                 "n": int(ok.sum())})

    rep["median_dt_head_s"] = float(np.median(dt_head))
    rep["median_dt_body_s"] = float(np.median(dt_body))
    rep["median_dt_eth_s"] = float(np.median(dt_eth))
    rep["ethanol_range"] = [float(np.min(eth_min)), float(np.max(eth_max))]
    rep["ethdeconv_range"] = [float(np.min(ethd_min)), float(np.max(ethd_max))]
    rep["threshold_median"] = float(np.nanmedian(thr))
    rep["dejump_Q_body_px"] = float(Qb)
    rep["dejump_Q_head_px"] = float(Qh)
    rep["body_dejump_removed_frac"] = [float(np.min(body_removed)), float(np.mean(body_removed)), float(np.max(body_removed))]
    rep["head_dejump_removed_frac"] = [float(np.min(head_removed)), float(np.mean(head_removed)), float(np.max(head_removed))]
    rep["head_in_sensor_coverage_frac"] = [float(np.min(cov_frac)), float(np.mean(cov_frac))]
    rep["headbody_norm_median_px_first6"] = headbody_norm
    rep["theta_sanity_first6"] = theta_sample
    rep["loc_attr_all_nan"] = bool(np.all([np.isnan(tr["loc"]) for tr in trials]))
    rep["duration_attr_all_nan"] = bool(np.all([np.isnan(tr["duration"]) for tr in trials]))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
