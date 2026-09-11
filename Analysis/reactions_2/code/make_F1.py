"""
Deliverable A -- Figure F1: bout definition (rarity) & selectivity.
STRICTLY from saved objects (data/stats.json, data/bouts.h5). No science recomputed.

(A) Per-trial bout-RATE distribution (from figure_curves/F1_rate == per-trial bout_rate),
    with v1 detector rate (1.7/s) as a reference line; annotate pooled median rate and
    % trials >=1 bout. Log-x given the huge v1-vs-new gap.
(B) Sampling bouts vs incidental: COM speed (bouts<<incidental) and head peak omega
    (bouts>=incidental) as strip+box; medians annotated from stats.json deliverable_A.

Number provenance:
  * Panel A annotations (median rate, %>=1) : stats.json deliverable_A.rarity  (== F1_rate array)
  * Panel A v1 reference line               : stats.json ...v1_baseline_rate_per_s
  * Panel B annotated medians               : stats.json deliverable_A.selectivity (authoritative)
  * Panel B plotted point clouds            : bouts.h5 figure_curves/F1_* (pooled per-event arrays)
"""
import json, os
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
STATS = os.path.join(BASE, "data", "stats.json")
H5 = os.path.join(BASE, "data", "bouts.h5")
FIGDIR = os.path.join(BASE, "reports", "figures")
os.makedirs(FIGDIR, exist_ok=True)
STEM = os.path.join(FIGDIR, "F1_bout_definition")

# ---- load saved objects (read only) ----------------------------------------
with open(STATS, "r", encoding="utf-8") as fh:
    S = json.load(fh)
dA = S["deliverable_A"]
rar = dA["rarity"]
sel = dA["selectivity"]

median_rate = rar["pooled_median_bout_rate_per_s"]
frac_ge1 = rar["frac_trials_ge1_bout"]
frac_0 = rar["frac_trials_0_bout"]
v1_rate = rar["v1_baseline_rate_per_s"]
fold_rarer = rar["fold_rarer_than_v1"]
cnt_min = dA["rarity"]["count_distribution"]["min"]
cnt_med = dA["rarity"]["count_distribution"]["median"]
cnt_max = dA["rarity"]["count_distribution"]["max"]

med_vcom_b = sel["median_v_com_bouts"]
med_vcom_i = sel["median_v_com_incidental"]
med_pom_b = sel["median_peak_omega_bouts_deg_s"]
med_pom_i = sel["median_peak_omega_incidental_deg_s"]
med_exc_b = sel["median_excursion_bouts_deg"]

n_bouts = dA["n_bouts_pooled"]
n_inc = dA["n_incidental_pooled"]
n_trials_contrib = dA["n_contributing_trials"]
n_pooled_trials = S["meta"]["n_pooled_trials"]

with h5py.File(H5, "r") as f:
    fc = f["figure_curves"]
    rate = fc["F1_rate"][:]              # per-trial bout rate, n=105
    bout_vcom = fc["F1_bout_vcom"][:]    # pooled per-event, n=111
    inc_vcom = fc["F1_inc_vcom"][:]      # pooled per-event, n=9061
    bout_pom = fc["F1_bout_pom"][:]
    inc_pom = fc["F1_inc_pom"][:]

n_rate = rate.size

# ---------------------------------------------------------------------------
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "figure.dpi": 200})
fig = plt.figure(figsize=(11, 4.6))
gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.0, 1.0], wspace=0.42)

C_BOUT = "#1f6feb"
C_INC = "#d1495b"

# ===== Panel A: per-trial bout-rate distribution (log-x) ====================
axA = fig.add_subplot(gs[0, 0])
pos = rate[rate > 0]
# log-spaced bins spanning positive per-trial rates up to well past v1
lo = max(pos.min(), 1e-4)
bins = np.logspace(np.log10(lo * 0.8), np.log10(max(v1_rate * 1.3, pos.max())), 26)
axA.hist(pos, bins=bins, color=C_BOUT, alpha=0.85, edgecolor="white", linewidth=0.4,
         label=f"per-trial bout rate (n={n_rate}; {(rate==0).sum()} trials at 0)")
