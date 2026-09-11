r"""verify_gate1.py -- INDEPENDENT Gate-1 verifier for reactions_2.
Recomputes kinematics/bouts from scratch using ONLY the accessor + reactions2_common
loaders, and cross-checks against data/bouts.h5 and data/stats.json. Does NOT import
build_bouts. Run with "$AR_PY".
"""
import os, sys, json
import numpy as np
import h5py
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reactions2_common as r2
import plume_common as pc

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
H5 = os.path.join(BASE, "data", "bouts.h5")
STATS = os.path.join(BASE, "data", "stats.json")
ODOR = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5"
POOLED = {"Loc1","Loc2","Loc3","Loc4","Loc5","Loc6"}

def line(s): print(s)

# ------------------------------------------------------------ 1. fresh h5 open
line("=== FRESH h5py OPEN ===")
with h5py.File(H5, "r") as f:
    line(f"root attrs build_complete={f.attrs['build_complete']} seed={f.attrs['seed']} "
         f"VERSION={f.attrs['VERSION']}")
    line(f"root v_pause={f.attrs['v_pause_px_s']:.5f} omega_min={f.attrs['omega_min_deg_s']:.5f} "
         f"achieved_rate={f.attrs['achieved_pooled_median_rate_per_s']:.6f}")
    line(f"groups: {list(f.keys())}")
    bt = f["bouts"]
    line(f"/bouts cols: {list(bt.keys())}  n_bouts={bt['onset_time'].shape[0]}")
    tg = f["trials"]
    tkeys = sorted(tg.keys())
    line(f"/trials n_groups={len(tkeys)}")
    g0 = tg[tkeys[0]]
    line(f"/trials/{tkeys[0]} datasets: {list(g0.keys())}")
    line(f"/trials/{tkeys[0]} attrs: {list(g0.attrs.keys())}")
    # gzip check
    ds = g0["head_c"]
    line(f"head_c compression={ds.compression}")
    line(f"figure_curves: {list(f['figure_curves'].keys())}")
    # per-trial counts for cross-check + bout counts
    h5_counts = {}
    h5_fbout = {}
    h5_focc = {}
    h5_endloc = {}
    h5_rate = {}
    for k in tkeys:
        g = tg[k]
        ti = int(k)
        h5_counts[ti] = int(g.attrs["bout_count"])
        h5_fbout[ti] = float(g.attrs["f_bout"])
        h5_focc[ti] = float(g.attrs["f_occ"])
        h5_endloc[ti] = g.attrs["end_loc"]
        h5_rate[ti] = float(g.attrs["bout_rate"])
    # bouts table trial_index -> count
    tv = bt["trial_index"][()]
    in_pooled_bt = bt["in_pooled"][()]
    n_bouts_pooled_h5 = int(in_pooled_bt.sum())

line(f"n_bouts_pooled (from /bouts in_pooled) = {n_bouts_pooled_h5}")

with open(STATS) as fp:
    S = json.load(fp)

# ------------------------------------------------------------ 2. recompute kinematics
line("\n=== RECOMPUTE FROM ACCESSOR ===")
trials, meta = pc.load_trials()
line(f"loaded {len(trials)} trials Fs={meta['Fs']}")
Qh = r2.pooled_dejump_Q(trials, "head")
Qb = r2.pooled_dejump_Q(trials, "body")
line(f"Q head={Qh:.3f} body={Qb:.3f}")

kins = {}
head_rm=[]; body_rm=[]
for ti, tr in enumerate(trials):
    ht = np.asarray(tr["head_time"], float); bt_ = np.asarray(tr["body_time"], float)
    head = np.asarray(tr["head"], float); body = np.asarray(tr["body"], float)
    idx_h, head_c, ht_c = r2.clean_track(head, ht, Qh)
    idx_b, body_c, bt_c = r2.clean_track(body, bt_, Qb)
    nhb = int(pc._in_box(head).sum()); nbb = int(pc._in_box(body).sum())
    if nhb: head_rm.append(1-head_c.shape[0]/nhb)
    if nbb: body_rm.append(1-body_c.shape[0]/nbb)
    if head_c.shape[0] < r2.SG_WIN+2 or bt_c.size < 2:
        kins[ti]=None; continue
    dt = float(np.median(np.diff(ht_c)))
    if not np.isfinite(dt) or dt<=0:
        kins[ti]=None; continue
    body_h = r2.interp_xy_to_head(ht_c, bt_c, body_c)
    v_com = r2.speed_savgol(body_h, dt)
    phi = r2.bearing_phi(head_c, body_h)
    omega = r2.angular_speed_omega(phi, dt)
    eth = np.asarray(tr["ethanol"], float); eth_t = np.asarray(tr["ethanol_time"], float)
    eth_bs = r2.align_signal(ht_c, eth_t, r2.baseline_subtract_ethanol(eth, eth_t))
    dur = float(ht_c[-1]-ht_c[0])
    kins[ti]={"head_c":head_c,"head_t":ht_c,"dt":dt,"v_com":v_com,"phi":phi,
              "omega":omega,"eth_bs":eth_bs,"dur":dur,
              "end_loc":r2.group_of(tr["file_name"]),"endpoint":r2.endpoint_of(tr)}

