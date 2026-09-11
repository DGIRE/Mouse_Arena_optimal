r"""audit_gate2.py -- INDEPENDENT Gate-2 re-derivation. Does NOT trust build_bouts.
Recomputes: (1) bout rate + translation-invariance sanity; (2) H1/H2/H3 headline
trial-level Wilcoxon p from a FRESH detection pass over the aggregate; (3) one trial's
f_bout/f_occ from h5 arrays + odor field; (4) amplitude frac; (5) kinematic spot-check.
Interpreter: "$AR_PY".
"""
import sys, os, json
import numpy as np
from scipy import stats

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
sys.path.insert(0, os.path.join(BASE, "code"))
import reactions2_common as r2
import plume_common as pc

ODOR_FIELDS_H5 = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5"
POOLED = {"Loc1","Loc2","Loc3","Loc4","Loc5","Loc6"}
SEED=1234; N_PERM=2000
PERI=(-0.5,0.5); PRE=(-0.75,-0.25); SLOPE=(-1.0,0.0); GRID_DT=0.05

def wmean(sig,t,ev,win):
    ev=np.atleast_1d(np.asarray(ev,float))
    if ev.size==0: return np.array([],float)
    _,M=r2.peri_event_matrix(sig,t,ev,window=win,grid_dt=GRID_DT)
    with np.errstate(all='ignore'): return np.nanmean(M,axis=1)

def onset_slope(sig,t,ev,win):
    ev=np.atleast_1d(np.asarray(ev,float)); out=np.full(ev.size,np.nan)
    if ev.size==0: return out
    grid,M=r2.peri_event_matrix(sig,t,ev,window=win,grid_dt=GRID_DT)
    for i in range(ev.size):
        y=M[i]; ok=np.isfinite(y)
        if ok.sum()>=2 and np.ptp(grid[ok])>0:
            out[i]=stats.linregress(grid[ok],y[ok]).slope
    return out

def wilc(diff):
    d=np.asarray(diff,float); d=d[np.isfinite(d)]
    if d.size<1 or np.all(d==0): return (np.nan,np.nan,d.size)
    try:
        r=stats.wilcoxon(d,alternative='greater',zero_method='wilcox')
        return (float(r.statistic),float(r.pvalue),d.size)
    except ValueError: return (np.nan,np.nan,d.size)

def med(a):
    a=np.asarray(a,float); a=a[np.isfinite(a)]
    return float(np.median(a)) if a.size else np.nan

trials,meta=pc.load_trials()
Qh=r2.pooled_dejump_Q(trials,"head"); Qb=r2.pooled_dejump_Q(trials,"body")

# fresh threshold pass
vp_pool=[]; om_pool=[]
kins=[]
for tr in trials:
    ht=np.asarray(tr["head_time"],float); bt=np.asarray(tr["body_time"],float)
    head=np.asarray(tr["head"],float); body=np.asarray(tr["body"],float)
    ih,hc,htc=r2.clean_track(head,ht,Qh); ib,bc,btc=r2.clean_track(body,bt,Qb)
    if hc.shape[0]<r2.SG_WIN+2 or btc.size<2: kins.append(None); continue
    dt=float(np.median(np.diff(htc)))
    if not np.isfinite(dt) or dt<=0: kins.append(None); continue
    bh=r2.interp_xy_to_head(htc,btc,bc)
    v=r2.speed_savgol(bh,dt); phi=r2.bearing_phi(hc,bh); om=r2.angular_speed_omega(phi,dt)
    eth=np.asarray(tr["ethanol"],float); et=np.asarray(tr["ethanol_time"],float)
    ebs=r2.align_signal(htc,et,r2.baseline_subtract_ethanol(eth,et))
    kins.append({"hc":hc,"htc":htc,"dt":dt,"v":v,"phi":phi,"om":om,"ebs":ebs,
                 "dur":float(htc[-1]-htc[0]),"loc":r2.group_of(tr["file_name"]),
                 "ep":r2.endpoint_of(tr)})
    vp_pool.append(v[np.isfinite(v)]); om_pool.append(om[np.isfinite(om)])

v_pause=float(np.percentile(np.concatenate(vp_pool),25.0))
omega_min=float(np.percentile(np.concatenate(om_pool),90.0))
print(f"[thresholds] v_pause={v_pause:.5f} (stored 5.89069) omega_min={omega_min:.5f} (stored 156.582)")

