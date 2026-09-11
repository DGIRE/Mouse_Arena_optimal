"""Build Figure F2 (peri-bout odor + kinematics, onset-aligned) STRICTLY from
saved result objects (data/bouts.h5 figure_curves + data/stats.json). No science
is recomputed here. Shared between H1 and H2 reports."""
import json
import os

import h5py
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
H5 = os.path.join(BASE, "data", "bouts.h5")
STATS = os.path.join(BASE, "data", "stats.json")
OUTDIR = os.path.join(BASE, "reports", "figures")
os.makedirs(OUTDIR, exist_ok=True)
STEM = os.path.join(OUTDIR, "F2_peri_bout")

PRE_ON = (-0.75, -0.25)  # H2 pre-onset window (shade)


def load_curve(g, name):
    grp = g[name]
    return {
        "grid": grp["grid"][:].astype(float),
        "mean": grp["mean"][:].astype(float),
        "lo": grp["lo"][:].astype(float),
        "hi": grp["hi"][:].astype(float),
    }


with h5py.File(H5, "r") as f:
    fc = f["figure_curves"]
    eth = load_curve(fc, "F2A_eth")
    null = load_curve(fc, "F2A_null")
    inc = load_curve(fc, "F2A_inc")
    vcom = load_curve(fc, "F2B_vcom")
    omega = load_curve(fc, "F2B_omega")

with open(STATS) as fh:
    st = json.load(fh)

fcm = st["figure_curves_meta"]
n_bouts_eth = int(fcm["F2A_eth"]["n_events"])
n_trials_eth = int(fcm["F2A_eth"]["n_trials"])
n_trials_null = int(fcm["F2A_null_trials"])
n_inc = int(fcm["F2A_incidental"]["n_events"])
n_inc_trials = int(fcm["F2A_incidental"]["n_trials"])

# ---- figure ----
fig, (axA, axB) = plt.subplots(
    2, 1, figsize=(7.2, 7.6), sharex=True, gridspec_kw={"height_ratios": [1, 1]}
)

# ============ Panel A: odor ============
C_ETH, C_NULL, C_INC = "#1f77b4", "#7f7f7f", "#d62728"

# pre-onset shade (H2 window)
axA.axvspan(PRE_ON[0], PRE_ON[1], color="#f0e442", alpha=0.30, zorder=0,
            label="pre-onset window [-0.75,-0.25] s")

# matched random-time null
axA.fill_between(null["grid"], null["lo"], null["hi"], color=C_NULL, alpha=0.20, zorder=1)
axA.plot(null["grid"], null["mean"], color=C_NULL, lw=1.8, ls="--",
         label="matched random-time null (95% CI)", zorder=3)

# incidental
axA.plot(inc["grid"], inc["mean"], color=C_INC, lw=1.6, ls=":",
         label="incidental events", zorder=3)

# peri-bout ethanol (headline)
axA.fill_between(eth["grid"], eth["lo"], eth["hi"], color=C_ETH, alpha=0.25, zorder=2)
axA.plot(eth["grid"], eth["mean"], color=C_ETH, lw=2.4,
         label="peri-bout ethanol (95% CI)", zorder=4)

axA.axvline(0.0, color="k", lw=1.0, ls="-", alpha=0.7, zorder=5)
axA.set_ylabel("baseline-subtracted ethanol (a.u.)")
axA.set_title("A  Peri-bout odor (onset-aligned)", loc="left", fontweight="bold")
axA.legend(loc="upper left", fontsize=8, framealpha=0.9)
axA.annotate(
    "H1 NOT supported: peri-bout eth (median {:.4f}) < null (median {:.4f})".format(
        st["H1"]["lead_magnitude"]["median_peri_bout_eth"],
        st["H1"]["lead_magnitude"]["median_null_eth"],
    ),
    xy=(0.5, 0.03), xycoords="axes fraction", ha="center", va="bottom", fontsize=7.5,
    color="#333333",
)

# ============ Panel B: kinematics (twin y) ============
C_V, C_W = "#2ca02c", "#9467bd"
axB.fill_between(vcom["grid"], vcom["lo"], vcom["hi"], color=C_V, alpha=0.20)
lnV, = axB.plot(vcom["grid"], vcom["mean"], color=C_V, lw=2.2, label="COM speed (px/s)")
axB.set_ylabel("COM speed (px/s)", color=C_V)
axB.tick_params(axis="y", labelcolor=C_V)
axB.axvline(0.0, color="k", lw=1.0, ls="-", alpha=0.7)
axB.axvspan(PRE_ON[0], PRE_ON[1], color="#f0e442", alpha=0.30, zorder=0)