line(f"de-jump removed frac head={np.nanmean(head_rm)*100:.3f}%  body={np.nanmean(body_rm)*100:.3f}%")

# pooled thresholds
vpool = np.concatenate([k["v_com"][np.isfinite(k["v_com"])] for k in kins.values() if k])
opool = np.concatenate([k["omega"][np.isfinite(k["omega"])] for k in kins.values() if k])
v_pause = float(np.percentile(vpool, 25.0))
omega_min = float(np.percentile(opool, 90.0))
line(f"RECOMPUTED v_pause(25pct)={v_pause:.5f}  omega_min(90pct)={omega_min:.5f}")
line(f"STORED     v_pause       ={S['meta']['v_pause_px_s']:.5f}  omega_min       ={S['meta']['omega_min_deg_s']:.5f}")

# ------------------------------------------------------------ 3. detect bouts
line("\n=== DETECT BOUTS (recomputed) ===")
my_counts={}; my_rate={}; my_bouts={}
odor_cache={}
def get_field(loc):
    if loc not in odor_cache:
        odor_cache[loc]=r2.load_odor_field(loc, path=ODOR) if (loc in POOLED or loc=="anotherLoc") else None
    return odor_cache[loc]

for ti,k in kins.items():
    if k is None: continue
    bouts = r2.detect_bouts(k["v_com"],k["phi"],k["omega"],k["head_t"],v_pause,omega_min,
                            tau_pause=r2.TAU_PAUSE,dphi_min=r2.DPHI_MIN,t_merge=r2.T_MERGE)
    my_counts[ti]=len(bouts)
    my_rate[ti]=len(bouts)/k["dur"] if k["dur"]>0 else np.nan
    my_bouts[ti]=bouts

pooled_ti=[ti for ti in kins if kins[ti] and kins[ti]["end_loc"] in POOLED]
another_ti=[ti for ti in kins if kins[ti] and kins[ti]["end_loc"]=="anotherLoc"]
line(f"n_pooled_trials={len(pooled_ti)}  n_anotherLoc={len(another_ti)}")
rates_pooled=[my_rate[ti] for ti in pooled_ti if np.isfinite(my_rate[ti])]
med_rate=float(np.median(rates_pooled))
line(f"RECOMPUTED pooled median bout rate = {med_rate:.6f} /s   (stored {S['deliverable_A']['rarity']['pooled_median_bout_rate_per_s']:.6f})")
line(f"D6 gate: {med_rate:.6f} <= 0.5 trigger? {med_rate<=0.5}   <<1.7? {med_rate<1.7}")
n_bouts_pooled_mine=sum(my_counts[ti] for ti in pooled_ti)
line(f"n_bouts_pooled recomputed = {n_bouts_pooled_mine}  (h5 {n_bouts_pooled_h5})")
cnts=np.array([my_counts[ti] for ti in pooled_ti])
line(f"count dist min={cnts.min()} median={np.median(cnts)} max={cnts.max()}")
line(f"frac trials >=1 bout = {np.mean(cnts>=1):.4f}  (stored {S['deliverable_A']['rarity']['frac_trials_ge1_bout']:.4f})")

# ------------------------------------------------------------ 4. count cross-check vs h5 (>=2 trials)
line("\n=== BOUT COUNT CROSS-CHECK vs h5 (per-trial) ===")
mismatch=0; checked=0
for ti in sorted(my_counts):
    if ti in h5_counts:
        checked+=1
        d=abs(my_counts[ti]-h5_counts[ti])
        if d>1:
            mismatch+=1
            line(f"  trial {ti}: mine={my_counts[ti]} h5={h5_counts[ti]} DIFF={d}")
