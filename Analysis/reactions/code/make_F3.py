"""Build Figure 3 (H3 illustrative example trial) STRICTLY from saved objects.

F3A: 2D COM (body_h) trajectory in arena box, colored by R(t); source endpoint marked (x).
F3B: stacked time series (baseline-subtracted ethanol, then R) on the head clock,
     with sweep-peak markers (sweep_times_R) in both panels.

Never recomputes science; reads sweeps.h5 (example trial), stats.json (identifiers),
odor_fields.h5 (source endpoint, read-only).
"""
import json
import os

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions"
STATS = os.path.join(BASE, "data", "stats.json")
SWEEPS = os.path.join(BASE, "data", "sweeps.h5")
ODOR = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5"
OUTDIR = os.path.join(BASE, "reports", "figures")
STEM = "F3_example_trajectory_and_timeseries"

ARENA_X = (0.0, 580.0)
ARENA_Y = (0.0, 280.0)

os.makedirs(OUTDIR, exist_ok=True)

# ---- read identifiers from stats.json (no recompute) ----
with open(STATS, "r", encoding="utf-8") as fh:
    stats = json.load(fh)
ex = stats["F3_example"]
trial_index = int(ex["trial_index"])
file_name = ex["file_name"]
sweep_rate = float(ex["sweep_rate"])
sweep_count = int(ex["sweep_count"])
end_loc = ex["end_loc"]

# group key is zero-padded trial index
gkey = f"{trial_index:03d}"

# ---- read per-frame arrays for the example trial ----
with h5py.File(SWEEPS, "r") as f:
    g = f["trials"][gkey]
    assert g.attrs["file_name"] == file_name, (
        f"file_name mismatch: {g.attrs['file_name']!r} vs {file_name!r}"
    )
    head_t = g["head_t"][:]
    body_h = g["body_h"][:]
    R = g["R"][:]
    eth_bs = g["eth_bs_h"][:]
    sweep_times_R = g["sweep_times_R"][:]

# ---- read source endpoint from odor field group (stored; read-only) ----
with h5py.File(ODOR, "r") as f:
    endpoint = f[end_loc]["endpoint"][:]
endpoint_x, endpoint_y = float(endpoint[0]), float(endpoint[1])

t0 = float(head_t[0])
t = head_t - t0            # seconds from trial start
st = sweep_times_R - t0    # sweep peak times on same clock

# interpolate R and eth at sweep times for marker y-placement
R_at = np.interp(sweep_times_R, head_t, R)
eth_at = np.interp(sweep_times_R, head_t, eth_bs)

# =====================  FIGURE  =====================
fig = plt.figure(figsize=(8.5, 8.5))
gs = fig.add_gridspec(3, 1, height_ratios=[2.0, 1.0, 1.0], hspace=0.32)

# ---------- F3A: trajectory colored by R ----------
axA = fig.add_subplot(gs[0, 0])
pts = body_h.reshape(-1, 1, 2)
segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
# color each segment by mean R of its two endpoints
seg_R = 0.5 * (R[:-1] + R[1:])
# clip color scale to a robust range so a few large R don't wash it out
vmax = float(np.nanpercentile(R, 99))
vmin = float(np.nanmin(R))
lc = LineCollection(segs, cmap="viridis", norm=plt.Normalize(vmin=vmin, vmax=vmax))
lc.set_array(seg_R)
lc.set_linewidth(1.2)
axA.add_collection(lc)
axA.plot(endpoint_x, endpoint_y, "x", color="red", markersize=14,
         markeredgewidth=3, label="odor source", zorder=5)
axA.set_xlim(*ARENA_X)
axA.set_ylim(*ARENA_Y)
axA.set_aspect("equal", adjustable="box")
axA.set_xlabel("x (px)")
axA.set_ylabel("y (px)")
axA.legend(loc="upper left", fontsize=8, framealpha=0.85)
cbar = fig.colorbar(lc, ax=axA, fraction=0.030, pad=0.02)
cbar.set_label(r"R = v_nose/v_com")
axA.set_title(
    f"{file_name}\nsweep rate = {sweep_rate:.3f}/s   |   sweep count = {sweep_count}",
    fontsize=9,
)

# ---------- F3B (i): baseline-subtracted ethanol ----------
axB1 = fig.add_subplot(gs[1, 0])
axB1.plot(t, eth_bs, color="tab:green", linewidth=0.7)
axB1.axhline(0.0, color="0.6", linewidth=0.6, linestyle="--")
# sweep-peak markers (downward arrowheads above the trace)
y_top = np.nanmax(eth_bs)
mark_y = y_top + 0.08 * (y_top - np.nanmin(eth_bs) + 1e-9)
axB1.plot(st, np.full_like(st, mark_y), marker="v", linestyle="none",
          color="black", markersize=4,
          label=f"sweep peaks (n={len(st)})")
