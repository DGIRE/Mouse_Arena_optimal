import sys, os, json
import numpy as np
import h5py
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plume_common as pc

ROOT = os.path.dirname(HERE)
print("=== LOAD ===")
trials, meta = pc.load_trials()
print("n_trials", len(trials))
groups = pc.group_trials(trials)
print("groups", {g: len(v) for g, v in sorted(groups.items())}, "sum", sum(len(v) for v in groups.values()))

# ---- validate endpoint spread ----
ginfo = pc.validate_groups(groups, warn=print)
for g, v in sorted(ginfo.items()):
    print(f"  {g}: n={v['n']} endpoint={v['endpoint']} spread={v['spread']}")

Q_head = pc.pooled_dejump_Q(trials, "head")
print("Q_head", Q_head)

# ============ TASK1 choose_L re-derivation for Loc1 ============
print("\n=== TASK1: choose_L re-derivation (Loc1) ===")
def grid_edges(L):
    xmin,xmax,ymin,ymax = pc.ARENA
    nx=int(np.ceil((xmax-xmin)/L)); ny=int(np.ceil((ymax-ymin)/L))
    return xmin+L*np.arange(nx+1), ymin+L*np.arange(ny+1), nx, ny
def bin_idx(xy,xe,ye):
    nx=xe.size-1; ny=ye.size-1
    col=np.clip(np.searchsorted(xe,xy[:,0],side="right")-1,0,nx-1)
    row=np.clip(np.searchsorted(ye,xy[:,1],side="right")-1,0,ny-1)
    return row,col

def cleaned_samples(trs):
    out=[]
    for tr in trs:
        head=np.asarray(tr["head"],float); ht=np.asarray(tr["head_time"],float)
        idx,xy,tc = pc.clean_track(head,ht,Q_head)
        if idx.size==0: continue
        eth=pc.align_signal(tc,np.asarray(tr["ethanol_time"],float),np.asarray(tr["ethdeconv"],float))
        cov=np.isfinite(eth)
        out.append((xy[cov],eth[cov]))
    return out

sl = cleaned_samples(groups["Loc1"])
for L in [40,30,25,20,15,10]:
    xe,ye,nx,ny=grid_edges(L)
    nmap=np.zeros((ny,nx),int); cnt=np.zeros((ny,nx),int)
    for xy,_ in sl:
        if xy.shape[0]==0: continue
        r,c=bin_idx(xy,xe,ye); flat=r*nx+c
        np.add.at(nmap.ravel(),flat,1)
        np.add.at(cnt.ravel(),np.unique(flat),1)
    vis=nmap>0; nvis=int(vis.sum())
    frac=float((cnt[vis]>=3).sum())/nvis if nvis else 0
    print(f"  L={L:2d} nvis={nvis:4d} cov={frac:.3f} meets60%={frac>=0.60}")
print("  -> smallest L meeting >=0.60 SHOULD be chosen (plan). Code chose L=40 (stored).")

# ============ TASK1 re-derive one valid bin mean from raw ============
print("\n=== TASK1: re-derive a Loc1 bin mean from raw data (L=40, stored grid) ===")
L=40; xe,ye,nx,ny=grid_edges(L)
sum_map=np.zeros((ny,nx)); n_map=np.zeros((ny,nx),int); cnt=np.zeros((ny,nx),int)
for xy,eth in sl:
    if xy.shape[0]==0: continue
    r,c=bin_idx(xy,xe,ye); flat=r*nx+c
    np.add.at(sum_map.ravel(),flat,eth)
    np.add.at(n_map.ravel(),flat,1)
    np.add.at(cnt.ravel(),np.unique(flat),1)
mean_map=np.where(n_map>0,sum_map/np.maximum(n_map,1),np.nan)
mean_map[cnt<3]=np.nan
# pick a valid bin with many samples
valid=np.argwhere((cnt>=3)&np.isfinite(mean_map))
# choose the bin with max count
best=valid[np.argmax([cnt[r,c] for r,c in valid])]
r,c=best
print(f"  bin (row={r},col={c}) count={cnt[r,c]} n_samp={n_map[r,c]} rederived_mean={mean_map[r,c]:.8g}")
# compare to stored h5
with h5py.File(os.path.join(ROOT,"data","odor_fields.h5"),"r") as f:
    stored=f["Loc1"]["mean"][r,c]
    scnt=f["Loc1"]["count"][r,c]
    print(f"  stored h5 Loc1 mean[{r},{c}]={stored:.8g} count={scnt}")
    print(f"  build_complete={f.attrs['build_complete']}  bin_size_px={f['Loc1'].attrs['bin_size_px']}")
    print("  MATCH" if abs(stored-mean_map[r,c])<1e-9 else "  MISMATCH")

print("\n=== TASK1 stored chosen_L per location (from stats) ===")
st=json.load(open(os.path.join(ROOT,"data","odor_field_stats.json")))
for g,d in st["locations"].items():
    print(f"  {g}: chosen_L={d['chosen_L']} cov={d['coverage_frac']:.3f} fallback={d['L_fallback_used']}")
