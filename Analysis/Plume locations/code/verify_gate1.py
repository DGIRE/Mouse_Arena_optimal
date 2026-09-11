r"""Gate-1 independent re-derivation. Uses accessor + plume_common ONLY for
load/group/clean/align; recomputes the two headline statistics independently."""
import sys, json, os
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\DATA\code")
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import numpy as np
import h5py
import plume_common as pc

DATA = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data"

trials, meta = pc.load_trials()
groups = pc.group_trials(trials)
Q_head = pc.pooled_dejump_Q(trials, "head")

# ============ TASK 1: recompute Loc6 mean at one valid bin ============
f = h5py.File(os.path.join(DATA, "odor_fields.h5"), "r")
g = f["Loc6"]
L = int(g.attrs["bin_size_px"])
x_edges = g["x_edges"][()]; y_edges = g["y_edges"][()]
mean_stored = g["mean"][()]; count_stored = g["count"][()]
nx = x_edges.size - 1

# choose target valid bin
valid = np.argwhere((count_stored >= 3) & np.isfinite(mean_stored))
R, C = valid[len(valid) // 2]
print(f"[T1] target bin row={R} col={C} L={L}")

# independently pool ethdeconv samples in that bin across Loc6 trials
pooled_vals = []
n_trials_in_bin = 0
for tr in groups["Loc6"]:
    head = np.asarray(tr["head"], float); ht = np.asarray(tr["head_time"], float)
    idx, xy, t = pc.clean_track(head, ht, Q_head)
    if idx.size == 0:
        continue
    eth = pc.align_signal(t, np.asarray(tr["ethanol_time"], float),
                          np.asarray(tr["ethdeconv"], float))
    cov = np.isfinite(eth)
    xy = xy[cov]; eth = eth[cov]
    if xy.shape[0] == 0:
        continue
    # my own binning (independent of build script): floor division on edges
    col = np.clip(((xy[:, 0] - x_edges[0]) / L).astype(int), 0, nx - 1)
    row = np.clip(((xy[:, 1] - y_edges[0]) / L).astype(int), 0, y_edges.size - 2)
    sel = (row == R) & (col == C)
    if sel.any():
        pooled_vals.append(eth[sel])
        n_trials_in_bin += 1

pooled_vals = np.concatenate(pooled_vals) if pooled_vals else np.array([])
my_mean = float(pooled_vals.mean())
print(f"[T1] my_mean={my_mean:.10g}  stored={mean_stored[R,C]:.10g}  "
      f"diff={abs(my_mean-mean_stored[R,C]):.2e}")
print(f"[T1] my_trial_count={n_trials_in_bin}  stored_count={count_stored[R,C]}")
f.close()

# ============ TASK 2: recompute n_before for one trial ============
st = json.load(open(os.path.join(DATA, "enhancement_stats.json")))
thr_before = st["thresholds"]["before"]
per = {p["trial_index"]: p for p in st["per_trial"]}

# pick a trial that has some before-encounters
target_ti = None
for p in st["per_trial"]:
    if p["n_before"] > 0:
        target_ti = p["trial_index"]; break
print(f"[T2] target trial={target_ti} stored n_before={per[target_ti]['n_before']} thr_before={thr_before}")

FS = 500.0
import pandas as pd
tr = next(t for t in trials if int(t["trial_index"]) == target_ti)
raw = np.asarray(tr["ethanol"], float)
et = np.asarray(tr["ethanol_time"], float)
W = int(min(max(round(20.0 * FS), 3), raw.size))
# independent rolling 10th pctile
base = pd.Series(raw).rolling(window=W, min_periods=1, center=True).quantile(0.10).to_numpy()
dc = raw - base
pk = pc.detect_encounters(dc, et, thresh=thr_before, refractory_s=0.2, min_prominence=1e-12)
print(f"[T2] my n_before={pk.size}  stored={per[target_ti]['n_before']}")

# H5 guard check from stats
print(f"[T2] FPR before={st['pooled_baseline_fpr_before']:.5f} after={st['pooled_baseline_fpr_after']:.5f} "
      f"guard_ok={st['H5_guard_after_le_before']}")
