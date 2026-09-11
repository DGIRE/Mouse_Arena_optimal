r"""audit_encounters.py -- is the encounter detector physically interpretable or noise?
Threshold thr~0.00072 on ethdeconv (range [-0.02,0.14]). Check: where do onsets fall
relative to (a) the ethdeconv value AT onset vs the whole-trace distribution,
(b) head-source distance at onset vs the trial's overall distance distribution,
(c) is the quiet baseline actually near-silent (near-zero detections)."""
import sys, numpy as np
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\DATA\code")
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
from mouse_arena_aggregate_io import Aggregate
import plume_common as pc
import re

AGG=r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5"
def group_of(fn):
    m=re.search(r"_Loc(\d+)",fn)
    return ("Loc%d"%int(m.group(1))) if m else ("anotherLoc" if "anotherLoc" in fn else "?")
def in_box(xy):
    x,y=xy[:,0],xy[:,1]
    return np.isfinite(x)&np.isfinite(y)&(x>=0)&(x<=580)&(y>=0)&(y<=280)
def detect_onsets(sig,t,thr,refrac=0.20):
    s=np.asarray(sig,float); below=~(s>=thr)
    cross=np.nonzero(below[:-1]&(s[1:]>=thr))[0]+1
    acc=[]; last=-np.inf
    for i in cross:
        if t[i]-last>=refrac: acc.append(i); last=t[i]
    return np.array(acc,int)

agg=Aggregate(AGG); trials=agg.behavior(lighting="infrared")
Qb=np.percentile(np.concatenate([np.linalg.norm(np.diff(np.asarray(tr["body"],float)[in_box(np.asarray(tr["body"],float))],axis=0),axis=1) for tr in trials]),99.5)
Qh=np.percentile(np.concatenate([np.linalg.norm(np.diff(np.asarray(tr["head"],float)[in_box(np.asarray(tr["head"],float))],axis=0),axis=1) for tr in trials]),99.5)
THR=0.0007181608994175671

onset_ethd=[]; onset_dist_pctile=[]; frac_trace_above=[]; ethd_median_all=[]
example=None
for ti,tr in enumerate(trials):
    S=np.asarray(tr["endpoint"],float).reshape(2)
    _,hc,htc=pc.clean_track(tr["head"],np.asarray(tr["head_time"],float),Qh)
    if htc.size<2: continue
    ed=np.asarray(tr["ethdeconv"],float); et=np.asarray(tr["ethanol_time"],float)
    ed_h=np.interp(htc,et,ed,left=np.nan,right=np.nan)
    hsd=np.hypot(hc[:,0]-S[0],hc[:,1]-S[1])
    on=detect_onsets(ed_h,htc,THR)
    fin=np.isfinite(ed_h)
    ethd_median_all.append(np.nanmedian(ed_h))
    frac_trace_above.append(np.mean(ed_h[fin]>THR) if fin.any() else np.nan)
    for i in on:
        onset_ethd.append(ed_h[i])
        # percentile of onset head-source distance within trial (0=closest,100=farthest)
        dd=hsd[fin]
        onset_dist_pctile.append(100.0*np.mean(dd<hsd[i]))
    if example is None and on.size>20:
        example=(tr["file_name"], np.nanmedian(ed_h), ed_h[on][:10], np.nanmax(ed_h))

onset_ethd=np.array(onset_ethd); onset_dist_pctile=np.array(onset_dist_pctile)
frac_trace_above=np.array(frac_trace_above); ethd_median_all=np.array(ethd_median_all)
print("THR=%.6f  (ethdeconv global range ~[-0.02,0.14])" % THR)
print("per-trial median ethdeconv: median across trials=%.6f  (frac of trials with median>THR=%.2f)"
      % (np.nanmedian(ethd_median_all), np.mean(ethd_median_all>THR)))
print("frac of each trace above THR: median=%.3f mean=%.3f min=%.3f max=%.3f"
      % (np.nanmedian(frac_trace_above),np.nanmean(frac_trace_above),np.nanmin(frac_trace_above),np.nanmax(frac_trace_above)))
print()
print("ethdeconv AT onset: median=%.5f  (vs THR=%.5f)  frac>0.01=%.2f  frac>0.05=%.2f"
      % (np.median(onset_ethd), THR, np.mean(onset_ethd>0.01), np.mean(onset_ethd>0.05)))
print("onset head-source distance PERCENTILE within trial (0=nearest,100=farthest):")
print("  median=%.1f  mean=%.1f  frac in nearest 20%%=%.2f  frac in nearest 50%%=%.2f  frac in farthest 20%%=%.2f"
      % (np.median(onset_dist_pctile),np.mean(onset_dist_pctile),
         np.mean(onset_dist_pctile<20),np.mean(onset_dist_pctile<50),np.mean(onset_dist_pctile>80)))
print()
print("example trial %s: trace median=%.5f  first onsets ethd=%s  trace max=%.5f"
      % (example[0],example[1],np.round(example[2],4),example[3]))