axBt = axB.twinx()
axBt.fill_between(omega["grid"], omega["lo"], omega["hi"], color=C_W, alpha=0.15)
lnW, = axBt.plot(omega["grid"], omega["mean"], color=C_W, lw=2.2, ls="--",
                 label="head angular speed omega (deg/s)")
axBt.set_ylabel("head angular speed omega (deg/s)", color=C_W)
axBt.tick_params(axis="y", labelcolor=C_W)

axB.set_xlabel("time to bout onset (s)")
axB.set_title("B  Peri-bout kinematics (onset-aligned): stop + cast", loc="left",
              fontweight="bold")
axB.legend(handles=[lnV, lnW], loc="upper right", fontsize=8, framealpha=0.9)
axB.set_xlim(-1.0, 1.0)

# n annotation
fig.text(0.99, 0.005,
         "n(bouts)={}  n(trials contributing)={}".format(n_bouts_eth, n_trials_eth),
         ha="right", va="bottom", fontsize=8, color="#333333")

fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(STEM + ".png", dpi=200, bbox_inches="tight")
fig.savefig(STEM + ".pdf", bbox_inches="tight")
plt.close(fig)

# ---- .txt sidecar ----
lines = []
lines.append("F2 - peri-bout odor & kinematics (onset-aligned)")
lines.append("Built by code/build_F2.py from saved objects (no recompute).")
lines.append("Sources:")
lines.append("  curves : data/bouts.h5  /figure_curves/{F2A_eth,F2A_null,F2A_inc,F2B_vcom,F2B_omega}")
lines.append("  numbers: data/stats.json  (H1 block, figure_curves_meta)")
lines.append("  seed=1234; trial-level inference; grid -1..+1 s, 50 ms.")
lines.append("")
lines.append("Panel A - baseline-subtracted ethanol (a.u.) vs time-to-onset (s):")
lines.append("  n(bouts)={}  n(trials)={}".format(n_bouts_eth, n_trials_eth))
lines.append("  null n(trials)={}   incidental n(events)={} n(trials)={}".format(
    n_trials_null, n_inc, n_inc_trials))
lines.append("  H1 median peri-bout eth = {:.6f}".format(
    st["H1"]["lead_magnitude"]["median_peri_bout_eth"]))
lines.append("  H1 median matched-null eth = {:.6f}".format(
    st["H1"]["lead_magnitude"]["median_null_eth"]))
lines.append("  delta (obs - null) = {:.6f}".format(
    st["H1"]["lead_magnitude"]["delta_median_obs_minus_null"]))
lines.append("  Wilcoxon bout>null p_greater = {:.6f} (stat={}, n={})".format(
    st["H1"]["a_bout_vs_null"]["p_greater"],
    st["H1"]["a_bout_vs_null"]["wilcoxon_stat"],
    st["H1"]["a_bout_vs_null"]["n_trials"]))
lines.append("  Wilcoxon bout>incidental p_greater = {:.6f} (stat={}, n={})".format(
    st["H1"]["b_bout_vs_incidental"]["p_greater"],
    st["H1"]["b_bout_vs_incidental"]["wilcoxon_stat"],
    st["H1"]["b_bout_vs_incidental"]["n_trials"]))
lines.append("  frac bouts peri-odor>0.01 = {:.4f}; above_floor={}".format(
    st["H1"]["amplitude_check"]["frac_bouts_peri_gt_0p01"],
    st["H1"]["amplitude_check"]["above_floor"]))
lines.append("  pre-onset shaded window (H2) = [{:.2f},{:.2f}] s".format(*PRE_ON))
lines.append("")


def row(tag, c):
    return "  {:10s} grid[0]={:+.2f} grid[-1]={:+.2f} mean[min,max]=[{:.4f},{:.4f}] mean@t=0={:.4f}".format(
        tag, c["grid"][0], c["grid"][-1], float(np.nanmin(c["mean"])),
        float(np.nanmax(c["mean"])), float(c["mean"][np.argmin(np.abs(c["grid"]))]))


lines.append("Curve summaries:")
lines.append(row("eth", eth))
lines.append(row("null", null))
lines.append(row("incidental", inc))
lines.append(row("v_com", vcom))
lines.append(row("omega", omega))
lines.append("")
lines.append("Panel B - COM speed (px/s, left) & head angular speed omega (deg/s, right).")

with open(STEM + ".txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

print("WROTE:", STEM + ".png / .pdf / .txt")
for ext in (".png", ".pdf", ".txt"):
    print("  ", ext, os.path.getsize(STEM + ext), "bytes")
