"""One-off data probe: verify request claims before planning. Read-only.
Outputs a JSON + text summary to Plume locations/data/_probe.json and prints tail.
"""
import sys, os, json, re
import numpy as np

sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\DATA\code")
from mouse_arena_aggregate_io import Aggregate

H5 = r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5"
OUT = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\_probe.json"

ARENA = (0, 580, 0, 280)


def loc_of(fn):
    m = re.search(r"_Loc(\d+)", fn)
    if m:
        return "Loc" + m.group(1)
    if "anotherLoc" in fn:
        return "anotherLoc"
    return "UNKNOWN"


def main():
    agg = Aggregate(H5)
    print(agg.summary())
    trials = agg.behavior()
    rep = {}
    rep["n_trials"] = len(trials)
    rep["schema_version"] = agg.schema_version
    rep["Fs"] = agg.Fs
    rep["reference"] = agg.reference

    # field presence + shapes of first trial
    t0 = trials[0]
    rep["fields"] = sorted([k for k in t0.keys()])
    rep["shapes_t0"] = {k: (list(np.shape(t0[k])) if hasattr(t0[k], "shape") else "scalar")
                        for k in ["head", "head_time", "body", "body_time", "ethanol",
                                  "ethanol_time", "ethdeconv", "endpoint"] if k in t0}

    # grouping + endpoint spread
    groups = {}
    for tr in trials:
        g = loc_of(tr["file_name"])
        groups.setdefault(g, []).append(tr)
    grp_info = {}
    for g, lst in sorted(groups.items()):
        eps = np.array([tr["endpoint"] for tr in lst], float)
        grp_info[g] = {
            "n": len(lst),
            "endpoint_mean": eps.mean(0).round(1).tolist(),
            "endpoint_spread_px": (eps.max(0) - eps.min(0)).round(1).tolist(),
        }
    rep["groups"] = grp_info

    # signal scales (pooled over all trials)
    eth_all, ethd_all, thr_all = [], [], []
    head_out_frac, cov_frac = [], []
    dt_head, dt_eth = [], []
    for tr in trials:
        eth = np.asarray(tr["ethanol"], float)
        ethd = np.asarray(tr["ethdeconv"], float)
        eth_all.append([np.nanmin(eth), np.nanmax(eth)])
        ethd_all.append([np.nanmin(ethd), np.nanmax(ethd)])
        thr_all.append(tr["threshold"])
        head = np.asarray(tr["head"], float)
        x, y = head[:, 0], head[:, 1]
        inbox = (x >= 0) & (x <= 580) & (y >= 0) & (y <= 280) & np.isfinite(x) & np.isfinite(y)
        head_out_frac.append(1 - inbox.mean())
        ht = np.asarray(tr["head_time"], float)
        et = np.asarray(tr["ethanol_time"], float)
        # coverage: head samples within sensor time span
        cov = (ht >= et.min()) & (ht <= et.max())
        cov_frac.append(cov.mean())
        if len(ht) > 1:
            dt_head.append(np.median(np.diff(ht)))
        if len(et) > 1:
            dt_eth.append(np.median(np.diff(et)))

    eth_all = np.array(eth_all); ethd_all = np.array(ethd_all)
    rep["ethanol_range"] = [float(eth_all[:, 0].min()), float(eth_all[:, 1].max())]
    rep["ethdeconv_range"] = [float(ethd_all[:, 0].min()), float(ethd_all[:, 1].max())]
    rep["threshold_range"] = [float(np.nanmin(thr_all)), float(np.nanmedian(thr_all)), float(np.nanmax(thr_all))]
    rep["head_out_of_box_frac"] = [float(np.min(head_out_frac)), float(np.mean(head_out_frac)), float(np.max(head_out_frac))]
    rep["head_in_sensor_coverage_frac"] = [float(np.min(cov_frac)), float(np.mean(cov_frac)), float(np.max(cov_frac))]
    rep["median_dt_head_s"] = float(np.median(dt_head))
    rep["median_dt_eth_s"] = float(np.median(dt_eth))

    # loc & duration attrs NaN check
    rep["loc_attr_all_nan"] = bool(np.all([np.isnan(tr["loc"]) for tr in trials]))
    rep["duration_attr_all_nan"] = bool(np.all([np.isnan(tr["duration"]) for tr in trials]))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print("\n=== PROBE SUMMARY ===")
    print(json.dumps(rep, indent=2))
    agg.close()


if __name__ == "__main__":
    main()
