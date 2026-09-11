r"""verify_gate1.py -- INDEPENDENT Gate-1 verification for the Trajectory analysis.

Loads raw trials via the accessor + traj_common ONLY for cleaning/interp primitives,
then RE-DERIVES geometry, calibration k-scan, and H1/H2/H3 numbers from scratch and
compares to data/stats.json + trajectory_metrics.h5. Does not import build_metrics.
"""
from __future__ import annotations
import os, sys, json
import numpy as np
from scipy import stats as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import traj_common as tc
import plume_common as pc

BASE = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(BASE, "data")
SEED = 1234
POOLED = {"Loc1","Loc2","Loc3","Loc4","Loc5","Loc6"}
PERI_LO, PERI_HI, PERI_STEP = -1.0, 1.0, 0.05

stats = json.load(open(os.path.join(DATA, "stats.json")))

# ---- load + process every trial independently (mirror geometry, no build_metrics) ----
trials, meta = pc.load_trials()
print("loaded", len(trials), "trials")
Q_body = tc.pooled_dejump_Q(trials, "body")
Q_head = tc.pooled_dejump_Q(trials, "head")
print("Q_body=%.6f Q_head=%.6f" % (Q_body, Q_head))

recs = []
body_rm_list, head_rm_list = [], []
for tr in trials:
    fn = tr["file_name"]; g = tc.group_of(fn)
    S = pc.endpoint_of(tr)
    body = np.asarray(tr["body"], float); body_t = np.asarray(tr["body_time"], float)
    head = np.asarray(tr["head"], float); head_t = np.asarray(tr["head_time"], float)
    eth_t = np.asarray(tr["ethanol_time"], float); ethd = np.asarray(tr["ethdeconv"], float)

    b_idx, body_c, body_tc = tc.clean_track(body, body_t, Q_body)
    h_idx, head_c, head_tc = tc.clean_track(head, head_t, Q_head)
    nb = int(pc._in_box(body).sum()); nh = int(pc._in_box(head).sum())
    body_rm_list.append(1 - b_idx.size/nb if nb else np.nan)
    head_rm_list.append(1 - h_idx.size/nh if nh else np.nan)

    tort, plen, straight = tc.tortuosity(body_c)
    body_h = tc.interp_body_to_head(head_tc, body_tc, body_c)
    ethd_h = tc.align_signal(head_tc, eth_t, ethd)
    u, vu = tc.body_axis_u(head_c, body_h)
    s, vs = tc.to_source_s(body_h, S)
    gv = vu & vs
    theta = np.full(head_tc.shape[0], np.nan)
    theta[gv] = tc.angle_theta(u[gv], s[gv])
    d = tc.distance_to_source(body_h, S)
    hsd = tc.distance_to_source(head_c, S)
    recs.append(dict(fn=fn, g=g, pooled=g in POOLED, S=S, tort=tort, plen=plen,
                     theta=theta, d=d, ethd_h=ethd_h, head_t=head_tc, hsd=hsd,
                     head_c=head_c, body_h=body_h))

print("mean body_rm=%.5f (%.3f%%)  mean head_rm=%.5f (%.3f%%)" % (
    np.nanmean(body_rm_list), 100*np.nanmean(body_rm_list),
    np.nanmean(head_rm_list), 100*np.nanmean(head_rm_list)))
print("max body_rm=%.4f max head_rm=%.4f  smell-test(<5%% mean): body=%s head=%s" % (
    np.nanmax(body_rm_list), np.nanmax(head_rm_list),
    np.nanmean(body_rm_list)<0.05, np.nanmean(head_rm_list)<0.05))

# ---- RE-DERIVE k-scan calibration independently ----
quiet_vals = []; quiet_segs = []
for r in recs:
    e = r["ethd_h"]; dd = r["hsd"]
    ok = np.isfinite(e) & np.isfinite(dd)
    if ok.sum() == 0: continue
    d80 = np.percentile(dd[ok], 80); med = np.median(e[ok])
    qm = ok & (dd > d80) & (e < med)
    if qm.any():
        quiet_vals.append(e[qm]); quiet_segs.append((e[qm], r["head_t"][qm]))
