import sys, os, json
import numpy as np
import h5py
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plume_common as pc
ROOT = os.path.dirname(HERE)

# ---------- Task1: verify anotherLoc excluded from pooled + 6 fields ----------
st=json.load(open(os.path.join(ROOT,"data","odor_field_stats.json")))
print("=== TASK1 pooled n_trials ===", st["pooled"]["n_trials"], "(expect 105 = Loc1-6)")
print("pooled endpoint_centroid", st["pooled"]["endpoint_centroid"])
print("robustness head-vs-body r =", st["robustness_head_vs_body"]["pearson_r"],
      "n bins", st["robustness_head_vs_body"]["n_common_valid_bins"])

# ---------- Task1: verify pooled max exp lambda headline 48.8 ----------
pm=st["pooled"]["distance"]["max"]["exp_decay"]
print("pooled max exp lambda =", pm["lambda"], "CI", pm["lambda_ci95"])
pols=st["pooled"]["distance"]["max"]["ols_log"]
print("pooled max OLS slope =", pols["slope"], "CI", pols["slope_ci95"])

# ---------- H1 null adequacy: gini vs uniform null ----------
print("\n=== H1 uniform null ===")
sp=st["pooled"]["sparseness"]
print("gini", sp["gini"], "uniform_null_gini", sp["gini_uniform_null"], "norm_entropy", sp["normalized_entropy"])
print("NOTE: uniform-null gini is trivially 0 (gini of np.ones). Not a sampling null; weak comparison.")

# ---------- Task1 report claims about frac>3xMAD etc: spot-check 4 numbers ----------
print("\n=== TASK1 spot-check stored vs report table ===")
for g in ["Loc1","Loc4","Loc6"]:
    s=st["locations"][g]["sparseness"]
    print(f"  {g}: gini={s['gini']:.3f} entropy={s['normalized_entropy']:.3f} frac3x={s['frac_above_3xMAD']:.3f} top5={s['top5pct_mass_share']:.3f}")

# ---------- Task2: unit-scale check. thr_before on drift-corrected RAW scale ----------
print("\n=== TASK2 unit scale check ===")
trials, meta = pc.load_trials()
tr=trials[9]  # a Loc5 trial
raw=np.asarray(tr["ethanol"],float)
print("raw ethanol range", np.nanmin(raw), np.nanmax(raw))
ethd=np.asarray(tr["ethdeconv"],float)
print("ethdeconv range", np.nanmin(ethd), np.nanmax(ethd))
print("thr_before=0.01558 -> compared to drift-corrected RAW (raw scale ~[-0.3,1.0]); NOT ethdeconv. OK")

# ---------- Task2 spot-check per-trial number vs H5 attrs ----------
print("\n=== TASK2 per-trial spot-check (stats vs H5 attrs) ===")
with h5py.File(os.path.join(ROOT,"data","enhanced_ethanol.h5"),"r") as f:
    for gid in ["009","094","041"]:
        g=f["trials"][gid]
        nb=g.attrs["n_before"]; na=g.attrs["n_after"]; sg=g.attrs["distal_snr_gain"]
        # find in stats
        rec=[p for p in st_e["per_trial"] if p["trial_index"]==int(gid)][0] if False else None
        print(f"  trial {gid}: H5 n_before={nb} n_after={na} snr_gain={sg:.4f}")
# reload enhancement stats
st_e=json.load(open(os.path.join(ROOT,"data","enhancement_stats.json")))
for ti in [9,94,41]:
    rec=[p for p in st_e["per_trial"] if p["trial_index"]==ti][0]
    print(f"  stats trial {ti}: n_before={rec['n_before']} n_after={rec['n_after']} snr_gain={rec['distal_snr_gain']:.4f}")

# ---------- verify distal count increase claim numbers in report ----------
print("\n=== TASK2 report headline numbers ===")
print("total_after=45331 total_before=46219 ->", st_e["counts"]["total_after"], st_e["counts"]["total_before"])
print("distal after/before =", st_e["counts"]["total_after_distal"], st_e["counts"]["total_before_distal"])
print("wilcoxon overall p =", st_e["wilcoxon"]["overall"]["pvalue"])
print("median drift timescale =", st_e["median_drift_timescale_s"], "(report says 0.61s, W=20s)")
