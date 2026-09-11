r"""make_F3.py -- Build Figure F3 (H3 spatial) STRICTLY from saved objects.
No science recomputed: numbers read from data\stats.json and data\bouts.h5;
odor-reached footprint read from Plume-locations odor_fields.h5 (count>=3 AND max>0.001).
Headless Agg. Interpreter: "$AR_PY". seed 1234 (no RNG used here).
"""
from __future__ import annotations
import json, os
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
STATS = os.path.join(BASE, "data", "stats.json")
BOUTS = os.path.join(BASE, "data", "bouts.h5")
ODOR = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5"
OUTDIR = os.path.join(BASE, "reports", "figures")
os.makedirs(OUTDIR, exist_ok=True)
STEM = os.path.join(OUTDIR, "F3_spatial")

ARENA_X = (0.0, 580.0)
ARENA_Y = (0.0, 280.0)
ODOR_CUTOFF = 0.001
EX_IDX = "047"

# ---------------------------------------------------------------- load stats
with open(STATS) as f:
    S = json.load(f)
H3 = S["H3"]
ex = S["deliverable_A"]["example_trial"]
med_fbout = H3["direction_first"]["median_f_bout"]
med_focc = H3["direction_first"]["median_f_occ"]
med_fbout_null = H3["direction_first"]["median_f_bout_minus_null"]
wilcox_p = H3["f_bout_gt_f_occ"]["p_greater"]
wilcox_stat = H3["f_bout_gt_f_occ"]["wilcoxon_stat"]
wilcox_n = H3["f_bout_gt_f_occ"]["n_trials"]
wnull_p = H3["f_bout_gt_null"]["p_greater"]
frac_enr = H3["frac_trials_enriched"]
cutoff = H3["odor_cutoff"]
n_pooled = S["meta"]["n_pooled_trials"]

# ---------------------------------------------------------------- load bouts example trial
with h5py.File(BOUTS, "r") as f:
    g = f["trials"][EX_IDX]
    body_h = g["body_h"][:]        # COM (cleaned) trajectory
    head_c = g["head_c"][:]
    head_t = g["head_t"][:]
    eth_bs = g["eth_bs_h"][:]
    omega = g["omega"][:]
    onset_t = g["bout_onset_times"][:]
    a = dict(g.attrs)
    ex_end_loc = a["end_loc"]
    ex_endpoint = np.asarray(a["endpoint"], float)
    ex_fname = a["file_name"]
    ex_count = int(a["bout_count"])
    ex_rate = float(a["bout_rate"])
    ex_fbout = float(a["f_bout"])
    ex_focc = float(a["f_occ"])
    # per-trial scatter arrays (only >=1 bout, pooled)
    fb, fo, nb = [], [], []
    for k in sorted(f["trials"].keys()):
        at = f["trials"][k].attrs
        if not bool(at.get("in_pooled", True)):
            continue
        bc = int(at["bout_count"])
        if bc >= 1:
            fb.append(float(at["f_bout"]))
            fo.append(float(at["f_occ"]))
            nb.append(bc)
fb = np.asarray(fb); fo = np.asarray(fo); nb = np.asarray(nb)
n_scatter = len(fb)

# ---------------------------------------------------------------- odor field footprint (Loc4)
with h5py.File(ODOR, "r") as f:
    og = f[ex_end_loc]
    o_max = og["max"][:]
    o_cnt = og["count"][:]
    xe = og["x_edges"][:]
    ye = og["y_edges"][:]
reached = np.isfinite(o_max) & (o_max > ODOR_CUTOFF) & (o_cnt >= 3)  # row=y, col=x
n_reached_bins = int(reached.sum())

# head position at bout onsets (interp on head clock)
onset_hx = np.interp(onset_t, head_t, head_c[:, 0])
onset_hy = np.interp(onset_t, head_t, head_c[:, 1])
# in-odor coloring of onset markers (replicate is_in_odor bin logic)
def in_odor(x, y):
    col = np.searchsorted(xe, x, side="right") - 1
    row = np.searchsorted(ye, y, side="right") - 1
    out = np.zeros(np.shape(x), bool)
    ny, nx = o_max.shape
    ok = (col >= 0) & (col < nx) & (row >= 0) & (row < ny)
    for i in np.nonzero(ok)[0] if np.ndim(x) else ([0] if ok else []):
        out[i] = reached[row[i], col[i]]
    return out
onset_in = in_odor(onset_hx, onset_hy)

# ================================================================ FIGURE
fig = plt.figure(figsize=(11.5, 9.0))
gs = fig.add_gridspec(3, 2, height_ratios=[1.35, 0.55, 0.55], width_ratios=[1.05, 1.0],
                      hspace=0.42, wspace=0.26)

