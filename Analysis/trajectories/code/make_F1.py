"""F1 - Encounters vs tortuosity scatter (H1). Plots ONLY from saved result objects."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories"
DATA = os.path.join(BASE, "data")
FIGDIR = os.path.join(BASE, "reports", "figures")
os.makedirs(FIGDIR, exist_ok=True)

stats = json.load(open(os.path.join(DATA, "stats.json")))
metrics = json.load(open(os.path.join(DATA, "trajectory_metrics.json")))
H1 = stats["H1"]
prim = H1["primary_n_encounters_vs_tortuosity"]

trials = metrics["trials"]
pooled = [t for t in trials if t["in_pooled"]]
another = [t for t in trials if t["end_loc"] == "anotherLoc"]

# color by end_location
locs = sorted({t["end_loc"] for t in pooled})
cmap = plt.get_cmap("tab10")
loc_color = {loc: cmap(i) for i, loc in enumerate(locs)}

px = np.array([t["n_encounters"] for t in pooled], float)
py = np.array([t["tortuosity"] for t in pooled], float)
ax_col = [loc_color[t["end_loc"]] for t in pooled]

ax = np.array([t["n_encounters"] for t in another], float)
ay = np.array([t["tortuosity"] for t in another], float)

fig, axm = plt.subplots(figsize=(8, 6))
for loc in locs:
    xs = [t["n_encounters"] for t in pooled if t["end_loc"] == loc]
    ys = [t["tortuosity"] for t in pooled if t["end_loc"] == loc]
    axm.scatter(xs, ys, s=40, color=loc_color[loc], edgecolor="k",
                linewidth=0.3, alpha=0.85, label=f"{loc} (n={len(xs)})", zorder=3)

# OLS trend line (D12): tortuosity on n_encounters, POOLED only
slope, intercept = np.polyfit(px, py, 1)
xline = np.linspace(px.min(), px.max(), 100)
axm.plot(xline, slope * xline + intercept, "r--", lw=2,
         label="OLS trend (D12, pooled)", zorder=4)

# anotherLoc as distinct marker, EXCLUDED from fit
axm.scatter(ax, ay, s=70, marker="^", facecolor="none", edgecolor="dimgray",
            linewidth=1.4, label=f"anotherLoc (n={len(another)}, excl. fit)", zorder=3)

ci = prim["ci95_boot_trial"]
annot = (f"Spearman $\\rho$ = {prim['spearman_rho']:.3f}\n"
         f"95% CI [{ci[0]:.3f}, {ci[1]:.3f}]\n"
         f"p = {prim['p']:.2e}   (n = {prim['n']})")
axm.text(0.97, 0.03, annot, transform=axm.transAxes, ha="right", va="bottom",
         fontsize=10, bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))

axm.set_xlabel("Ethanol encounters per trial (counts)")
axm.set_ylabel("Tortuosity (path_length / straight_line, unitless)")
axm.set_title("F1 - Ethanol encounters vs trajectory tortuosity (pooled Loc1-6)")
axm.set_yscale("log")
axm.legend(loc="upper left", fontsize=8, framealpha=0.9)
fig.tight_layout()

png = os.path.join(FIGDIR, "F1_encounters_vs_tortuosity.png")
pdf = os.path.join(FIGDIR, "F1_encounters_vs_tortuosity.pdf")
fig.savefig(png, dpi=200, bbox_inches="tight")
fig.savefig(pdf, bbox_inches="tight")
plt.close(fig)

# sidecar
txt = os.path.join(FIGDIR, "F1_encounters_vs_tortuosity.txt")
with open(txt, "w", encoding="utf-8") as fh:
    fh.write("F1 - Encounters vs tortuosity scatter\n")
    fh.write("Source files:\n")
    fh.write("  data/stats.json  (H1.primary_n_encounters_vs_tortuosity)\n")
    fh.write("  data/trajectory_metrics.json  (per-trial n_encounters, tortuosity, end_loc, in_pooled)\n\n")
    fh.write("Plotted points: pooled Loc1-6 trials, one per trial.\n")
    fh.write(f"  n_pooled = {len(pooled)}\n")
    fh.write(f"  n_anotherLoc (distinct marker, EXCLUDED from OLS fit) = {len(another)}\n\n")
    fh.write("Exact numbers drawn (from stats.json):\n")
    fh.write(f"  Spearman rho(n_encounters, tortuosity) = {prim['spearman_rho']}\n")
    fh.write(f"  95% CI (trial bootstrap) = [{ci[0]}, {ci[1]}]\n")
    fh.write(f"  p = {prim['p']}\n")
    fh.write(f"  n = {prim['n']}\n")
    fh.write(f"  direction = {prim['direction']}\n")
    fh.write(f"  prior_rho = {prim['prior_rho']}, prior_p = {prim['prior_p']}\n")
    fh.write(f"  accept_H1 = {prim['accept_H1']}\n\n")
    fh.write("Red dashed OLS trend line (computed on POOLED points only, for display):\n")
    fh.write(f"  tortuosity = {slope:.6f} * n_encounters + {intercept:.6f}\n\n")
    fh.write("Per-location Spearman rho (from stats.json H1.per_location_rho...):\n")
    for loc, v in H1["per_location_rho_n_encounters_vs_tortuosity"].items():
        fh.write(f"  {loc}: rho={v['rho']:.4f}, p={v['p']:.4g}, n={v['n']}\n")
    aL = H1["anotherLoc_separate"]["n_encounters_vs_tortuosity"]
    fh.write(f"\nanotherLoc (separate): rho={aL['rho']:.4f}, p={aL['p']:.4g}, n={aL['n']}\n\n")
    fh.write("Pooled trials plotted (trial_index, end_loc, n_encounters, tortuosity):\n")
    for t in pooled:
        fh.write(f"  {t['trial_index']}\t{t['end_loc']}\t{t['n_encounters']}\t{t['tortuosity']:.4f}\t{t['file_name']}\n")
    fh.write("\nanotherLoc trials plotted (excluded from fit):\n")
    for t in another:
        fh.write(f"  {t['trial_index']}\t{t['end_loc']}\t{t['n_encounters']}\t{t['tortuosity']:.4f}\t{t['file_name']}\n")

print("F1 written:", png, pdf, txt)
print("sizes:", os.path.getsize(png), os.path.getsize(pdf), os.path.getsize(txt))