allq = np.concatenate(quiet_vals)
madq = float(1.4826*np.median(np.abs(allq - np.median(allq))))
total_dur = sum(float(t[-1]-t[0]) for _, t in quiet_segs if t.size>=2)
print("\n=== RE-DERIVED k-scan  mad_quiet=%.8g total_quiet_dur=%.2fs ===" % (madq, total_dur))
chosen_k = None
for k in (5,6,8,10):
    thr = k*madq; n_on = 0
    for s_, t_ in quiet_segs:
        if s_.size >= 2:
            n_on += len(tc.detect_onsets(s_, t_, thr))
    fpr = n_on/total_dur if total_dur>0 else np.inf
    flag = ""
    if chosen_k is None and fpr <= 0.05:
        chosen_k = k; flag = " <-- CHOSEN (smallest with FPR<=0.05)"
    print("  k=%2d thr=%.8g n_onsets=%d fpr=%.6g/s%s" % (k, thr, n_on, fpr, flag))
thr_chosen = chosen_k*madq
print("re-derived chosen k=%d threshold=%.10g" % (chosen_k, thr_chosen))
print("stored        k=%d threshold=%.10g fpr=%.6g" % (
    stats["calibration"]["k"], stats["calibration"]["threshold"], stats["calibration"]["fpr_per_s"]))

# ---- encounters using stored threshold (to reproduce n_encounters / H1) ----
THR = stats["calibration"]["threshold"]
for r in recs:
    on = tc.detect_onsets(r["ethd_h"], r["head_t"], THR, 0.20)
    r["onsets"] = on; r["nenc"] = int(on.size)
    r["frac"] = tc.frac_above(r["ethd_h"], THR)

pooled = [r for r in recs if r["pooled"]]
print("\nn_pooled=%d n_anotherLoc=%d" % (len(pooled), sum(1 for r in recs if r["g"]=="anotherLoc")))

nenc = np.array([r["nenc"] for r in pooled], float)
tort = np.array([r["tort"] for r in pooled], float)
frac = np.array([r["frac"] for r in pooled], float)
plen = np.array([r["plen"] for r in pooled], float)

def sp(x, y):
    m = np.isfinite(x)&np.isfinite(y)
    return st.spearmanr(x[m], y[m])[0]

print("\n=== H1 ===")
print("rho(nenc,tort)        re=%.4f stored=%.4f" % (sp(nenc,tort), stats["H1"]["primary_n_encounters_vs_tortuosity"]["spearman_rho"]))
rate = np.where(plen>0, nenc/plen, np.nan)
print("rho(enc_rate,tort)    re=%.4f stored=%.4f" % (sp(rate,tort), stats["H1"]["rho_encounter_rate_vs_tort"]["spearman_rho"]))
print("rho(frac_above,tort)  re=%.4f stored=%.4f" % (sp(frac,tort), stats["H1"]["secondary_frac_above_vs_tortuosity"]["spearman_rho"]))
print("rho(nenc,plen)        re=%.4f stored=%.4f" % (sp(nenc,plen), stats["H1"]["rho_nenc_pathlen"]["spearman_rho"]))
print("rho(tort,plen)        re=%.4f stored=%.4f" % (sp(tort,plen), stats["H1"]["rho_tort_pathlen"]["spearman_rho"]))
print("median nenc pooled    re=%.1f stored=%.1f" % (np.median(nenc), stats["calibration"]["n_encounters_distribution_pooled"]["median"]))

print("\n=== H2 ===")
slopes = []
for r in pooled:
    m = np.isfinite(r["theta"])&np.isfinite(r["d"])
    slopes.append(np.polyfit(r["d"][m], r["theta"][m], 1)[0] if m.sum()>=2 else np.nan)
slopes = np.array(slopes)
sf = slopes[np.isfinite(slopes)]
w, wp = st.wilcoxon(sf, alternative="greater")
print("n_finite_slope re=%d stored=%d" % (sf.size, stats["H2"]["n_trials_with_finite_slope"]))
print("first 3 slopes re=%s" % [round(float(x),6) for x in slopes[:3]])
stored_sl = stats["H2"]["per_trial_slopes"][:3]
print("first 3 slopes stored=%s" % [round(x,6) for x in stored_sl])
print("median slope   re=%.6f stored=%.6f" % (np.median(sf), stats["H2"]["median_slope_deg_per_px"]))
print("Wilcoxon>0 p   re=%.6f stored=%.6f" % (wp, stats["H2"]["wilcoxon_slopes_gt_0"]["p"]))