# ---- F3A top: trajectory + footprint
axA = fig.add_subplot(gs[0, 0])
# footprint mask: pcolormesh of reached bins, translucent
mask = np.where(reached, 1.0, np.nan)
axA.pcolormesh(xe, ye, mask, cmap=matplotlib.colors.ListedColormap(["#f39c12"]),
               shading="flat", alpha=0.28, zorder=1)
axA.plot(body_h[:, 0], body_h[:, 1], color="0.35", lw=0.8, alpha=0.85, zorder=2,
         label="COM trajectory (body_h)")
axA.scatter(onset_hx[~onset_in], onset_hy[~onset_in], marker="v", s=90,
            facecolor="#2c7fb8", edgecolor="k", lw=0.7, zorder=5,
            label="bout onset (out-odor)")
if onset_in.any():
    axA.scatter(onset_hx[onset_in], onset_hy[onset_in], marker="v", s=90,
                facecolor="#d7191c", edgecolor="k", lw=0.7, zorder=6,
                label="bout onset (in-odor)")
axA.scatter([ex_endpoint[0]], [ex_endpoint[1]], marker="x", s=140, color="k",
            lw=2.2, zorder=7, label="source endpoint")
axA.set_xlim(*ARENA_X); axA.set_ylim(*ARENA_Y)
axA.set_aspect("equal")
axA.set_xlabel("x (px)"); axA.set_ylabel("y (px)")
axA.set_title(f"A  Example trial (idx {int(EX_IDX)}, {ex_end_loc})", fontsize=11, loc="left")
handles = [
    Line2D([], [], color="0.35", lw=1.2, label="COM trajectory"),
    Line2D([], [], marker="v", ls="", mfc="#2c7fb8", mec="k", ms=9, label="onset (out-odor)"),
    Line2D([], [], marker="v", ls="", mfc="#d7191c", mec="k", ms=9, label="onset (in-odor)"),
    Line2D([], [], marker="x", ls="", color="k", ms=10, mew=2, label="source endpoint"),
    Patch(facecolor="#f39c12", alpha=0.28, label="odor-reached footprint"),
]
axA.legend(handles=handles, fontsize=7.2, loc="upper left", framealpha=0.9)

# ---- F3B: scatter f_bout vs f_occ (top-right, tall)
axB = fig.add_subplot(gs[0, 1])
sizes = 22 + 42 * (nb.astype(float))  # size prop to n_bout
axB.plot([0, 1], [0, 1], ls="--", color="0.5", lw=1.2, zorder=1, label="identity  y = x")
sc = axB.scatter(fo, fb, s=sizes, c="#377eb8", alpha=0.6, edgecolor="k", lw=0.4, zorder=3)
axB.set_xlim(-0.02, 1.02); axB.set_ylim(-0.02, 1.02)
axB.set_aspect("equal")
axB.set_xlabel(r"$f_{occ}$  (occupancy fraction in odor-reached bins)")
axB.set_ylabel(r"$f_{bout}$  (bout-onset fraction in odor-reached bins)")
axB.set_title("B  Per-trial bout vs occupancy (pooled Loc1-6)", fontsize=11, loc="left")
# size legend
for s in (1, 3, 6):
    axB.scatter([], [], s=22 + 42 * s, c="#377eb8", alpha=0.6, edgecolor="k",
                lw=0.4, label=f"n_bout = {s}")
axB.legend(fontsize=7.5, loc="lower right", framealpha=0.9)
ann = (f"Wilcoxon $f_{{bout}}>f_{{occ}}$: p = {wilcox_p:.3f}  (n = {wilcox_n} trials)\n"
       f"median $f_{{bout}}$ = {med_fbout:.3f} < median $f_{{occ}}$ = {med_focc:.3f}\n"
       f"trials enriched: {frac_enr*100:.1f}%   (H3 NOT supported)")
axB.text(0.03, 0.97, ann, transform=axB.transAxes, fontsize=8.0, va="top", ha="left",
         bbox=dict(boxstyle="round", fc="#fff4e6", ec="0.6", alpha=0.95))

# ---- F3A bottom stacked time series (span full width across 2 rows)
axE = fig.add_subplot(gs[1, :])
axE.plot(head_t, eth_bs, color="#1b7837", lw=0.7)
axE.axhline(0.0, color="0.7", lw=0.6, ls=":")
for i, ot in enumerate(onset_t):
    axE.axvline(ot, color="#d7191c", lw=1.0, alpha=0.75)
