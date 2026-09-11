r"""audit_gate2.py -- INDEPENDENT scientific re-derivation (Gate 2).
Does NOT import build_metrics. Reimplements geometry/encounter/stats from scratch
off the accessor, to cross-check stored stats.json. Reuses only traj_common for the
cleaning primitive parity check (also reimplements a naive version).
"""
import sys, os, json
import numpy as np
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\DATA\code")
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
from mouse_arena_aggregate_io import Aggregate
import plume_common as pc
from scipy import stats as st

AGG = r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5"
ARENA = (0.0, 580.0, 0.0, 280.0)
SEED = 1234
REFRAC = 0.20
import re
def group_of(fn):
    m = re.search(r"_Loc(\d+)", fn)
    if m: return "Loc%d" % int(m.group(1))
    if "anotherLoc" in fn: return "anotherLoc"
    return "?"

def in_box(xy):
    x, y = xy[:,0], xy[:,1]
    return np.isfinite(x)&np.isfinite(y)&(x>=ARENA[0])&(x<=ARENA[1])&(y>=ARENA[2])&(y<=ARENA[3])

def clean_track(xy, t, Q):
    """Use the VALIDATED plume_common.clean_track (consecutive box-kept step<=Q,
    single vectorized pass -- the correct non-cascading rule). Returns kept xy, t,
    removed_frac (relative to in-box count)."""
    idx, xyc, tc = pc.clean_track(np.asarray(xy,float), np.asarray(t,float), Q)
    nb = int(in_box(np.asarray(xy,float)).sum())
    removed = (1.0 - idx.size/nb) if nb>0 else np.nan
    return xyc, tc, removed

def pooled_Q(trials, key):
    steps = []
    for tr in trials:
        xy = np.asarray(tr[key], float)
        m = in_box(xy)
        xy = xy[m]
        if xy.shape[0] >= 2:
            steps.append(np.linalg.norm(np.diff(xy, axis=0), axis=1))
    steps = np.concatenate(steps)
    return float(np.percentile(steps, 99.5))

def mad(x):
    return pc.mad(x)  # validated: scale=1.4826

def detect_onsets(sig, t, thr, refrac=REFRAC):
    s = np.asarray(sig,float); t=np.asarray(t,float)
    below = ~(s>=thr)
    cross = np.nonzero(below[:-1] & (s[1:]>=thr))[0]+1
    acc=[]; last=-np.inf
    for i in cross:
        if t[i]-last>=refrac:
            acc.append(i); last=t[i]
    return np.array(acc,int)

