import sys, os, json
import numpy as np
import h5py
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plume_common as pc
import build_enhancement as be

ROOT = os.path.dirname(HERE)
st = json.load(open(os.path.join(ROOT, "data", "enhancement_stats.json")))
thr_before = st["thresholds"]["before"]
thr_after = st["thresholds"]["after"]
print("stored thr_before", thr_before, "thr_after", thr_after)
print("stored fpr_before", st["pooled_baseline_fpr_before"], "fpr_after", st["pooled_baseline_fpr_after"])

# ---- Independent re-derivation of baseline FPR from stored H5 traces ----
# H5 stores drift_corrected and enhanced per trial, plus head/head_time/endpoint/time.
# Rebuild the quiet far-from-source baseline mask exactly as baseline_segments does,
# then count detections at the STORED thresholds -> confirm after <= before.
FS = be.FS
FAR = be.FAR_DIST_PCTILE
AMPF = be.BASELINE_AMP_FRAC
REFRAC = be.REFRACTORY_S

def detrate(seglist, segtimes, thr):
    tot_n = 0; tot_dur = 0.0
    for sig, tt in zip(seglist, segtimes):
        if sig.size < 3: continue
        pk = pc.detect_encounters(sig, tt, thresh=thr, refractory_s=REFRAC, min_prominence=1e-12)
        tot_n += int(pk.size)
        tot_dur += float(tt[-1]-tt[0]) if tt.size>=2 else 0.0
    return (tot_n/tot_dur if tot_dur>0 else 0.0), tot_n, tot_dur

def contiguous(idx):
    if idx.size==0: return []
    runs=[]; start=prev=idx[0]
    for i in idx[1:]:
        if i==prev+1: prev=i
        else: runs.append((start,prev)); start=prev=i
    runs.append((start,prev)); return runs

before_segs=[]; before_t=[]; after_segs=[]; after_t=[]
h5 = os.path.join(ROOT,"data","enhanced_ethanol.h5")
with h5py.File(h5,"r") as f:
    print("build_complete", f.attrs["build_complete"])
    print("root fpr_before attr", f.attrs["baseline_fpr_before"], "fpr_after attr", f.attrs["baseline_fpr_after"])
    tg=f["trials"]
    for gid in tg:
        g=tg[gid]
        dc=g["drift_corrected"][:].astype(float)
        enh=g["enhanced"][:].astype(float)
        et=g["time"][:].astype(float)
        head=g["head"][:].astype(float)
        ht=g["head_time"][:].astype(float)
        ep=g["endpoint"][:].astype(float)
        hx=pc.align_signal(et,ht,head[:,0]); hy=pc.align_signal(et,ht,head[:,1])
        dist=np.hypot(hx-ep[0],hy-ep[1]); cov=np.isfinite(dist)
        if not cov.any(): continue
        far_cut=np.percentile(dist[cov],FAR)
        far=cov&(dist>far_cut)
        if far.sum()<5: continue
        amp=np.abs(dc); far_idx=np.nonzero(far)[0]
        amp_thr=np.percentile(amp[far_idx],AMPF*100.0)
        q=far_idx[amp[far_idx]<=amp_thr]
        if q.size<5: q=far_idx
        for (a,b) in contiguous(np.sort(q)):
            if b-a+1<3: continue
            before_segs.append(dc[a:b+1]); before_t.append(et[a:b+1])
            after_segs.append(enh[a:b+1]); after_t.append(et[a:b+1])

fb,nb,db = detrate(before_segs,before_t,thr_before)
fa,na,da = detrate(after_segs,after_t,thr_after)
print("\n=== INDEPENDENT RE-DERIVATION FROM STORED H5 ===")
print(f"  n_baseline_segments={len(before_segs)} (stored {st['n_baseline_segments']})")
print(f"  fpr_before RE-DERIVED = {fb:.6f}/s  (n={nb}, dur={db:.1f}s)  stored={st['pooled_baseline_fpr_before']:.6f}")
print(f"  fpr_after  RE-DERIVED = {fa:.6f}/s  (n={na}, dur={da:.1f}s)  stored={st['pooled_baseline_fpr_after']:.6f}")
print(f"  H5 GUARD (after<=before): {fa <= fb + 1e-9}  [HARD GATE]")

# ---- Re-derive overall/distal count direction from stored per-trial ----
pt=st["per_trial"]
tb=sum(p["n_before"] for p in pt); ta=sum(p["n_after"] for p in pt)
tbd=sum(p["n_before_distal"] for p in pt); tad=sum(p["n_after_distal"] for p in pt)
tbp=sum(p["n_before_prox"] for p in pt); tap=sum(p["n_after_prox"] for p in pt)
print("\n=== COUNT DIRECTION (re-summed per_trial) ===")
print(f"  overall before={tb} after={ta}  (stored {st['counts']['total_before']}/{st['counts']['total_after']}) DECREASE={ta<tb}")
print(f"  distal  before={tbd} after={tad}  INCREASE={tad>tbd}")
print(f"  prox    before={tbp} after={tap}  DECREASE={tap<tbp}")
gain=sum(1 for p in pt if p['n_after']>p['n_before']); lose=sum(1 for p in pt if p['n_after']<p['n_before']); tie=sum(1 for p in pt if p['n_after']==p['n_before'])
print(f"  gain/lose/tie = {gain}/{lose}/{tie} (stored {st['counts']['trials_gaining']}/{st['counts']['trials_losing']}/{st['counts']['trials_tying']})")

# ---- sanity on magnitude of 'encounters' ----
nbs=np.array([p['n_before'] for p in pt])
print("\n=== ENCOUNTER COUNT MAGNITUDE (before) ===")
print(f"  min={nbs.min()} median={np.median(nbs)} max={nbs.max()} mean={nbs.mean():.0f}")
print("  (trials are ~tens of seconds; thousands of 'encounters'/trial => detector counting noise wiggles)")

# ---- top10 distal SNR gain: how many are negative? ----
print("\n=== TOP10 distal SNR gain (Figure A candidates) ===")
print("  gains:", st["top10_figureA_distal_snr_gain"])
allg=[p['distal_snr_gain'] for p in pt]
print(f"  across all 114 trials: #positive={sum(1 for g in allg if g>0)} #negative={sum(1 for g in allg if g<0)} max={max(allg):.3f} min={min(allg):.3f}")