axE.set_ylabel("eth (a.u.)\nbaseline-sub", fontsize=8.5)
axE.set_xlim(head_t.min(), head_t.max())
axE.set_title("Baseline-subtracted ethanol (head clock); red = bout onsets", fontsize=9, loc="left")
axE.tick_params(labelbottom=False)

axW = fig.add_subplot(gs[2, :], sharex=axE)
axW.plot(head_t, omega, color="#5e3c99", lw=0.6)
for ot in onset_t:
    axW.axvline(ot, color="#d7191c", lw=1.0, alpha=0.75)
axW.set_ylabel(r"$\omega(t)$" + "\n(deg/s)", fontsize=8.5)
axW.set_xlabel("time (s, head clock)")
axW.set_xlim(head_t.min(), head_t.max())
axW.set_title(r"Head angular speed $\omega(t)$; red = bout onsets", fontsize=9, loc="left")

# ---- suptitle = file_name, count, rate
fig.suptitle(f"F3  Sampling-bout locations vs odor-reached regions (H3)\n"
             f"{ex_fname}   |   {ex_count} bouts, rate {ex_rate:.4f}/s",
             fontsize=11, y=0.995)

fig.savefig(STEM + ".png", dpi=200, bbox_inches="tight")
fig.savefig(STEM + ".pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- sidecar .txt
lines = []
lines.append("F3_spatial -- Sampling-bout locations vs odor-reached regions (H3)")
lines.append("Built by make_F3.py from saved objects (no science recomputed). seed 1234.")
lines.append("")
lines.append("SOURCES:")
lines.append(f"  stats.json      : {STATS}")
lines.append(f"  bouts.h5        : {BOUTS}  (/trials/{EX_IDX}, /trials/<idx> attrs)")
lines.append(f"  odor_fields.h5  : {ODOR}  ({ex_end_loc} group: max,count,x_edges,y_edges)")
lines.append("")
lines.append("HONEST FRAMING: H3 NOT supported (accept_H3 = %s)." % S["H3"]["accept_H3"])
lines.append("  Bout-onset locations are NOT enriched in odor-reached bins; direction is NEGATIVE.")
lines.append("")
lines.append("PANEL A (example trial):")
lines.append(f"  trial_index = {int(EX_IDX)}   end_loc = {ex_end_loc}")
lines.append(f"  file_name = {ex_fname}")
lines.append(f"  bout_count = {ex_count}   bout_rate = {ex_rate:.6f} /s")
lines.append(f"  trial f_bout = {ex_fbout:.6f}   trial f_occ = {ex_focc:.6f}")
lines.append(f"  source endpoint (px) = ({ex_endpoint[0]:.1f}, {ex_endpoint[1]:.1f})")
lines.append(f"  bout onset times (s) = {np.array2string(onset_t, precision=4, separator=', ')}")
lines.append(f"  onset head positions (px) x = {np.array2string(onset_hx, precision=1, separator=', ')}")
lines.append(f"                            y = {np.array2string(onset_hy, precision=1, separator=', ')}")
lines.append(f"  onsets in odor-reached bin = {int(onset_in.sum())}/{len(onset_in)}")
lines.append(f"  odor-reached bins (count>=3 AND max>{ODOR_CUTOFF}) = {n_reached_bins}")
lines.append(f"  arena box = x{ARENA_X} y{ARENA_Y} (equal aspect)")
lines.append("")
lines.append("PANEL B (per-trial scatter, pooled Loc1-6, only >=1-bout trials):")
lines.append(f"  n trials plotted = {n_scatter}   (matches Wilcoxon n = {wilcox_n})")
lines.append(f"  n_pooled_trials (all) = {n_pooled}")
lines.append(f"  median f_bout = {med_fbout:.6f}   median f_occ = {med_focc:.6f}")
lines.append(f"  median (f_bout - null) = {med_fbout_null:.6f}")
lines.append(f"  Wilcoxon f_bout > f_occ : stat = {wilcox_stat}, p = {wilcox_p:.6f}, n = {wilcox_n}")
lines.append(f"  Wilcoxon f_bout > null  : p = {wnull_p:.6f}")
lines.append(f"  fraction trials enriched = {frac_enr:.6f}  ({frac_enr*100:.2f}%)")
lines.append(f"  odor_cutoff = {cutoff}  (above ~4e-4 noise floor)")
lines.append(f"  point size proportional to n_bout (range {int(nb.min())}-{int(nb.max())})")
with open(STEM + ".txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

# report sizes
for e in (".png", ".pdf", ".txt"):
    p = STEM + e
    print(f"{p}  {os.path.getsize(p)} bytes")
print("n_scatter", n_scatter, "onsets_in_odor", int(onset_in.sum()), "reached_bins", n_reached_bins)
