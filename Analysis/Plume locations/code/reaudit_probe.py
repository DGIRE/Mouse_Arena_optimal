r"""reaudit_probe.py -- INDEPENDENT re-audit (Gate 2, iteration 1).
Re-derives FPR before/after from stored H5 traces, chosen_L for >=2 locations,
and regression invariants. Does NOT trust stats narratives.
Run with $AR_PY.
"""
import json, os, sys
import numpy as np
import h5py

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations"
CODE = os.path.join(BASE, "code")
DATA = os.path.join(BASE, "data")
sys.path.insert(0, CODE)
import plume_common as pc

ENH_H5 = os.path.join(DATA, "enhanced_ethanol.h5")
FLD_H5 = os.path.join(DATA, "odor_fields.h5")
ENH_STATS = json.load(open(os.path.join(DATA, "enhancement_stats.json")))

FS = 500.0
FAR_DIST_PCTILE = 80.0
BASELINE_AMP_FRAC = 0.20
REFRACTORY_S = 0.2

def contiguous_runs(idx):
    if idx.size == 0: return []
    runs=[]; start=prev=idx[0]
    for i in idx[1:]:
        if i==prev+1: prev=i
        else: runs.append((start,prev)); start=prev=i
    runs.append((start,prev)); return runs

def baseline_quiet_idx(dist_sensor, drift_corr, covered):
    if not covered.any(): return None
    far_cut = np.percentile(dist_sensor[covered], FAR_DIST_PCTILE)
    far_mask = covered & (dist_sensor > far_cut)
    if far_mask.sum() < 5: return None
    amp = np.abs(drift_corr)
    far_idx = np.nonzero(far_mask)[0]
    amp_thr = np.percentile(amp[far_idx], BASELINE_AMP_FRAC*100.0)
    q = far_idx[amp[far_idx] <= amp_thr]
    if q.size < 5: q = far_idx
    return q

def rate_on(seglist, segtimes, thr):
    tot_n=0; tot_dur=0.0
    for sig,tt in zip(seglist,segtimes):
        if sig.size<3: continue
        pk = pc.detect_encounters(sig, tt, thresh=thr, refractory_s=REFRACTORY_S, min_prominence=1e-12)
        tot_n += int(pk.size)
        tot_dur += float(tt[-1]-tt[0]) if tt.size>=2 else 0.0
    return (tot_n/tot_dur if tot_dur>0 else 0.0), tot_n, tot_dur

# ---- reload trials to recompute dist_sensor / drift baseline independently ----
trials, meta = pc.load_trials()
Q = pc.pooled_dejump_Q(trials, "head")
by_ti = {int(tr["trial_index"]): tr for tr in trials}

thr_before = ENH_STATS["thresholds"]["before"]
thr_after  = ENH_STATS["thresholds"]["after"]
print("stored thr_before=%.6g thr_after=%.6g" % (thr_before, thr_after))

before_segs, before_times, after_segs, after_times = [], [], [], []
with h5py.File(ENH_H5, "r") as f:
    print("H5 build_complete =", int(f.attrs["build_complete"]))
    print("H5 baseline_fpr_before(attr)=%.6g after(attr)=%.6g" %
          (float(f.attrs["baseline_fpr_before"]), float(f.attrs["baseline_fpr_after"])))
    tg = f["trials"]
    n_groups = len(tg.keys())
    for gid in tg.keys():
        g = tg[gid]
        ti = int(gid)
        drift_corr = np.asarray(g["drift_corrected"], float)
        enhanced   = np.asarray(g["enhanced"], float)
        et         = np.asarray(g["time"], float)
        # recompute dist_sensor from stored head + endpoint
        head = np.asarray(g["head"], float)
        head_time = np.asarray(g["head_time"], float)
        endpoint = np.asarray(g["endpoint"], float).reshape(2)
        hx = pc.align_signal(et, head_time, head[:,0])
        hy = pc.align_signal(et, head_time, head[:,1])
        dist_sensor = np.hypot(hx-endpoint[0], hy-endpoint[1])
        covered = np.isfinite(dist_sensor)
        q = baseline_quiet_idx(dist_sensor, drift_corr, covered)
        if q is None: continue
        for (a,b) in contiguous_runs(np.sort(q)):
            if b-a+1 < 3: continue
            before_segs.append(drift_corr[a:b+1]); before_times.append(et[a:b+1])
            after_segs.append(enhanced[a:b+1]);   after_times.append(et[a:b+1])