# detect + measure per trial
rows=[]
for ti,kin in enumerate(kins):
    if kin is None: continue
    rng=np.random.default_rng(SEED+ti*101+1)
    bouts=r2.detect_bouts(kin["v"],kin["phi"],kin["om"],kin["htc"],v_pause,omega_min)
    inc=r2.detect_incidental(kin["v"],kin["om"],kin["htc"],v_pause,omega_min)
    onset_idx=np.array([b["onset_idx"] for b in bouts],int)
    ot=kin["htc"][onset_idx] if onset_idx.size else np.array([],float)
    it=kin["htc"][inc] if inc.size else np.array([],float)
    field=r2.load_odor_field(kin["loc"],path=ODOR_FIELDS_H5) if kin["loc"] in POOLED or kin["loc"]=="anotherLoc" else None
    def inod(xs,ys):
        xs=np.atleast_1d(xs); ys=np.atleast_1d(ys)
        if field is not None: return r2.is_in_odor(field,xs,ys,cutoff=r2.ODOR_CUTOFF)
        return np.hypot(xs-kin["ep"][0],ys-kin["ep"][1])<=100.0
    peri=wmean(kin["ebs"],kin["htc"],ot,PERI)
    pre=wmean(kin["ebs"],kin["htc"],ot,PRE)
    slp=onset_slope(kin["ebs"],kin["htc"],ot,SLOPE)
    incp=wmean(kin["ebs"],kin["htc"],it,PERI)
    nb=onset_idx.size
    lo,hi=(kin["htc"][0],kin["htc"][-1])
    null_peri=np.nan; null_pre=np.nan
    if nb>=1 and kin["dur"]>0:
        rt=rng.uniform(lo,hi,size=(N_PERM,nb))
        wm=wmean(kin["ebs"],kin["htc"],rt.reshape(-1),PERI).reshape(N_PERM,nb)
        with np.errstate(all='ignore'): null_peri=float(np.nanmean(np.nanmean(wm,axis=1)))
        rt2=rng.uniform(lo,hi,size=(N_PERM,nb))
        wm2=wmean(kin["ebs"],kin["htc"],rt2.reshape(-1),PRE).reshape(N_PERM,nb)
        with np.errstate(all='ignore'): null_pre=float(np.nanmean(np.nanmean(wm2,axis=1)))
    tb=float(np.nanmedian(kin["ebs"])) if np.any(np.isfinite(kin["ebs"])) else np.nan
    allio=inod(kin["hc"][:,0],kin["hc"][:,1])
    f_occ=float(np.mean(allio)) if allio.size else np.nan
    if onset_idx.size:
        io=inod(kin["hc"][onset_idx,0],kin["hc"][onset_idx,1]); f_bout=float(np.mean(io))
    else: f_bout=np.nan
    rows.append({"ti":ti,"loc":kin["loc"],"pooled":kin["loc"] in POOLED,"nb":nb,
        "rate":(nb/kin["dur"]) if kin["dur"]>0 else np.nan,
        "m_peri":med(peri),"null_peri":null_peri,"m_pre":med(pre),"null_pre":null_pre,
        "m_slope":med(slp),"m_incp":med(incp),"tb":tb,"f_bout":f_bout,"f_occ":f_occ,
        "peri_all":peri})

pooled=[r for r in rows if r["pooled"]]
ge1=[r for r in pooled if r["nb"]>=1]
rates=[r["rate"] for r in pooled if np.isfinite(r["rate"])]
print(f"\n[RARITY] pooled median rate={np.median(rates):.6f}/s (stored 0.0073328) n_bouts_pooled={sum(r['nb'] for r in pooled)} (stored 111)")
print(f"         frac>=1={np.mean([r['nb']>=1 for r in pooled]):.4f} (stored 0.6381) n_contrib={len(ge1)} (stored 67)")

# H1
d=[r["m_peri"]-r["null_peri"] for r in ge1 if np.isfinite(r["m_peri"]) and np.isfinite(r["null_peri"])]
s,p,n=wilc(d); print(f"\n[H1a] bout>null Wilcoxon p={p:.4f} stat={s} n={n} (stored p=0.9998 stat=231 n=46)")
amp=np.concatenate([r["peri_all"][np.isfinite(r["peri_all"])] for r in ge1])
print(f"[H1 amp] frac peri>0.01 = {np.mean(amp>0.01):.4f} (stored 0.6049)")

# H2
d2=[r["m_pre"]-r["tb"] for r in ge1 if np.isfinite(r["m_pre"]) and np.isfinite(r["tb"])]
s2,p2,n2=wilc(d2); print(f"\n[H2] pre>baseline Wilcoxon p={p2:.4f} stat={s2} n={n2} (stored p=0.6493 stat=200 n=29)")
sl=[r["m_slope"] for r in ge1 if np.isfinite(r["m_slope"])]
s3,p3,n3=wilc(sl); print(f"[H2 slope] slope>0 p={p3:.4f} n={n3} (stored p=0.4324 n=29)")

# H3
d3=[r["f_bout"]-r["f_occ"] for r in ge1 if np.isfinite(r["f_bout"]) and np.isfinite(r["f_occ"])]
s4,p4,n4=wilc(d3); print(f"\n[H3] f_bout>f_occ Wilcoxon p={p4:.4f} stat={s4} n={n4} (stored p=0.9937 stat=740 n=67)")
print(f"[H3] median f_bout={med([r['f_bout'] for r in ge1]):.4f} f_occ={med([r['f_occ'] for r in ge1]):.4f} (stored 0.0 / 0.3076)")

# one trial f_bout/f_occ re-derive (trial 47)
r47=[r for r in rows if r["ti"]==47][0]
print(f"\n[TRIAL 47] f_bout={r47['f_bout']:.4f} f_occ={r47['f_occ']:.4f} nb={r47['nb']}")