axA.axvline(median_rate, color="black", lw=1.6, ls="-")
axA.axvline(v1_rate, color=C_INC, lw=2.0, ls="--")
axA.set_xscale("log")
axA.set_xlabel("per-trial bout rate  (bouts / s, log scale)")
axA.set_ylabel("number of trials")
axA.set_title("A  Rarity: bout rate vs v1 detector")
ymax = axA.get_ylim()[1]
axA.text(median_rate, ymax * 0.97, f" pooled median\n {median_rate:.4f}/s",
         color="black", va="top", ha="left", fontsize=8)
axA.text(v1_rate, ymax * 0.55, f"v1 detector\n{v1_rate:.1f}/s\n({fold_rarer:.0f}x rarer)",
         color=C_INC, va="top", ha="right", fontsize=8, fontweight="bold")
axA.text(0.02, 0.02,
         f"{frac_ge1*100:.1f}% of trials >=1 bout\n{frac_0*100:.1f}% have 0 bouts\n"
         f"count/trial: min {cnt_min}, median {cnt_med:.0f}, max {cnt_max}",
         transform=axA.transAxes, va="bottom", ha="left", fontsize=7.6,
         bbox=dict(boxstyle="round,pad=0.35", fc="#f0f4ff", ec="#9db8e8", lw=0.6))
axA.legend(loc="upper left", fontsize=6.8, framealpha=0.9)

# ===== helper: strip + box compare ==========================================
def strip_box(ax, data_b, data_i, med_b, med_i, ylabel, title, logy=True):
    groups = [data_b, data_i]
    cols = [C_BOUT, C_INC]
    labels = [f"bouts\n(n={n_bouts})", f"incidental\n(n={n_inc})"]
    rng = np.random.default_rng(1234)
    for i, (d, c) in enumerate(zip(groups, cols)):
        dd = d.copy()
        if logy:
            dd = dd[dd > 0]
        x = np.full(dd.shape, i + 1.0) + rng.uniform(-0.16, 0.16, dd.shape)
        ax.scatter(x, dd, s=6, color=c, alpha=0.30 if i == 1 else 0.6,
                   edgecolors="none", zorder=2, rasterized=(i == 1))
    bp = ax.boxplot(groups, positions=[1, 2], widths=0.55, showfliers=False,
                    patch_artist=True, zorder=3,
                    medianprops=dict(color="black", lw=1.8),
                    boxprops=dict(facecolor="none", edgecolor="black", lw=1.0),
                    whiskerprops=dict(color="black", lw=0.9),
                    capprops=dict(color="black", lw=0.9))
    # annotate authoritative medians (from stats.json deliverable_A.selectivity)
    ax.annotate(f"med {med_b:.2f}", xy=(1, med_b), xytext=(1.32, med_b),
                fontsize=7.6, color=C_BOUT, va="center", fontweight="bold")
    ax.annotate(f"med {med_i:.1f}", xy=(2, med_i), xytext=(2.32, med_i),
                fontsize=7.6, color=C_INC, va="center", fontweight="bold")
    if logy:
        ax.set_yscale("log")
    ax.set_xticks([1, 2])
    ax.set_xticklabels(labels)
    ax.set_xlim(0.5, 2.85)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

# ===== Panel B: COM speed (definitional) ====================================
axB = fig.add_subplot(gs[0, 1])
strip_box(axB, bout_vcom, inc_vcom, med_vcom_b, med_vcom_i,
          "COM speed during event  (px/s, log)",
          "B  COM speed (DEFINITIONAL)")
axB.text(0.5, 1.005, "low COM = pause condition (not a finding)",
         transform=axB.transAxes, ha="center", va="bottom", fontsize=6.8,
         color="#555555", style="italic")

# ===== Panel C: head peak omega =============================================
axC = fig.add_subplot(gs[0, 2])
strip_box(axC, bout_pom, inc_pom, med_pom_b, med_pom_i,
          "head peak angular speed  (deg/s, log)",
          "C  Head cast: peak omega")