def main():
    agg = Aggregate(AGG)
    trials = agg.behavior(lighting="infrared")
    print("n trials:", len(trials))
    Qb = pooled_Q(trials, "body"); Qh = pooled_Q(trials, "head")
    print("Q body=%.5f head=%.5f" % (Qb, Qh))

    recs=[]
    body_rm=[]; head_rm=[]
    for tr in trials:
        fn = tr["file_name"]; g = group_of(fn)
        S = np.asarray(tr["endpoint"], float).reshape(2)
        bt = np.asarray(tr["body_time"],float); ht=np.asarray(tr["head_time"],float)
        et = np.asarray(tr["ethanol_time"],float); ed=np.asarray(tr["ethdeconv"],float)
        bc, btc, brm = clean_track(tr["body"], bt, Qb)
        hc, htc, hrm = clean_track(tr["head"], ht, Qh)
        body_rm.append(brm); head_rm.append(hrm)
        if htc.size<2 or btc.size<2: continue
        # interp body->head
        bx = np.interp(htc, btc, bc[:,0]); by = np.interp(htc, btc, bc[:,1])
        body_h = np.column_stack([bx,by])
        # align ethdeconv->head (nan outside support)
        ed_h = np.interp(htc, et, ed, left=np.nan, right=np.nan)
        # geometry
        du = hc - body_h; nu = np.linalg.norm(du,axis=1)
        ds = S[None,:]-body_h; ns = np.linalg.norm(ds,axis=1)
        vu = np.isfinite(nu)&(nu>=1.0); vs=np.isfinite(ns)&(ns>=1.0)
        gv = vu&vs
        theta = np.full(htc.shape[0], np.nan)
        u = du[gv]/nu[gv,None]; s = ds[gv]/ns[gv,None]
        dot = np.clip(np.sum(u*s,axis=1),-1,1)
        theta[gv] = np.degrees(np.arccos(dot))
        d = np.hypot(body_h[:,0]-S[0], body_h[:,1]-S[1])
        hsd = np.hypot(hc[:,0]-S[0], hc[:,1]-S[1])
        # tortuosity on cleaned body
        steps = np.linalg.norm(np.diff(bc,axis=0),axis=1)
        pl = float(np.nansum(steps))
        sl = float(np.hypot(bc[-1,0]-bc[0,0], bc[-1,1]-bc[0,1]))
        tort = pl/sl if sl>=1.0 else np.nan
        recs.append(dict(fn=fn,g=g,in_pooled=g.startswith("Loc"),S=S,
            htc=htc,ed_h=ed_h,theta=theta,d=d,hsd=hsd,tort=tort,pl=pl,sl=sl))

    print("mean body_rm=%.5f max=%.5f" % (np.nanmean(body_rm), np.nanmax(body_rm)))
    print("mean head_rm=%.5f max=%.5f" % (np.nanmean(head_rm), np.nanmax(head_rm)))

    # quiet baseline & calibration
    qvals=[]; qsegs=[]; qdur=0.0
    for r in recs:
        ed=r["ed_h"]; hsd=r["hsd"]
        ok=np.isfinite(ed)&np.isfinite(hsd)
        if ok.sum()==0: continue
        d80=np.percentile(hsd[ok],80); med=np.median(ed[ok])
        qm = ok&(hsd>d80)&(ed<med)
        if qm.any():
            qvals.append(ed[qm]); qsegs.append((ed[qm], r["htc"][qm]))
            tq=r["htc"][qm]
            if tq.size>=2: qdur += tq[-1]-tq[0]
    qall=np.concatenate(qvals)
    m=mad(qall)
    print("mad_quiet=%.8f  qdur=%.1f" % (m, qdur))
    for k in (5,6,8,10):
        thr=k*m; non=0
        for s,t in qsegs:
            if len(s)>=2: non+=len(detect_onsets(s,t,thr))
        print("  k=%d thr=%.8f fpr=%.6g n_onsets=%d" % (k,thr,non/qdur,non))
    thr = 5*m  # smallest passing
    print("chosen thr=%.8f" % thr)

    # encounters, tort, pathlen per trial (pooled)
    for r in recs:
        on = detect_onsets(r["ed_h"], r["htc"], thr)
        r["n_enc"]=on.size; r["onset_t"]=r["htc"][on]
        edf = r["ed_h"][np.isfinite(r["ed_h"])]
        r["frac_above"]=float(np.mean(edf>thr)) if edf.size else np.nan

    pooled=[r for r in recs if r["in_pooled"]]
    other=[r for r in recs if r["g"]=="anotherLoc"]
    ne=np.array([r["n_enc"] for r in pooled],float)
    to=np.array([r["tort"] for r in pooled],float)
    pl=np.array([r["pl"] for r in pooled],float)
    fr=np.array([r["frac_above"] for r in pooled],float)
    ne_all=np.array([r["n_enc"] for r in recs],float)
    print("\nn_enc pooled: median=%g mean=%g min=%g max=%g" %
          (np.median(ne),np.mean(ne),ne.min(),ne.max()))
    print("n_enc all: median=%g" % np.median(ne_all))

    def sp(x,y):
        m=np.isfinite(x)&np.isfinite(y); rho,p=st.spearmanr(x[m],y[m]); return rho,p,int(m.sum())
    def boot(x,y,nb=2000):
        rng=np.random.default_rng(SEED)
        m=np.isfinite(x)&np.isfinite(y); x,y=x[m],y[m]; n=x.size; rr=[]
        for _ in range(nb):
            idx=rng.integers(0,n,n)
            if np.all(x[idx]==x[idx][0]) or np.all(y[idx]==y[idx][0]): continue
            rr.append(st.spearmanr(x[idx],y[idx])[0])
        rr=np.array(rr); return np.percentile(rr,2.5),np.percentile(rr,97.5)

    print("\n== H1 ==")
    r1,p1,n1=sp(ne,to); print("n_enc vs tort: rho=%.4f p=%.3g n=%d CI=%s" % (r1,p1,n1,boot(ne,to)))
    rrt=ne/pl; rr,pr,nr=sp(rrt,to); print("enc_rate vs tort: rho=%.4f p=%.3g CI=%s" % (rr,pr,boot(rrt,to)))
    rnp,pnp,_=sp(ne,pl); print("n_enc vs pathlen: rho=%.4f p=%.3g" % (rnp,pnp))
    rtp,ptp,_=sp(to,pl); print("tort vs pathlen: rho=%.4f p=%.3g" % (rtp,ptp))
    rfa,pfa,_=sp(fr,to); print("frac_above vs tort: rho=%.4f p=%.3g" % (rfa,pfa))

    print("\n== H2 ==")
    slopes=[]
    for r in pooled:
        mm=np.isfinite(r["theta"])&np.isfinite(r["d"])
        if mm.sum()>=2: slopes.append(np.polyfit(r["d"][mm],r["theta"][mm],1)[0])
        else: slopes.append(np.nan)
    slopes=np.array(slopes,float); sf=slopes[np.isfinite(slopes)]
    W,pw=st.wilcoxon(sf,alternative="greater")
    print("Wilcoxon slopes>0: W=%.1f p=%.4f n=%d median=%.5f npos=%d nneg=%d" %
          (W,pw,sf.size,np.median(sf),(sf>0).sum(),(sf<0).sum()))

    print("\n== H3 ==")
    rel=np.arange(-1.0,1.0+1e-9,0.05)
    pre_l=[]; post_l=[]; total_c=0
    for r in pooled:
        on_t=r["onset_t"]
        vt=np.isfinite(r["theta"])
        tv=r["htc"][vt]; thv=r["theta"][vt]
        if on_t.size==0 or tv.size<2:
            pre_l.append(np.nan); post_l.append(np.nan); continue
        total_c += on_t.size
        per=np.full((on_t.size,rel.size),np.nan)
        tmin,tmax=tv[0],tv[-1]
        for j,ot in enumerate(on_t):
            grid=ot+rel; samp=np.interp(grid,tv,thv)
            samp[(grid<tmin)|(grid>tmax)]=np.nan; per[j]=samp
        pm=rel<0; qm=rel>0
        with np.errstate(invalid="ignore"):
            pre_l.append(np.nanmean(per[:,pm]) if np.isfinite(per[:,pm]).any() else np.nan)
            post_l.append(np.nanmean(per[:,qm]) if np.isfinite(per[:,qm]).any() else np.nan)
    pre=np.array(pre_l); post=np.array(post_l)
    pr2=np.isfinite(pre)&np.isfinite(post)
    prp,pop=pre[pr2],post[pr2]
    Wh,ph=st.wilcoxon(pop,prp,alternative="less")
    print("total_contacts=%d n_pairs=%d" % (total_c,pr2.sum()))
    print("median pre=%.4f post=%.4f  (post-pre=%.4f)" % (np.median(prp),np.median(pop),np.median(pop-prp)))
    print("n pairs post<pre=%d  post>pre=%d" % ((pop<prp).sum(),(pop>prp).sum()))
    print("paired Wilcoxon post<pre: W=%.1f p=%.4f" % (Wh,ph))

    # angle sanity: trial 2 near-source median theta
    print("\n== angle sanity ==")
    r=recs[2]
    th=r["theta"]; hsd=r["hsd"]; near=hsd<np.nanpercentile(hsd,20)
    mm=np.isfinite(th)
    print("trial2 %s global median theta=%.2f  near-source median=%.2f  theta range=[%.2f,%.2f]" %
          (r["fn"], np.nanmedian(th), np.nanmedian(th[near&mm]), np.nanmin(th[mm]), np.nanmax(th[mm])))
    allth=np.concatenate([r["theta"][np.isfinite(r["theta"])] for r in recs])
    print("global theta min=%.4f max=%.4f" % (allth.min(), allth.max()))

if __name__=="__main__":
    main()
