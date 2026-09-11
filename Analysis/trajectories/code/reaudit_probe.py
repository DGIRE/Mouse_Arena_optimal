r"""reaudit_probe.py -- independent re-derivation of encounter diagnostics from the
h5 ONLY (no build_metrics logic reused). Confirms onset_ethd_median and
frac_onsets_above_0p01 for the pooled Loc1-6 set, plus a few regression spot checks.
"""
import json, os
import numpy as np
import h5py

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories"
H5 = os.path.join(BASE, "data", "trajectory_metrics.h5")
STATS = os.path.join(BASE, "data", "stats.json")

with open(STATS) as fh:
    stats = json.load(fh)

onset_vals = []          # ethd_h at onset_idx, pooled Loc1-6
pertrial_medians = []
n_onsets_total = 0
theta_min, theta_max = np.inf, -np.inf
n_pooled = 0

with h5py.File(H5, "r") as f:
    print("build_complete attr:", f.attrs.get("build_complete"))
    print("h5 threshold attr:", float(f.attrs.get("threshold")))
    print("h5 k attr:", int(f.attrs.get("k")))
    print("h5 seed attr:", int(f.attrs.get("seed")))
    trials = f["trials"]
    for key in trials:
        g = trials[key]
        in_pooled = bool(g.attrs["in_pooled"])
        th = np.asarray(g["theta"])
        thf = th[np.isfinite(th)]
        if thf.size:
            theta_min = min(theta_min, float(thf.min()))
            theta_max = max(theta_max, float(thf.max()))
        if not in_pooled:
            continue
        n_pooled += 1
        ethd = np.asarray(g["ethd_h"], float)
        oi = np.asarray(g["onset_idx"], int)
        if oi.size:
            ov = ethd[oi]
            ov = ov[np.isfinite(ov)]
            onset_vals.append(ov)
            n_onsets_total += ov.size
        ethd_fin = ethd[np.isfinite(ethd)]
        if ethd_fin.size:
            pertrial_medians.append(float(np.median(ethd_fin)))

onset_pool = np.concatenate(onset_vals) if onset_vals else np.array([])
pertrial_medians = np.asarray(pertrial_medians)

onset_median = float(np.median(onset_pool))
frac_above = float(np.mean(onset_pool > 0.01))
pertrial_med_med = float(np.median(pertrial_medians))

print("\n=== INDEPENDENT RE-DERIVATION (from h5, pooled Loc1-6) ===")
print("n_pooled_trials         :", n_pooled)
print("n_onsets_pooled         :", int(onset_pool.size))
print("onset_ethd_median       :", onset_median)
print("frac_onsets_above_0p01  :", frac_above)
print("pertrial_ethd_med_median:", pertrial_med_med)
print("theta global range      : [%.4f, %.4f]" % (theta_min, theta_max))

d = stats["encounter_diagnostics"]
print("\n=== STORED (stats.json encounter_diagnostics) ===")
print("n_onsets_pooled         :", d["n_onsets_pooled"])
print("onset_ethd_median       :", d["onset_ethd_median"])
print("frac_onsets_above_0p01  :", d["frac_onsets_above_0p01"])
print("pertrial_ethd_med_median:", d["pertrial_ethd_median_median"])
print("calibrated_threshold    :", d["calibrated_threshold"])
print("signal_max_ref          :", d["signal_max_ref"])
print("n_encounters_amp        :", d["n_encounters_amp"])

def match(a, b, tol=1e-9):
    return "MATCH" if abs(a-b) <= tol*max(1, abs(b)) else "MISMATCH"

print("\n=== COMPARISON ===")
print("onset_ethd_median       :", match(onset_median, d["onset_ethd_median"]))
print("frac_onsets_above_0p01  :", match(frac_above, d["frac_onsets_above_0p01"]))
print("n_onsets_pooled         :", "MATCH" if int(onset_pool.size)==d["n_onsets_pooled"] else "MISMATCH")
print("pertrial_ethd_med_median:", match(pertrial_med_med, d["pertrial_ethd_median_median"]))
print("threshold vs h5 attr    :", match(d["calibrated_threshold"], stats["calibration"]["threshold"]))