line(f"checked {checked} trials; count diffs >1: {mismatch}")
# show a couple example trials explicitly
ex_show=[t for t in [47,0,1,2,5] if t in my_counts][:3]
for t in ex_show:
    line(f"  trial {t}: mine={my_counts.get(t)} h5={h5_counts.get(t)}")

# ------------------------------------------------------------ 5. H3 one-trial f_bout/f_occ
line("\n=== H3 one-trial f_bout/f_occ recompute ===")
# pick a pooled trial with a bout and a field
tgt=None
for ti in pooled_ti:
    if my_counts[ti]>=1 and get_field(kins[ti]["end_loc"]) is not None:
        tgt=ti; break
if tgt is not None:
    k=kins[tgt]; field=get_field(k["end_loc"])
    all_io=r2.is_in_odor(field,k["head_c"][:,0],k["head_c"][:,1],cutoff=r2.ODOR_CUTOFF)
    focc=float(np.mean(all_io))
    onset_idx=np.array([b["onset_idx"] for b in my_bouts[tgt]],int)
    io=r2.is_in_odor(field,k["head_c"][onset_idx,0],k["head_c"][onset_idx,1],cutoff=r2.ODOR_CUTOFF)
    fbout=float(np.mean(io))
    line(f"trial {tgt} ({k['end_loc']}): f_bout={fbout:.4f} f_occ={focc:.4f}  "
         f"| h5 f_bout={h5_fbout.get(tgt):.4f} f_occ={h5_focc.get(tgt):.4f}")

# ------------------------------------------------------------ 6. H3 pooled medians
line("\n=== H3 pooled medians ===")
ge1=[ti for ti in pooled_ti if my_counts[ti]>=1]
fbouts=[]; foccs=[]; diffs=[]
for ti in ge1:
    k=kins[ti]; field=get_field(k["end_loc"])
    if field is None: continue
    all_io=r2.is_in_odor(field,k["head_c"][:,0],k["head_c"][:,1],cutoff=r2.ODOR_CUTOFF)
    onset_idx=np.array([b["onset_idx"] for b in my_bouts[ti]],int)
    io=r2.is_in_odor(field,k["head_c"][onset_idx,0],k["head_c"][onset_idx,1],cutoff=r2.ODOR_CUTOFF)
    fb=float(np.mean(io)); fo=float(np.mean(all_io))
    fbouts.append(fb); foccs.append(fo); diffs.append(fb-fo)
line(f"median f_bout={np.median(fbouts):.4f} (stored {S['H3']['direction_first']['median_f_bout']})")
line(f"median f_occ={np.median(foccs):.4f} (stored {S['H3']['direction_first']['median_f_occ']:.4f})")
w=stats.wilcoxon(np.array(diffs),alternative="greater",zero_method="wilcox")
line(f"f_bout>f_occ Wilcoxon p={w.pvalue:.4f} (stored {S['H3']['f_bout_gt_f_occ']['p_greater']:.4f}) n={len(diffs)}")

# ------------------------------------------------------------ 7. selectivity check
line("\n=== SELECTIVITY (recomputed per-trial medians over ge1) ===")
bv=[]; bo=[]
for ti in ge1:
    bvc=np.array([b["v_com_during"] for b in my_bouts[ti]])
    bpo=np.array([b["peak_omega"] for b in my_bouts[ti]])
    bv.append(np.nanmean(bvc)); bo.append(np.nanmean(bpo))
line(f"median bout v_com={np.median(bv):.4f} (stored {S['deliverable_A']['selectivity']['median_v_com_bouts']:.4f})")
line(f"median bout peak_omega={np.median(bo):.2f} (stored {S['deliverable_A']['selectivity']['median_peak_omega_bouts_deg_s']:.2f})")

# ------------------------------------------------------------ 8. kinematic sanity on example trial
line("\n=== EXAMPLE TRIAL 47 sanity (bout onsets in low-v_com, big excursion) ===")
if 47 in my_bouts:
    k=kins[47]
    for b in my_bouts[47][:6]:
        oi=b["onset_idx"]
        line(f"  onset t={k['head_t'][oi]:.2f}s v_com_during={b['v_com_during']:.3f} "
             f"(v_pause={v_pause:.2f}) excursion={b['excursion_deg']:.1f}deg peak_omega={b['peak_omega']:.1f}")
line(f"eth_bs range on trial47: [{np.nanmin(k['eth_bs']):.3f},{np.nanmax(k['eth_bs']):.3f}]")

line("\n=== DONE ===")
