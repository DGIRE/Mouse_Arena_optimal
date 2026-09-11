"""Diagnostic: understand the de-jump over-removal. Read-only."""
import sys, numpy as np
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import plume_common as pc

trials, meta = pc.load_trials()
Q = pc.pooled_dejump_Q(trials, "head")
print("pooled Q_head (99.5pct) =", round(Q, 3), "px")

# step distribution among box-kept samples, pooled
allsteps = []
for tr in trials:
    xy = np.asarray(tr["head"], float)
    m = pc._in_box(xy)
    kept = xy[m]
    if kept.shape[0] >= 2:
        allsteps.append(np.linalg.norm(np.diff(kept, axis=0), axis=1))
allsteps = np.concatenate(allsteps)
for p in [50, 90, 95, 99, 99.5, 99.9]:
    print(f"  step pctile {p}: {np.percentile(allsteps, p):.3f} px")
print("  mean step", round(allsteps.mean(), 3), "max", round(allsteps.max(), 1))
print("  frac steps > Q:", round((allsteps > Q).mean(), 4))

# compare current (anchor-stall) vs consecutive-diff removal on a few trials
def consec_diff_keep(xy, Q):
    m = pc._in_box(xy)
    idx = np.nonzero(m)[0]
    if idx.size < 2:
        return idx
    k = xy[idx]
    step = np.r_[0.0, np.linalg.norm(np.diff(k, axis=0), axis=1)]
    return idx[step <= Q]

print("\ntrial : n_total  box  anchor_keep  consec_keep")
for i in [0, 1, 2, 40, 94]:
    tr = trials[i]
    xy = np.asarray(tr["head"], float)
    t = np.asarray(tr["head_time"], float)
    n, nb, na = pc.clean_counts(xy, t, Q)
    nc = consec_diff_keep(xy, Q).size
    print(f"  {i:3d} : {n:6d}  {nb:5d}  {na:6d}      {nc:6d}")