print("\n=== H3 ===")
rel = np.arange(PERI_LO, PERI_HI+1e-9, PERI_STEP)
pre_l, post_l = [], []
for r in pooled:
    on = r["onsets"]
    vt = np.isfinite(r["theta"])
    tv = r["head_t"][vt]; thv = r["theta"][vt]
    if on.size and tv.size>=2:
        per = np.full((on.size, rel.size), np.nan)
        tmin, tmax = tv[0], tv[-1]
        for j, oi in enumerate(on):
            grid = r["head_t"][oi] + rel
            samp = np.interp(grid, tv, thv)
            samp[(grid<tmin)|(grid>tmax)] = np.nan
            per[j] = samp
        with np.errstate(invalid="ignore"):
            pre = np.nanmean(per[:, rel<0]); post = np.nanmean(per[:, rel>0])
        pre_l.append(pre); post_l.append(post)
    else:
        pre_l.append(np.nan); post_l.append(np.nan)
pre = np.array(pre_l); post = np.array(post_l)
pm = np.isfinite(pre)&np.isfinite(post)
h3w, h3p = st.wilcoxon(post[pm], pre[pm], alternative="less")
print("n_pairs        re=%d stored=%d" % (pm.sum(), stats["H3"]["n_paired_trials"]))
print("median pre     re=%.4f stored=%.4f" % (np.median(pre[pm]), stats["H3"]["median_pre_theta"]))
print("median post    re=%.4f stored=%.4f" % (np.median(post[pm]), stats["H3"]["median_post_theta"]))
print("paired Wilcoxon post<pre p re=%.6f stored=%.6f" % (h3p, stats["H3"]["paired_wilcoxon_post_lt_pre"]["p"]))
print("total contacts re=%d stored=%d" % (sum(r["nenc"] for r in pooled if r["nenc"]>=1), stats["H3"]["total_contacts_pooled"]))

# ---- ANGLE SANITY: trial index 2, near-source median theta ----
print("\n=== ANGLE SANITY (trial idx 2) ===")
r2 = recs[2]
th2 = r2["theta"]; d2 = r2["d"]
near = np.isfinite(th2) & np.isfinite(d2) & (d2 < np.nanpercentile(d2[np.isfinite(d2)], 20))
print("trial2 fn=%s near-source(<20pct d) median theta=%.3f (probe expected ~23.36)" % (r2["fn"], np.nanmedian(th2[near])))
allth = np.concatenate([r["theta"][np.isfinite(r["theta"])] for r in recs])
print("global theta range [%.4f, %.4f]  (expect [0,180])" % (allth.min(), allth.max()))

# ---- H5 structural check on a FRESH h5py read ----
print("\n=== H5 FRESH READ ===")
import h5py
with h5py.File(os.path.join(DATA, "trajectory_metrics.h5"), "r") as f:
    tg = f["trials"]
    print("n trial groups=%d" % len(tg.keys()))
    print("build_complete=%s seed=%s k=%s" % (f.attrs.get("build_complete"), f.attrs.get("seed"), f.attrs.get("k")))
    g0 = tg["000"]
    print("group000 datasets=%s" % sorted(g0.keys()))
    print("root attrs has README/created_utc/generator/version:",
          all(a in f.attrs for a in ("README","created_utc","generator","version")))
    # gzip check on a >=256 numeric dataset
    comp = {k: g0[k].compression for k in g0.keys()}
    big = [k for k in g0.keys() if g0[k].size>=256 and np.issubdtype(g0[k].dtype, np.number)]
    print("compression on big numeric datasets:", {k: comp[k] for k in big})
    # verify a stored theta matches our recompute for group000
    st_theta = g0["theta"][()]
    my_theta = recs[0]["theta"]
    n = min(st_theta.size, my_theta.size)
    both = np.isfinite(st_theta[:n]) & np.isfinite(my_theta[:n])
    print("group000 theta max abs diff vs recompute: %.3e (n=%d)" % (
        np.max(np.abs(st_theta[:n][both]-my_theta[:n][both])) if both.any() else np.nan, both.sum()))

print("\nVERIFY DONE")