print("n_trial_groups in H5 =", n_groups)
fpr_b, nb, durb = rate_on(before_segs, before_times, thr_before)
fpr_a, na, dura = rate_on(after_segs, after_times, thr_after)
print("RE-DERIVED baseline FPR before = %.6f /s  (%d det / %.1f s)" % (fpr_b, nb, durb))
print("RE-DERIVED baseline FPR after  = %.6f /s  (%d det / %.1f s)" % (fpr_a, na, dura))
print("stored fpr_before=%.6f after=%.6f" %
      (ENH_STATS["pooled_baseline_fpr_before"], ENH_STATS["pooled_baseline_fpr_after"]))
print("H5 GUARD after<=before :", fpr_a <= fpr_b + 1e-9)
print("both <= 0.05/s :", fpr_b <= 0.05 and fpr_a <= 0.05)

# ---- per-trial before-count range (plausibility) ----
nbf = np.array([p["n_before"] for p in ENH_STATS["per_trial"]])
naf = np.array([p["n_after"]  for p in ENH_STATS["per_trial"]])
print("per-trial n_before: min=%d median=%d max=%d" % (nbf.min(), int(np.median(nbf)), nbf.max()))
print("per-trial n_after : min=%d median=%d max=%d" % (naf.min(), int(np.median(naf)), naf.max()))

# =================== B1: re-derive choose_L for Loc1 & Loc6 ===================
def clean_head_samples(tr, Q):
    head = np.asarray(tr["head"], float); ht = np.asarray(tr["head_time"], float)
    idx, xy, t = pc.clean_track(head, ht, Q)
    if idx.size==0: return None
    eth = pc.align_signal(t, np.asarray(tr["ethanol_time"],float), np.asarray(tr["ethdeconv"],float))
    cov = np.isfinite(eth)
    return xy[cov]

ARENA = pc.ARENA
def coverage_for_L(xy_list, L):
    xmin,xmax,ymin,ymax = ARENA
    nx=int(np.ceil((xmax-xmin)/L)); ny=int(np.ceil((ymax-ymin)/L))
    xe=xmin+L*np.arange(nx+1); ye=ymin+L*np.arange(ny+1)
    n_map=np.zeros((ny,nx),np.int64); c_map=np.zeros((ny,nx),np.int64)
    for xy in xy_list:
        if xy.shape[0]==0: continue
        col=np.clip(np.searchsorted(xe,xy[:,0],side="right")-1,0,nx-1)
        row=np.clip(np.searchsorted(ye,xy[:,1],side="right")-1,0,ny-1)
        flat=row*nx+col
        np.add.at(n_map.ravel(),flat,1)
        np.add.at(c_map.ravel(),np.unique(flat),1)
    vis=n_map>0; nvis=int(vis.sum())
    frac = float((c_map[vis]>=3).sum())/nvis if nvis>0 else 0.0
    return frac

groups = pc.group_trials(trials)
L_SCAN=[40,30,25,20,15,10]
for loc, expect in [("Loc1",15),("Loc6",10)]:
    xy_list=[]
    for tr in groups[loc]:
        s=clean_head_samples(tr,Q)
        if s is not None and s.shape[0]>0: xy_list.append(s)
    row=[]
    passing=[]
    for L in L_SCAN:
        fr=coverage_for_L(xy_list,L); row.append((L,round(fr,3)))
        if fr>=0.60: passing.append(L)
    chosen = min(passing) if passing else 40
    print("%s coverage-vs-L: %s -> chosen_L=%d (expect %d) %s" %
          (loc, row, chosen, expect, "OK" if chosen==expect else "MISMATCH"))

# =================== field h5 checks ===================
with h5py.File(FLD_H5,"r") as f:
    print("fields H5 build_complete =", int(f.attrs["build_complete"]))
    for g in ["Loc1","Loc6"]:
        grp=f[g]
        print("  %s bin_size_px=%d mean.shape=%s" %
              (g, int(grp.attrs["bin_size_px"]), grp["mean"].shape))
    print("groups present:", [k for k in f.keys()])
