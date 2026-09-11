"""Build H1 figures F1 (2-panel) and F2B strictly from saved result objects.
Never recomputes the science: curves/stats come from stats.json; F2B points from sweeps.h5.
The only computation is the Spearman rho+CI+p of the *plotted* F2B points (seed 1234),
which describes the scatter itself (per figure spec)."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import h5py
from scipy.stats import spearmanr

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions"
DATA = BASE + r"\data"
FIGS = BASE + r"\reports\figures"
STATS_PATH = DATA + r"\stats.json"
H5_PATH = DATA + r"\sweeps.h5"
SEED = 1234

with open(STATS_PATH) as fh:
    S = json.load(fh)

# ---------------- F1: two stacked panels ----------------
f1a = S["F1A_peri_eth"]
f1b = S["F1B_peri_vcom"]
gA = np.array(f1a["grid_s"]); mA = np.array(f1a["mean"])
loA = np.array(f1a["ci_lo"]); hiA = np.array(f1a["ci_hi"])
gB = np.array(f1b["grid_s"]); mB = np.array(f1b["mean"])
loB = np.array(f1b["ci_lo"]); hiB = np.array(f1b["ci_hi"])
n_sweeps = f1a["n_sweeps"]; n_trials = f1a["n_trials"]

fig, (axA, axB) = plt.subplots(2, 1, figsize=(7.0, 7.5), sharex=True)

axA.fill_between(gA, loA, hiA, color="#1f77b4", alpha=0.25, label="95% CI")
axA.plot(gA, mA, color="#1f77b4", lw=2.0, label="mean")
axA.axvline(0.0, color="k", ls="--", lw=1.0, alpha=0.7)
axA.set_ylabel("Baseline-sub. ethanol (a.u.)")
axA.set_title("F1A  Peri-sweep ethanol")
axA.legend(loc="upper right", frameon=False, fontsize=8)
axA.annotate(f"n(sweeps)={n_sweeps:,}   n(trials)={n_trials}",
             xy=(0.02, 0.04), xycoords="axes fraction", fontsize=8, color="0.3")

axB.fill_between(gB, loB, hiB, color="#d62728", alpha=0.25, label="95% CI")
axB.plot(gB, mB, color="#d62728", lw=2.0, label="mean")
axB.axvline(0.0, color="k", ls="--", lw=1.0, alpha=0.7)
axB.set_ylabel("COM speed v_com (px/s)")
axB.set_xlabel("Time relative to sweep peak (s)")
axB.set_title("F1B  Peri-sweep COM speed")
axB.legend(loc="upper right", frameon=False, fontsize=8)
axB.annotate(f"n(sweeps)={n_sweeps:,}   n(trials)={n_trials}",
             xy=(0.02, 0.04), xycoords="axes fraction", fontsize=8, color="0.3")

fig.tight_layout()
f1_png = FIGS + r"\F1_peri_sweep_odor_and_com.png"
f1_pdf = FIGS + r"\F1_peri_sweep_odor_and_com.pdf"
fig.savefig(f1_png, dpi=200, bbox_inches="tight")
fig.savefig(f1_pdf, bbox_inches="tight")
plt.close(fig)

with open(FIGS + r"\F1_peri_sweep_odor_and_com.txt", "w") as fh:
    fh.write("F1 Peri-sweep ethanol (F1A) and COM speed (F1B)\n")
    fh.write("Source: data/stats.json keys F1A_peri_eth, F1B_peri_vcom\n")
    fh.write(f"Window (peri): {S['meta']['windows']['peri']} s, grid_dt={S['meta']['windows']['grid_dt']} s\n")
    fh.write(f"n_sweeps={n_sweeps}  n_trials={n_trials}\n\n")
    fh.write("F1A grid_s, mean, ci_lo, ci_hi (baseline-sub ethanol, a.u.):\n")
    for i in range(len(gA)):
        fh.write(f"  {gA[i]:+.2f}  {mA[i]:.6f}  {loA[i]:.6f}  {hiA[i]:.6f}\n")
    fh.write("\nF1B grid_s, mean, ci_lo, ci_hi (v_com, px/s):\n")
    for i in range(len(gB)):
        fh.write(f"  {gB[i]:+.2f}  {mB[i]:.4f}  {loB[i]:.4f}  {hiB[i]:.4f}\n")

# ---------------- F2B: scatter, one point per pooled sweep ----------------
with h5py.File(H5_PATH, "r") as hf:
    g = hf["sweeps"]
    in_pooled = g["in_pooled"][:].astype(bool)
    v_nose = g["v_nose"][:]
    summed_eth = g["summed_eth"][:]

mask = in_pooled & np.isfinite(v_nose) & np.isfinite(summed_eth)
x = v_nose[mask]
y = summed_eth[mask]
n_pts = int(x.size)

# Spearman of the PLOTTED points (describes the scatter) + bootstrap CI (seed 1234)
rho_plot, p_plot = spearmanr(x, y)
rng = np.random.default_rng(SEED)
B = 2000
boots = np.empty(B)
for b in range(B):
    idx = rng.integers(0, n_pts, n_pts)
    boots[b], _ = spearmanr(x[idx], y[idx])
ci_lo_plot, ci_hi_plot = np.percentile(boots, [2.5, 97.5])

fig2, ax = plt.subplots(figsize=(7.0, 5.5))
ax.scatter(x, y, s=4, alpha=0.12, color="#333333", edgecolors="none", rasterized=True)
ax.set_xlabel("Nose speed at sweep peak, v_nose (px/s)")
ax.set_ylabel("Summed baseline-sub. ethanol over [-0.5,+0.5]s (a.u.)")
ax.set_title("F2B  Nose speed vs local summed odor (pooled Loc1-6 sweeps)")
ax.axhline(0.0, color="0.6", lw=0.8, ls=":")
# clip x-axis to 99th pct for readability but note full range in sidecar
x99 = np.percentile(x, 99.5)
ax.set_xlim(0, x99)
ann = (f"Spearman (plotted pts)\n"
       f"rho={rho_plot:.3f}  95% CI [{ci_lo_plot:.3f}, {ci_hi_plot:.3f}]\n"
       f"p={p_plot:.2e}   n={n_pts:,}")
ax.annotate(ann, xy=(0.98, 0.97), xycoords="axes fraction", ha="right", va="top",
            fontsize=8, color="0.15",
            bbox=dict(boxstyle="round", fc="white", ec="0.7", alpha=0.9))
fig2.tight_layout()
f2_png = FIGS + r"\F2B_nose_vs_summed_odor.png"
f2_pdf = FIGS + r"\F2B_nose_vs_summed_odor.pdf"
fig2.savefig(f2_png, dpi=200, bbox_inches="tight")
fig2.savefig(f2_pdf, bbox_inches="tight")
plt.close(fig2)

with open(FIGS + r"\F2B_nose_vs_summed_odor.txt", "w") as fh:
    fh.write("F2B Nose speed vs summed baseline-sub ethanol (pooled Loc1-6 sweeps)\n")
    fh.write("Source: data/sweeps.h5 /sweeps columns v_nose, summed_eth, in_pooled\n")
    fh.write(f"eth_sum window: {S['meta']['windows']['eth_sum']} s\n")
    fh.write(f"n_points_plotted={n_pts} (in_pooled & finite v_nose & finite summed_eth)\n")
    fh.write("x = v_nose@peak (px/s); y = summed baseline-sub ethanol (a.u.)\n")
    fh.write(f"x range: {np.min(x):.3f} .. {np.max(x):.3f} px/s (x-axis clipped to 99.5pct={x99:.1f} for display)\n")
    fh.write(f"y range: {np.min(y):.4f} .. {np.max(y):.4f} a.u.\n\n")
    fh.write("Spearman of PLOTTED points (describes the scatter; seed 1234, 2000 bootstraps over points):\n")
    fh.write(f"  rho={rho_plot:.6f}  p={p_plot:.6e}  95% CI [{ci_lo_plot:.6f}, {ci_hi_plot:.6f}]\n\n")
    fh.write("NOTE: the pre-registered H1(c) inferential statistic is the R-based Spearman from stats.json:\n")
    hc = S["H1c_spearman"]
    fh.write(f"  rho(R@peak, summed eth_bs)={hc['rho']:.6f}  p={hc['p_value']:.6e}  "
             f"CI [{hc['ci95'][0]:.6f}, {hc['ci95'][1]:.6f}]  n_sweeps={hc['n_sweeps']}\n")

# emit computed F2B annotation numbers for the report script to reuse
with open(DATA + r"\_f2b_plot_stats.json", "w") as fh:
    json.dump(dict(rho=rho_plot, p=p_plot, ci_lo=ci_lo_plot, ci_hi=ci_hi_plot,
                   n_points=n_pts, seed=SEED, n_bootstrap=B), fh, indent=1)

print("F1 png/pdf/txt and F2B png/pdf/txt written.")
print(f"F2B plotted rho={rho_plot:.4f} CI[{ci_lo_plot:.4f},{ci_hi_plot:.4f}] p={p_plot:.2e} n={n_pts}")
