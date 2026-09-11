"""F2 - Most/least tortuous example paths (H1). Plots ONLY from saved objects."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import h5py

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories"
DATA = os.path.join(BASE, "data")
FIGDIR = os.path.join(BASE, "reports", "figures")
os.makedirs(FIGDIR, exist_ok=True)

metrics = json.load(open(os.path.join(DATA, "trajectory_metrics.json")))
h5path = os.path.join(DATA, "trajectory_metrics.h5")

trials = metrics["trials"]
pooled = [t for t in trials if t["in_pooled"]]
pooled_sorted = sorted(pooled, key=lambda t: t["tortuosity"])
lowest3 = pooled_sorted[:3]                 # least tortuous
highest3 = list(reversed(pooled_sorted[-3:]))  # most tortuous (descending)

ARENA = [0.0, 580.0, 0.0, 280.0]  # root attr arena_extent
NROW = 3

with h5py.File(h5path, "r") as f:
    THRESH = float(f.attrs["threshold"])
    K = int(f.attrs["k"])
    SEED = int(f.attrs["seed"])
    g = f["trials"]

    # Build a per-cell nested gridspec: 3 rows x 2 cols, each cell = 2 stacked axes
    fig = plt.figure(figsize=(13, 15))
    outer = GridSpec(NROW, 2, figure=fig, hspace=0.42, wspace=0.22)

    # global ethd color scale across the 6 example contact sets (jet), for comparability
    contact_vals = []
    picks = []
    for col, group in enumerate((highest3, lowest3)):
        for row, t in enumerate(group):
            grp = g["%03d" % t["trial_index"]]
            oi = grp["onset_idx"][:].astype(int)
            ethd = grp["ethd_h"][:]
            cv = ethd[oi] if oi.size else np.array([])
            contact_vals.append(cv)
            picks.append((col, row, t))
    all_cv = np.concatenate([c for c in contact_vals if c.size]) if any(c.size for c in contact_vals) else np.array([0, 1])
    vmin, vmax = float(np.min(all_cv)), float(np.max(all_cv))
    if vmin == vmax:
        vmax = vmin + 1e-9

    sidecar_rows = []
    last_scatter = None
    for (col, row, t) in picks:
        grp = g["%03d" % t["trial_index"]]
        body = grp["body_clean"][:]
        head = grp["head_clean"][:]
        ethd = grp["ethd_h"][:]
        head_t = grp["head_t"][:]
        oi = grp["onset_idx"][:].astype(int)
        ot = grp["onset_time"][:]

        # nested gridspec for this cell: top track (taller) + bottom timeseries
        inner = outer[row, col].subgridspec(2, 1, height_ratios=[2.3, 1.0], hspace=0.32)
        ax_top = fig.add_subplot(inner[0])
        ax_bot = fig.add_subplot(inner[1])

        # ---- top: trajectory ----
        vb = ~np.isnan(body[:, 0]) & ~np.isnan(body[:, 1])
        ax_top.plot(body[vb, 0], body[vb, 1], "-", color="0.55", lw=0.8, zorder=1)
        # endpoint = last valid body point (straight_line uses p_end)
        endp = body[vb][-1]
        ax_top.plot(endp[0], endp[1], "x", color="red", mew=2.5, ms=13, zorder=5)
        ax_top.plot(endp[0], endp[1], "x", color="white", mew=0.9, ms=13, zorder=6)
        # contacts: head_clean at onset_idx, colored by ethd_h at those onsets (jet)
        if oi.size:
            cpos = head[oi]
            cval = ethd[oi]
            vcm = ~np.isnan(cpos[:, 0])
            last_scatter = ax_top.scatter(cpos[vcm, 0], cpos[vcm, 1], c=cval[vcm],
                                          cmap="jet", vmin=vmin, vmax=vmax, s=30,
                                          edgecolor="k", linewidth=0.3, zorder=4)
        ax_top.set_xlim(ARENA[0], ARENA[1])
        ax_top.set_ylim(ARENA[2], ARENA[3])
        ax_top.set_aspect("equal")
        ax_top.set_xlabel("x (px)", fontsize=8)
        ax_top.set_ylabel("y (px)", fontsize=8)
        ax_top.tick_params(labelsize=7)
        ax_top.set_title(f"{t['file_name']}\ntortuosity = {t['tortuosity']:.2f}  |  "
                         f"n_enc = {t['n_encounters']}  |  {t['end_loc']}",
                         fontsize=7.5)

        # ---- bottom: ethd_h vs head_t + threshold + onset marks ----
        vt = ~np.isnan(ethd)
        ax_bot.plot(head_t[vt], ethd[vt], "-", color="steelblue", lw=0.6, zorder=1)
        ax_bot.axhline(THRESH, color="crimson", ls="--", lw=1.0, zorder=2,
                       label=f"threshold={THRESH:.2e}")
        for tt in ot:
            ax_bot.axvline(tt, color="green", ls=":", lw=0.7, alpha=0.7, zorder=1)
        ax_bot.set_xlabel("head clock time (s)", fontsize=8)
        ax_bot.set_ylabel("ethdeconv (a.u.)", fontsize=8)
        ax_bot.tick_params(labelsize=7)
        ax_bot.legend(fontsize=6, loc="upper right")

        sidecar_rows.append((
            "MOST" if col == 0 else "LEAST", t["trial_index"], t["end_loc"],
            t["n_encounters"], t["tortuosity"], t["file_name"]))

    # shared colorbar (jet) for ethd at contacts
    if last_scatter is not None:
        cax = fig.add_axes([0.93, 0.25, 0.015, 0.5])
        cb = fig.colorbar(last_scatter, cax=cax)
        cb.set_label("ethdeconv at contact onset (a.u.)", fontsize=9)
        cb.ax.tick_params(labelsize=7)

    fig.suptitle("F2 - Example pooled trials: most tortuous (left col) vs least tortuous (right col)\n"
                 "top = body track + jet ethanol contacts (red/white x = endpoint);  "
                 "bottom = ethdeconv time series (threshold + onsets)",
                 fontsize=11, y=0.995)

png = os.path.join(FIGDIR, "F2_example_paths.png")
pdf = os.path.join(FIGDIR, "F2_example_paths.pdf")
fig.savefig(png, dpi=200, bbox_inches="tight")
fig.savefig(pdf, bbox_inches="tight")
plt.close(fig)

txt = os.path.join(FIGDIR, "F2_example_paths.txt")
with open(txt, "w", encoding="utf-8") as fh:
    fh.write("F2 - Most/least tortuous example paths\n")
    fh.write("Source files:\n")
    fh.write("  data/trajectory_metrics.json  (per-trial tortuosity, n_encounters, in_pooled)\n")
    fh.write("  data/trajectory_metrics.h5    (/trials/<idx>: body_clean, head_clean, ethd_h,\n")
    fh.write("                                  head_t, onset_idx, onset_time; root threshold/k/seed)\n\n")
    fh.write(f"Root attrs drawn: threshold={THRESH}  k={K}  seed={SEED}\n")
    fh.write(f"Arena box (arena_extent): x[{ARENA[0]},{ARENA[1]}] y[{ARENA[2]},{ARENA[3]}]\n")
    fh.write(f"Contact colormap: jet, vmin={vmin}, vmax={vmax} (ethd_h at onset_idx, pooled across 6 examples)\n\n")
    fh.write("Examples (side, trial_index, end_loc, n_encounters, tortuosity, file_name):\n")
    for r in sidecar_rows:
        fh.write(f"  {r[0]:5s}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]:.4f}\t{r[5]}\n")

print("F2 written:", png, pdf, txt)
print("sizes:", os.path.getsize(png), os.path.getsize(pdf), os.path.getsize(txt))