axC.text(0.5, 1.005, f"bouts > incidental; excursion ~{med_exc_b:.0f} deg",
         transform=axC.transAxes, ha="center", va="bottom", fontsize=6.8,
         color="#555555", style="italic")

fig.suptitle(
    f"F1  Sampling-bout definition & selectivity  "
    f"(pooled Loc1-6, n={n_pooled_trials} trials; {n_trials_contrib} contributing; "
    f"{n_bouts} bouts vs {n_inc} incidental)",
    fontsize=10, y=1.02)

for ext in ("png", "pdf"):
    fig.savefig(f"{STEM}.{ext}", dpi=200, bbox_inches="tight")
plt.close(fig)

# ---- .txt sidecar: sources + numbers ---------------------------------------
lines = []
lines.append("F1_bout_definition -- sources & injected numbers")
lines.append("=" * 64)
lines.append("Generated by: code/make_F1.py  (Deliverable A figure-builder)")
lines.append("Sources (read-only, no science recomputed):")
lines.append("  - data/stats.json  (deliverable_A: rarity, selectivity; meta)")
lines.append("  - data/bouts.h5    (figure_curves/F1_rate, F1_bout_vcom, F1_inc_vcom,")
lines.append("                      F1_bout_pom, F1_inc_pom)")
lines.append("")
lines.append("PANEL A -- per-trial bout-rate distribution (rarity)")
lines.append(f"  plotted array        : figure_curves/F1_rate  (per-trial bout_rate, n={n_rate})")
lines.append(f"  pooled median rate   : {median_rate:.10g} /s   [stats.json rarity]")
lines.append(f"  v1 detector ref line : {v1_rate} /s            [stats.json rarity]")
lines.append(f"  fold rarer than v1   : {fold_rarer:.6g}x        [stats.json rarity]")
lines.append(f"  frac trials >=1 bout : {frac_ge1:.10g}  ({frac_ge1*100:.2f}%)")
lines.append(f"  frac trials 0 bouts  : {frac_0:.10g}  ({frac_0*100:.2f}%)")
lines.append(f"  count/trial min/med/max : {cnt_min} / {cnt_med:.0f} / {cnt_max}")
lines.append("")
lines.append("PANEL B -- COM speed, bouts vs incidental (low-COM is DEFINITIONAL)")
lines.append(f"  plotted clouds       : F1_bout_vcom (n={bout_vcom.size}), F1_inc_vcom (n={inc_vcom.size})")
lines.append(f"  annotated median bouts      : {med_vcom_b:.10g} px/s   [stats.json selectivity]")
lines.append(f"  annotated median incidental : {med_vcom_i:.10g} px/s   [stats.json selectivity]")
lines.append("")
lines.append("PANEL C -- head peak angular speed, bouts vs incidental")
lines.append(f"  plotted clouds       : F1_bout_pom (n={bout_pom.size}), F1_inc_pom (n={inc_pom.size})")
lines.append(f"  annotated median bouts      : {med_pom_b:.10g} deg/s  [stats.json selectivity]")
lines.append(f"  annotated median incidental : {med_pom_i:.10g} deg/s  [stats.json selectivity]")
lines.append(f"  median excursion bouts      : {med_exc_b:.10g} deg    [stats.json selectivity]")
lines.append("")
lines.append("NOTE: Panel B/C annotated medians are the authoritative aggregate medians in")
lines.append("      stats.json deliverable_A.selectivity. Plotted point clouds are the pooled")
lines.append("      per-event arrays saved in figure_curves (per-event medians differ slightly).")
lines.append("")
lines.append("Counts: n_bouts_pooled=%d, n_incidental_pooled=%d, n_contributing_trials=%d, n_pooled_trials=%d"
             % (n_bouts, n_inc, n_trials_contrib, n_pooled_trials))
with open(f"{STEM}.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

print("F1 written:")
for ext in ("png", "pdf", "txt"):
    p = f"{STEM}.{ext}"
    print(f"  {p}  ({os.path.getsize(p)} bytes)")
