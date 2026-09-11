# -*- coding: utf-8 -*-
"""Build Figure F2A: v_nose@peak vs v_com@peak scatter (pooled Loc1-6 sweeps).
STRICTLY from saved objects: data/sweeps.h5 /sweeps columns v_nose, v_com, in_pooled.
Spearman rho + 95% CI + p of the PLOTTED points (seed 1234) is an annotation only
(describes the scatter); no science recomputed for the report.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import h5py
from scipy import stats

SEED = 1234
BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions"
H5 = os.path.join(BASE, "data", "sweeps.h5")
FIGDIR = os.path.join(BASE, "reports", "figures")
os.makedirs(FIGDIR, exist_ok=True)

# --- Load the two saved columns + pooling mask ---
with h5py.File(H5, "r") as f:
    g = f["sweeps"]
    v_nose = np.asarray(g["v_nose"][:], dtype=float)
    v_com = np.asarray(g["v_com"][:], dtype=float)
    in_pooled = np.asarray(g["in_pooled"][:], dtype=bool)

mask = in_pooled & np.isfinite(v_nose) & np.isfinite(v_com)
x = v_nose[mask]
y = v_com[mask]
n_pts = int(x.size)
assert n_pts > 0, "F2A: no plottable points"

# --- Spearman of the plotted points (annotation describing the scatter) ---
rho, p = stats.spearmanr(x, y)
rng = np.random.default_rng(SEED)
N_BOOT = 2000
boot = np.empty(N_BOOT, dtype=float)
idx = np.arange(n_pts)
for b in range(N_BOOT):
    s = rng.choice(idx, size=n_pts, replace=True)
    boot[b] = stats.spearmanr(x[s], y[s]).correlation
ci_lo, ci_hi = np.nanpercentile(boot, [2.5, 97.5])

# --- Display clipping (robust axis limits; points beyond are kept but axes trimmed) ---
xhi = float(np.percentile(x, 99.5))
yhi = float(np.percentile(y, 99.5))
axhi = max(xhi, yhi)

# --- Plot ---
fig, ax = plt.subplots(figsize=(5.4, 5.2))
ax.scatter(x, y, s=4, alpha=0.15, color="#1f4e79", edgecolors="none", rasterized=True)
ax.plot([0, axhi], [0, axhi], ls="--", lw=1.0, color="0.5", label="y = x")
ax.set_xlim(0, axhi)
ax.set_ylim(0, axhi)
ax.set_aspect("equal", adjustable="box")
ax.set_xlabel("Nose speed at sweep peak, v_nose (px/s)")
ax.set_ylabel("COM speed at sweep peak, v_com (px/s)")
ax.set_title("F2A  Nose vs COM speed per sweep (pooled Loc1-6)")

ann = (f"Spearman rho = {rho:.3f}\n"
       f"95% CI [{ci_lo:.3f}, {ci_hi:.3f}]\n"
       f"p = {p:.2e}\n"
       f"n = {n_pts} sweeps")
ax.text(0.03, 0.97, ann, transform=ax.transAxes, va="top", ha="left",
        fontsize=9, bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))
ax.legend(loc="lower right", fontsize=8, frameon=False)
fig.tight_layout()

png = os.path.join(FIGDIR, "F2A_nose_vs_com.png")
pdf = os.path.join(FIGDIR, "F2A_nose_vs_com.pdf")
fig.savefig(png, dpi=200, bbox_inches="tight")
fig.savefig(pdf, bbox_inches="tight")
plt.close(fig)

# --- Sidecar .txt ---
txt = os.path.join(FIGDIR, "F2A_nose_vs_com.txt")
with open(txt, "w", encoding="utf-8") as fh:
    fh.write("F2A Nose speed vs COM speed at sweep peak (pooled Loc1-6 sweeps)\n")
    fh.write("Source: data/sweeps.h5 /sweeps columns v_nose, v_com, in_pooled\n")
    fh.write("One point per pooled sweep; x = v_nose@peak (px/s), y = v_com@peak (px/s)\n")
    fh.write(f"n_points_plotted={n_pts} (in_pooled & finite v_nose & finite v_com)\n")
    fh.write(f"x range: {x.min():.3f} .. {x.max():.3f} px/s (axes trimmed to 99.5pct={axhi:.1f})\n")
    fh.write(f"y range: {y.min():.3f} .. {y.max():.3f} px/s\n\n")
    fh.write("Spearman of PLOTTED points (describes the scatter; seed 1234, 2000 bootstraps over points):\n")
    fh.write(f"  rho={rho:.6f}  p={p:.6e}  95% CI [{ci_lo:.6f}, {ci_hi:.6f}]\n\n")
    fh.write("NOTE: This annotation describes the plotted cloud only. H2 inference lives in\n")
    fh.write("data/stats.json (H2 block): primary R-set during-vs-baseline Wilcoxon and the\n")
    fh.write("non-circular numerator-only (body-frame) headline test.\n")

for pth in (png, pdf, txt):
    assert os.path.getsize(pth) > 0, f"empty output: {pth}"

print("F2A_OK")
print(f"n_pts={n_pts} rho={rho:.6f} p={p:.6e} ci=[{ci_lo:.6f},{ci_hi:.6f}]")
print(f"png_bytes={os.path.getsize(png)} pdf_bytes={os.path.getsize(pdf)} txt_bytes={os.path.getsize(txt)}")