axB1.set_ylabel("eth_bs (a.u.)")
axB1.legend(loc="upper right", fontsize=8, framealpha=0.85)
axB1.set_title("Baseline-subtracted ethanol (head clock)", fontsize=9)

# ---------- F3B (ii): R(t) ----------
axB2 = fig.add_subplot(gs[2, 0], sharex=axB1)
axB2.plot(t, R, color="tab:blue", linewidth=0.7)
r_top = np.nanmax(R)
mark_yR = r_top + 0.06 * (r_top - np.nanmin(R) + 1e-9)
axB2.plot(st, np.full_like(st, mark_yR), marker="v", linestyle="none",
          color="black", markersize=4)
# also mark the detected peaks on the trace itself
axB2.plot(st, R_at, marker=".", linestyle="none", color="red",
          markersize=3, alpha=0.6)
axB2.set_ylabel(r"R = v_nose/v_com")
axB2.set_xlabel("time (s, head clock)")
axB2.set_title("R(t) with detected sweep peaks", fontsize=9)

fig.suptitle(
    "F3 — Example trial (highest sweep rate): trajectory + peri-sweep time series "
    "(illustrative for H3)",
    fontsize=10, y=0.995,
)

png = os.path.join(OUTDIR, STEM + ".png")
pdf = os.path.join(OUTDIR, STEM + ".pdf")
fig.savefig(png, dpi=200, bbox_inches="tight")
fig.savefig(pdf, bbox_inches="tight")
plt.close(fig)

# ---------- .txt sidecar (source + numbers) ----------
txt = os.path.join(OUTDIR, STEM + ".txt")
lines = []
lines.append("F3 — Example trajectory + peri-sweep time series (H3, illustrative)")
lines.append("=" * 70)
lines.append("SOURCE OBJECTS (read-only; no recompute):")
lines.append(f"  stats.json        : {STATS}")
lines.append(f"  sweeps.h5         : {SWEEPS}  (group /trials/{gkey})")
lines.append(f"  odor_fields.h5    : {ODOR}  (group {end_loc}/endpoint)")
lines.append("")
lines.append("EXAMPLE TRIAL (stats.json F3_example):")
lines.append(f"  trial_index       : {trial_index}  (h5 group key /trials/{gkey})")
lines.append(f"  file_name         : {file_name}")
lines.append(f"  end_loc           : {end_loc}")
lines.append(f"  sweep_rate (/s)   : {sweep_rate:.6f}")
lines.append(f"  sweep_count       : {sweep_count}")
lines.append("")
lines.append("PER-FRAME ARRAYS (from /trials/%s):" % gkey)
lines.append(f"  n_frames          : {len(head_t)}")
lines.append(f"  head_t range (s)  : [{head_t.min():.4f}, {head_t.max():.4f}]  "
             f"(duration {head_t.max()-head_t.min():.4f})")
lines.append(f"  body_h x range px : [{np.nanmin(body_h[:,0]):.3f}, "
             f"{np.nanmax(body_h[:,0]):.3f}]")
lines.append(f"  body_h y range px : [{np.nanmin(body_h[:,1]):.3f}, "
             f"{np.nanmax(body_h[:,1]):.3f}]")
lines.append(f"  R range           : [{np.nanmin(R):.4f}, {np.nanmax(R):.4f}]  "
             f"(color vmin={vmin:.4f}, vmax=99pct {vmax:.4f})")
lines.append(f"  eth_bs range (a.u.): [{np.nanmin(eth_bs):.5f}, "
             f"{np.nanmax(eth_bs):.5f}]")
lines.append(f"  n sweep peaks     : {len(sweep_times_R)}  "
             f"(sweep_times_R; same events in both F3B panels)")
lines.append(f"  sweep peaks range : [{st.min():.4f}, {st.max():.4f}] s")
lines.append("")
lines.append("ARENA BOX (equal aspect):")
lines.append(f"  x: [{ARENA_X[0]}, {ARENA_X[1]}]   y: [{ARENA_Y[0]}, {ARENA_Y[1]}]")
lines.append(f"  source endpoint (x): ({endpoint_x:.1f}, {endpoint_y:.1f}) px")
lines.append("")
lines.append("PANELS:")
lines.append("  F3A: body_h (COM) trajectory, line colored by R(t); "
             "red x = odor source endpoint.")
lines.append("  F3B(i): baseline-subtracted ethanol (a.u.) vs time; "
             "black v = sweep-peak times.")
lines.append("  F3B(ii): R(t) vs time; black v = sweep-peak times; "
             "red dots = R at peaks.")
lines.append("")
lines.append("NOTE: F3 is illustrative for H3. H3 is NOT supported (null): "
             "median f_sweep ~0.336 ~= f_occ ~0.349.")
with open(txt, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

print("WROTE:")
for p in (png, pdf, txt):
    print(f"  {p}  ({os.path.getsize(p)} bytes)")
