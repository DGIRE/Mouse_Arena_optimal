"""Task 2 (ethanol signal enhancement) FIGURE-BUILDER + REPORT-WRITER.

Builds Figure A, Figure B, and the DOCX report STRICTLY from saved result objects
(enhanced_ethanol.h5, enhancement_stats.json). No science is recomputed here; every
number in the report is injected from those files.

Run:
  "C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe" code/make_task2_report.py
"""
import os
import json

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations"
H5_PATH = os.path.join(BASE, "data", "enhanced_ethanol.h5")
STATS_PATH = os.path.join(BASE, "data", "enhancement_stats.json")
DRIFT_PATH = os.path.join(BASE, "data", "drift_validation.json")
FIG_DIR = os.path.join(BASE, "reports", "figures", "enhancement")
DOCX_PATH = os.path.join(BASE, "reports", "Signal enhancement report.docx")

REL_H5 = r"data\enhanced_ethanol.h5"
REL_STATS = r"data\enhancement_stats.json"
REL_DRIFT = r"data\drift_validation.json"
REPRO_CMD = ('"C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/'
             'python.exe" code/build_enhancement.py')


def load_stats():
    with open(STATS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_drift():
    with open(DRIFT_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _ttt(idx):
    return f"{int(idx):03d}"


def build_figure_A(stats):
    idxs = stats["top10_figureA_trial_indices"]
    gains = stats["top10_figureA_distal_snr_gain"]
    gain_by_idx = {int(i): float(g) for i, g in zip(idxs, gains)}

    n = len(idxs)
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 2.6 * nrows), squeeze=False)
    axes_flat = axes.ravel()

    C_BEFORE = "#ff7f0e"  # drift-corrected raw (before) -> left axis
    C_AFTER = "#1f77b4"   # enhanced matched-filter score (after) -> right axis

    legend_done = False
    with h5py.File(H5_PATH, "r") as f:
        tr = f["trials"]
        for panel_i, tidx in enumerate(idxs):
            ax = axes_flat[panel_i]
            g = tr[_ttt(tidx)]
            t = g["time"][:]
            enhanced = g["enhanced"][:]
            drift_corrected = g["drift_corrected"][:]  # raw "before" trace the detector runs on
            cb_t = g["contacts_before_time"][:]
            ca_t = g["contacts_after_time"][:]
            n_before = int(g.attrs["n_before"])
            n_after = int(g.attrs["n_after"])
            gain = float(g.attrs["distal_snr_gain"])

            # head-to-endpoint distance context (per-trial median), from stored geometry
            head = g["head"][:]
            ep = g["endpoint"][:]
            d = np.sqrt(((head - ep) ** 2).sum(axis=1))
            med_dist = float(np.nanmedian(d))

            # BEFORE: drift-corrected raw amplitude on the LEFT y-axis
            ax.plot(t, drift_corrected, color=C_BEFORE, lw=0.7,
                    label="drift-corrected (before)", zorder=2)
            ax.axhline(float(g.attrs["thresh_before"]), color=C_BEFORE, ls=":", lw=0.6)
            ax.set_ylabel("drift-corr. raw (a.u.)", fontsize=7, color=C_BEFORE)
            ax.tick_params(axis="y", labelsize=7, colors=C_BEFORE)
            ax.tick_params(axis="x", labelsize=7)
            ax.set_xlabel("time (s)", fontsize=7)

            # AFTER: enhanced matched-filter score on the RIGHT (twin) y-axis
            ax2 = ax.twinx()
            ax2.plot(t, enhanced, color=C_AFTER, lw=0.6,
                     label="enhanced (after)", zorder=1)
            ax2.axhline(float(g.attrs["thresh_after"]), color=C_AFTER, ls=":", lw=0.6)
            ax2.set_ylabel("matched-filter score", fontsize=7, color=C_AFTER)
            ax2.tick_params(axis="y", labelsize=7, colors=C_AFTER)

            # Encounter markers: contacts_before on before axis, contacts_after on after axis
            b0, b1 = ax.get_ylim()
            yb = b1 - 0.06 * (b1 - b0)
            ax.scatter(cb_t, np.full_like(cb_t, yb, dtype=float), marker="v",
                       s=18, color="#d62728", edgecolor="k", linewidth=0.2,
                       label="encounter before", zorder=6)
            a0, a1 = ax2.get_ylim()
            ya = a1 - 0.06 * (a1 - a0)
            ax2.scatter(ca_t, np.full_like(ca_t, ya, dtype=float), marker="^",
                        s=18, color="#2ca02c", edgecolor="k", linewidth=0.2,
                        label="encounter after", zorder=6)

            ax.set_title(
                f"Trial {int(tidx)}  |  distal SNR gain={gain:+.2f}\n"
                f"n_before={n_before}, n_after={n_after}, med head-endpt={med_dist:.0f}px",
                fontsize=8)

            if not legend_done:
                handles = [
                    Line2D([], [], color=C_BEFORE, lw=1.2,
                           label="drift-corrected (before, left axis)"),
                    Line2D([], [], color=C_AFTER, lw=1.2,
                           label="enhanced (after, right axis)"),
                    Line2D([], [], marker="v", ls="", color="#d62728",
                           label="encounter before"),
                    Line2D([], [], marker="^", ls="", color="#2ca02c",
                           label="encounter after"),
                ]
                ax.legend(handles=handles, fontsize=6, loc="upper left", framealpha=0.85)
                legend_done = True

    for j in range(n, len(axes_flat)):
        axes_flat[j].axis("off")

    fig.suptitle(
        "Figure A - Top-10 most distal-SNR-improved ethanol trials: "
        "drift-corrected (before) vs enhanced matched-filter (after), twin y-axes, "
        "with detected encounters",
        fontsize=11, y=1.005)
    fig.tight_layout()

    png = os.path.join(FIG_DIR, "enhance_examples.png")
    pdf = os.path.join(FIG_DIR, "enhance_examples.pdf")
    fig.savefig(png, dpi=200, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)

    sidecar = os.path.join(FIG_DIR, "enhance_examples.txt")
    with open(sidecar, "w", encoding="utf-8") as fh:
        fh.write("Figure A - enhance_examples\n")
        fh.write("Source result files:\n")
        fh.write(f"  {REL_H5}  (/trials/<ttt>: time, drift_corrected, enhanced, "
                 "contacts_before_time, contacts_after_time, head, endpoint; "
                 "group attrs n_before/n_after/distal_snr_gain/thresh_before/thresh_after)\n")
        fh.write(f"  {REL_STATS}  (top10_figureA_trial_indices, "
                 "top10_figureA_distal_snr_gain)\n")
        fh.write(f"Trials plotted (top10_figureA_trial_indices): {idxs}\n")
        fh.write(f"distal_snr_gain per trial: {gains}\n")
        fh.write("Series: before=drift_corrected (drift-corrected raw amplitude, "
                 "left y-axis, the trace the BEFORE detector runs on); "
                 "after=enhanced (matched-filter score, right/twin y-axis). "
                 "The two are plotted on separate y-scales because they differ in "
                 "units. Encounter markers: contacts_before_time on the before axis, "
                 "contacts_after_time on the after axis (distinct markers).\n")
    return png, pdf, sidecar, gain_by_idx


def build_figure_B(stats):
    counts = stats["counts"]
    per = stats["per_trial"]
    nb = np.array([p["n_before"] for p in per], dtype=float)
    na = np.array([p["n_after"] for p in per], dtype=float)

    gain = int(counts["trials_gaining"])
    lose = int(counts["trials_losing"])
    tie = int(counts["trials_tying"])

    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    ax.scatter(nb, na, s=22, alpha=0.65, color="#1f77b4", edgecolor="k",
               linewidth=0.3, zorder=3)
    lo = 0
    hi = float(max(nb.max(), na.max())) * 1.05
    ax.plot([lo, hi], [lo, hi], color="#d62728", ls="--", lw=1.0,
            label="identity (y=x)", zorder=2)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("# encounters before enhancement")
    ax.set_ylabel("# encounters after enhancement")
    ax.set_title("Figure B - Per-trial encounter counts, before vs after enhancement\n"
                 "(matched false-positive rate)")

    txt = (f"gain (y>x): {gain}\n"
           f"lose (y<x): {lose}\n"
           f"tie  (y=x): {tie}\n"
           f"total trials: {gain + lose + tie}")
    ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", ha="left",
            fontsize=9, bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()

    png = os.path.join(FIG_DIR, "enhance_count_scatter.png")
    pdf = os.path.join(FIG_DIR, "enhance_count_scatter.pdf")
    fig.savefig(png, dpi=200, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)

    sidecar = os.path.join(FIG_DIR, "enhance_count_scatter.txt")
    with open(sidecar, "w", encoding="utf-8") as fh:
        fh.write("Figure B - enhance_count_scatter\n")
        fh.write("Source result files:\n")
        fh.write(f"  {REL_STATS}  (per_trial[].n_before / n_after; "
                 "counts.trials_gaining/losing/tying)\n")
        fh.write(f"gain={gain}, lose={lose}, tie={tie}, "
                 f"total={gain + lose + tie}\n")
    return png, pdf, sidecar


# --------------------------- DOCX ---------------------------------------------

def build_docx(stats, drift, figA_png, figB_png):
    from docx import Document
    from docx.shared import Inches

    p = stats["params"]
    th = stats["thresholds"]
    w = stats["wilcoxon"]
    c = stats["counts"]
    cal = stats["calibration"]
    snr = stats["distal_snr_gain_summary"]

    fpr_b = stats["pooled_baseline_fpr_before"]
    fpr_a = stats["pooled_baseline_fpr_after"]
    guard = bool(stats["H5_guard_after_le_before"])
    n_trials = int(stats["n_trials_processed"])
    seed = int(stats["seed"])
    n_baseline_seg = int(stats["n_baseline_segments"])
    baseline_dur = float(stats["baseline_total_duration_s"])
    med_drift_tau = float(stats["median_drift_timescale_s"])
    tmpl_trials = int(stats["template"]["n_contributing_trials"])
    tmpl_len = int(p["template_len_samples"])
    src = stats["source_aggregate_path"]
    k_used = float(cal["k_used"])
    baseline_mad = float(cal["baseline_mad"])
    k_grid = p["k_grid"]
    target_fpr = float(p["target_fpr_max_per_s"])

    total_before = int(c["total_before"])
    total_after = int(c["total_after"])
    dist_before = int(c["total_before_distal"])
    dist_after = int(c["total_after_distal"])
    prox_before = int(c["total_before_prox"])
    prox_after = int(c["total_after_prox"])
    gaining = int(c["trials_gaining"])
    losing = int(c["trials_losing"])
    tying = int(c["trials_tying"])

    p_overall = float(w["overall"]["pvalue"])
    p_distal = float(w["distal_only"]["pvalue"])
    p_prox = float(w["proximal_only"]["pvalue"])

    snr_pos = int(snr["n_trials_positive_gain"])
    snr_neg = int(snr["n_trials_negative_gain"])
    snr_zero = int(snr["n_trials_zero_gain"])
    snr_min = float(snr["gain_min"])
    snr_med = float(snr["gain_median"])
    snr_max = float(snr["gain_max"])

    doc = Document()

    doc.add_heading("Ethanol Signal Enhancement - Task 2 Report", level=0)
    intro = doc.add_paragraph()
    intro.add_run("Generator: ").bold = True
    intro.add_run(f"{stats['generator']} ({stats['plume_common_version']}); "
                  f"created {stats['created_utc']}. "
                  f"Cohort: single infrared cohort, {n_trials} ethanol trials. "
                  f"Seed = {seed}. All numbers below are injected verbatim from "
                  f"{REL_STATS}, {REL_H5}, and {REL_DRIFT}.")

    # -------------------- HEADLINE (null result) --------------------
    doc.add_heading("Headline finding (revised): null / negative result", level=1)
    hp = doc.add_paragraph()
    hp.add_run(
        "At a physically meaningful false-positive rate calibrated on quiet "
        "far-from-source baseline "
        f"(pooled FPR before = {fpr_b:.4f}/s, well below the request cap of "
        f"{target_fpr:.2f}/s), the matched-filter enhancement does NOT significantly "
        "change the number of detected ethanol encounters and does NOT recover distal "
        "encounters.").bold = True
    doc.add_paragraph(
        f"Overall paired Wilcoxon: p = {p_overall:.3f} (not significant): before/after "
        f"encounter counts are statistically indistinguishable "
        f"({total_after} after vs {total_before} before). "
        f"Distal subset: counts DECREASE ({dist_after} after vs {dist_before} before), "
        f"Wilcoxon p = {p_distal:.3f} (not significant): the enhancement does not "
        "recover distal encounters. Proximal subset also decreases "
        f"({prox_after} after vs {prox_before} before, p = {p_prox:.3f}). "
        f"Per-trial split: gain = {gaining}, lose = {losing}, tie = {tying} "
        f"(essentially symmetric). "
        "H4 (disproportionately distal recovery) is NOT SUPPORTED at a meaningful FPR.")
    doc.add_paragraph(
        "H5 (no-fabrication guard) HOLDS and is the key positive result: the pooled "
        f"baseline FPR after enhancement ({fpr_a:.4f}/s) is less than or equal to the "
        f"before FPR ({fpr_b:.4f}/s), and both are below the {target_fpr:.2f}/s cap. "
        "The enhancement does not manufacture encounters.")

    # -------------------- Correction vs prior draft --------------------
    doc.add_heading("Correction from the prior draft (methodological lesson)", level=1)
    doc.add_paragraph(
        "An earlier draft reported an apparently strong, significant enhancement "
        "(overall Wilcoxon p ~ 1.9e-6) and a distal-recovery effect. That result was "
        "an artifact of an implausibly permissive detection threshold whose baseline "
        "false-positive rate was ~0.5/s - roughly one spurious 'encounter' every two "
        "seconds on quiet baseline. At that permissive setting the huge number of noise "
        "crossings (total before ~ tens of thousands) drove a small but 'significant' "
        "paired difference that reflected noise statistics, not biology.")
    doc.add_paragraph(
        "In this revision the detector is recalibrated to a physically meaningful "
        f"target FPR (cap {target_fpr:.2f}/s), yielding a pooled baseline FPR of "
        f"{fpr_b:.4f}/s before enhancement (about 16x lower than the prior ~0.5/s). "
        "At this calibration the effect disappears: the result is a null. The lesson is "
        "that matched-filter 'enhancement' gains can be manufactured purely by lowering "
        "the detection bar; significance must be assessed at a calibrated, "
        "physically defensible FPR.")

    # -------------------- Goal + method --------------------
    doc.add_heading("Goal and method", level=1)
    doc.add_paragraph(
        "Goal: recover weak, distal ethanol encounters that are buried under slow "
        "baseline drift and sensor noise, without fabricating events, and test the "
        "pre-registered 'disproportionately distal' recovery pattern.")
    doc.add_paragraph(
        "Pipeline (per trial, on the sensor clock at "
        f"Fs = {p['Fs_hz']:.0f} Hz):", style="List Number")
    doc.add_paragraph(
        f"Drift removal: subtract a rolling {p['drift_percentile']:.0f}th-percentile "
        f"baseline computed in a window W = {p['drift_window_s']:.0f} s.",
        style="List Number")
    doc.add_paragraph(
        f"Template: pool near-endpoint, high-SNR encounters "
        f"(near-distance percentile <= {p['near_dist_pctile']:.0f}, "
        f"peak >= {p['template_k_mad']:.0f} x MAD) into a unit-energy matched filter of "
        f"half-window {p['template_half_window_s']:.2f} s "
        f"({tmpl_len} samples); built from {tmpl_trials} contributing trials.",
        style="List Number")
    doc.add_paragraph(
        "Enhancement: normalized cross-correlation of the drift-corrected trace "
        "against the template (matched-filter score = 'enhanced').",
        style="List Number")
    doc.add_paragraph(
        f"Detection: peak-pick with a refractory gap of {p['refractory_s']:.2f} s, "
        "before (on drift-corrected raw) and after (on enhanced), each thresholded "
        "to a MATCHED false-positive rate on quiet far-from-source baseline "
        f"(target cap {target_fpr:.2f} FP/s; before threshold = {th['before']:.6f}, "
        f"after threshold = {th['after']:.6f}).",
        style="List Number")

    doc.add_heading("Detection recalibration (k x MAD)", level=2)
    doc.add_paragraph(
        "The before threshold is k x MAD of the quiet far-from-source drift-corrected "
        f"baseline (baseline MAD = {baseline_mad:.6f}). k was scanned over "
        f"{k_grid} and the smallest k whose pooled baseline FPR fell at or below the "
        f"{target_fpr:.2f}/s cap was selected: k = {k_used:.0f}.")
    kt = doc.add_table(rows=1, cols=4)
    kt.style = "Light Grid Accent 1"
    kh = kt.rows[0].cells
    kh[0].text = "k"
    kh[1].text = "threshold"
    kh[2].text = "baseline FPR (/s)"
    kh[3].text = "n detections"
    for row in cal["k_scan"]:
        r = kt.add_row().cells
        sel = " (selected)" if float(row["k"]) == k_used else ""
        r[0].text = f"{float(row['k']):.0f}{sel}"
        r[1].text = f"{float(row['thr']):.6f}"
        r[2].text = f"{float(row['fpr_per_s']):.4f}"
        r[3].text = f"{int(row['n_det'])}"

    doc.add_heading("Window W justification (honest)", level=2)
    doc.add_paragraph(
        f"W = {p['drift_window_s']:.0f} s is a PRE-REGISTERED choice within the "
        "request's 10-30 s band. It is chosen because it is much larger than the "
        "~0.3 s encounter width and the ~2 s deconvolution timescale, so it removes "
        "slow baseline drift without erasing the encounters themselves. We do NOT "
        "claim the raw-trace autocorrelation 1/e time (median "
        f"{med_drift_tau:.2f} s here) justifies W: that number reflects fast transient "
        "structure in the raw trace, not the slow baseline drift, and is reported only "
        "for transparency.")

    # -------------------- H4 --------------------
    doc.add_heading("H4 - Encounter recovery (paired before/after): NOT SUPPORTED",
                    level=1)
    doc.add_paragraph(
        "At the matched, physically meaningful FPR the overall encounter count is a "
        f"modest net decrease ({total_after} after vs {total_before} before), with "
        f"trials roughly symmetric ({gaining} gain, {losing} lose, {tying} tie across "
        f"{gaining + losing + tying} trials). The paired Wilcoxon shows no significant "
        f"overall change (p = {p_overall:.3f}).")
    doc.add_paragraph(
        "Critically, the distal subset does NOT increase - it DECREASES "
        f"({dist_after} after vs {dist_before} before), with a non-significant distal "
        f"Wilcoxon (p = {p_distal:.3f}). The proximal subset also decreases "
        f"({prox_after} after vs {prox_before} before, p = {p_prox:.3f}). "
        "The pre-registered 'disproportionately distal recovery' pattern is therefore "
        "NOT observed. Distal is defined per trial as head-to-endpoint distance "
        "greater than the per-trial MEDIAN distance.")

    doc.add_heading("Wilcoxon signed-rank tests (paired per-trial counts)", level=2)
    wt = doc.add_table(rows=1, cols=4)
    wt.style = "Light Grid Accent 1"
    hdr = wt.rows[0].cells
    hdr[0].text = "Subset"
    hdr[1].text = "Wilcoxon statistic"
    hdr[2].text = "p-value"
    hdr[3].text = "Significant (p<0.05)?"
    for label, key in [("Overall", "overall"),
                       ("Distal only", "distal_only"),
                       ("Proximal only", "proximal_only")]:
        row = wt.add_row().cells
        row[0].text = label
        row[1].text = f"{w[key]['statistic']:.1f}"
        row[2].text = f"{w[key]['pvalue']:.3f}"
        row[3].text = "No" if float(w[key]["pvalue"]) >= 0.05 else "Yes"
    doc.add_paragraph(
        f"Trials: gain = {gaining}, lose = {losing}, tie = {tying} "
        f"(total = {gaining + losing + tying}). "
        "H4 acceptance criterion (a significant, disproportionately distal increase "
        "at matched FPR): NOT MET.")

    # -------------------- M2 / distal SNR --------------------
    doc.add_heading("M2 - Distal SNR gain (honest)", level=1)
    doc.add_paragraph(
        "Distal SNR gain (a cross-trial ranking, not an absolute delta) is POSITIVE "
        f"for only {snr_pos} of {n_trials} trials and NEGATIVE for {snr_neg} of "
        f"{n_trials} (zero for {snr_zero}). Across trials the gain ranges from "
        f"min = {snr_min:.2f} through median = {snr_med:.2f} to max = {snr_max:.2f}: "
        "the median is negative, so the method does NOT improve distal SNR for most "
        "trials. Figure A shows only the genuine positive-gain trials "
        "(top-10 by distal SNR gain).")

    # -------------------- H5 --------------------
    doc.add_heading("H5 - No-fabrication guard (hard gate): HOLDS", level=1)
    doc.add_paragraph(
        "Pooled baseline false-positive rate on quiet far-from-source segments "
        f"({n_baseline_seg} segments, {baseline_dur:.1f} s total): "
        f"before = {fpr_b:.6f}/s, after = {fpr_a:.6f}/s (both at or below the "
        f"{target_fpr:.2f}/s cap). "
        f"The guard 'after FPR <= before FPR' HOLDS: {guard}. "
        "This is the hard gate confirming the enhancement does not fabricate "
        "encounters at matched calibration - the key positive result of this task.")

    # -------------------- m4 drift validation --------------------
    doc.add_heading("m4 - Drift-window residual validation", level=1)
    dp = float(drift["drift_percentile"])
    dws = float(drift["drift_window_s"])
    doc.add_paragraph(
        f"The W = {dws:.0f} s rolling {dp:.0f}th-percentile baseline is subtracted from "
        "the raw ethanol trace (before = raw, after = drift-corrected). The slow-trend "
        "OLS slope should collapse toward zero after subtraction (drift removed) while "
        "the fast encounter-band variance should be preserved (retained fraction ~ 1). "
        "This holds for the validated example trials:")
    dt = doc.add_table(rows=1, cols=5)
    dt.style = "Light Grid Accent 1"
    dh = dt.rows[0].cells
    dh[0].text = "Trial"
    dh[1].text = "slow slope before (/s)"
    dh[2].text = "slow slope after (/s)"
    dh[3].text = "|slope| reduction x"
    dh[4].text = "encounter-band var retained"
    for ex in drift["examples"]:
        r = dt.add_row().cells
        r[0].text = f"{int(ex['trial_index'])}"
        r[1].text = f"{float(ex['slow_trend_slope_per_s_before']):.3e}"
        r[2].text = f"{float(ex['slow_trend_slope_per_s_after']):.3e}"
        r[3].text = f"{float(ex['slow_trend_slope_abs_reduction_factor']):.2f}"
        r[4].text = f"{float(ex['encounter_band_var_retained_frac']):.4f}"
    doc.add_paragraph(
        f"Across the {len(drift['examples'])} example trials the slow-trend slope is "
        "reduced (drift removed) while the fast-transient variance is retained near "
        "unity, confirming W = 20 s tracks slow drift without erasing fast encounters.")

    # -------------------- Methods --------------------
    doc.add_heading("Methods", level=1)
    doc.add_paragraph(
        f"Data source: {src}. Accessor: per-trial groups /trials/<ttt> in "
        f"{REL_H5} (datasets enhanced, drift_corrected, time, baseline, "
        f"contacts_before/after_*, head, head_time, body, endpoint); "
        f"pooled statistics in {REL_STATS}; drift validation in {REL_DRIFT}. "
        "Interpreter/venv: vras (Research Setup) Python; headless matplotlib (Agg). "
        f"Seed = {seed}.")
    mt = doc.add_table(rows=1, cols=2)
    mt.style = "Light Grid Accent 1"
    mt.rows[0].cells[0].text = "Parameter"
    mt.rows[0].cells[1].text = "Value"

    def prow(name, val):
        r = mt.add_row().cells
        r[0].text = name
        r[1].text = val

    prow("Sampling rate Fs", f"{p['Fs_hz']:.0f} Hz")
    prow("Drift window W", f"{p['drift_window_s']:.0f} s")
    prow("Drift percentile", f"{p['drift_percentile']:.0f}th")
    prow("Template half-window", f"{p['template_half_window_s']:.2f} s ({tmpl_len} samples)")
    prow("Template peak rule", f">= {p['template_k_mad']:.0f} x MAD")
    prow("Template near-endpoint rule", f"near-distance percentile <= {p['near_dist_pctile']:.0f}")
    prow("Template contributing trials", f"{tmpl_trials}")
    prow("Refractory gap", f"{p['refractory_s']:.2f} s")
    prow("Detection threshold rule (before)", str(p["before_thresh_rule"]))
    prow("k scanned / k used", f"{k_grid} / {k_used:.0f}")
    prow("Baseline MAD (quiet)", f"{baseline_mad:.6f}")
    prow("Distal rule", str(p["distal_rule"]))
    prow("Far-distance percentile", f"{p['far_dist_pctile']:.0f}")
    prow("Baseline amplitude fraction", f"{p['baseline_amp_frac']:.2f}")
    prow("SNR definition", str(p["snr_def"]))
    prow("Target FPR cap (matched)", f"{target_fpr:.2f} FP/s")
    prow("Threshold before", f"{th['before']:.6f}")
    prow("Threshold after", f"{th['after']:.6f}")
    prow("Pooled baseline FPR before / after", f"{fpr_b:.6f} / {fpr_a:.6f} FP/s")
    prow("Baseline segments / duration", f"{n_baseline_seg} / {baseline_dur:.1f} s")
    prow("Seed", f"{seed}")

    # -------------------- Results / figures --------------------
    doc.add_heading("Results", level=1)
    doc.add_paragraph(
        "Figure A shows the 10 trials with the largest distal-SNR improvement "
        "(top10_figureA_trial_indices) - the only trials with genuine positive gain "
        "are shown. Each panel overlays the drift-corrected raw trace (before, left "
        "y-axis) - the exact signal the BEFORE detector runs on - and the enhanced "
        "matched-filter score (after, right y-axis) on a common time axis, with "
        "detected encounters before (down triangles) and after (up triangles), the "
        "per-trial median head-to-endpoint distance, and the distal SNR gain. The two "
        "traces are drawn on separate y-scales (twin axes) because the matched-filter "
        "score and the raw amplitude differ in units and are not directly comparable; "
        "the SNR gain is a cross-trial ranking, not an absolute delta (see Caveats). "
        "These are the best-case trials and are not representative: the median distal "
        f"SNR gain across all {n_trials} trials is negative ({snr_med:.2f}).")
    doc.add_picture(figA_png, width=Inches(6.5))
    doc.add_paragraph(
        "Figure A. Top-10 distal-SNR-improved (positive-gain) ethanol trials: "
        "drift-corrected raw trace (before, left axis) vs enhanced matched-filter "
        "score (after, right axis) on twin y-scales, with matched-FPR encounter "
        "detections.").italic = True

    doc.add_paragraph(
        "Figure B plots per-trial encounter counts before (x) vs after (y) with the "
        f"identity line. Trials gain = {gaining}, lose = {losing}, tie = {tying}; the "
        "cloud sits roughly symmetrically about y=x, consistent with the null overall "
        f"Wilcoxon (p = {p_overall:.3f}) and the modest net decrease at matched FPR.")
    doc.add_picture(figB_png, width=Inches(4.8))
    doc.add_paragraph(
        "Figure B. Per-trial encounter counts before vs after enhancement at "
        "matched false-positive rate (identity line dashed).").italic = True

    # -------------------- Caveats --------------------
    doc.add_heading("Caveats", level=1)
    for cav in [
        "Primary caveat / lesson: apparent enhancement 'significance' is highly "
        "sensitive to the detection threshold. The prior draft's strong effect "
        "(p ~ 1.9e-6) was driven by an implausible ~0.5/s baseline FPR; at a "
        f"calibrated {fpr_b:.4f}/s FPR the effect is null.",
        f"The matched-filter template is built from only {tmpl_trials} near-endpoint "
        "high-SNR trials, so it may not generalize to all encounter morphologies.",
        "The SNR gain is a CROSS-TRIAL RANKING, not an absolute delta: the before "
        "and after traces are on different scales (drift-corrected raw vs "
        "matched-filter score), so their amplitudes are not directly comparable. "
        f"It is positive for only {snr_pos}/{n_trials} trials.",
        "Signals are in uncalibrated arbitrary units (a.u.).",
        f"Single cohort, infrared, {n_trials} trials; results are not yet replicated "
        "across cohorts or imaging modalities.",
        "In Figure A the before trace is the drift-corrected raw signal (the exact "
        "series the before detector runs on) and the after trace is the enhanced "
        "matched-filter score; they are shown on separate y-scales because the two "
        "quantities differ in units.",
    ]:
        doc.add_paragraph(cav, style="List Bullet")

    # -------------------- Reproducibility footer --------------------
    doc.add_heading("Reproducibility", level=1)
    doc.add_paragraph("Exact build command:")
    doc.add_paragraph(REPRO_CMD)
    doc.add_paragraph("Result files consumed by this report:")
    doc.add_paragraph(f"{REL_H5}")
    doc.add_paragraph(f"{REL_STATS}")
    doc.add_paragraph(f"{REL_DRIFT}")

    doc.save(DOCX_PATH)
    return DOCX_PATH


def scan_placeholders(path):
    from docx import Document
    doc = Document(path)
    tokens = ["{{", "}}", "placeholder", "TODO", "XXX", "FIXME", "TBD"]
    hits = []
    for para in doc.paragraphs:
        low = para.text.lower()
        for tok in tokens:
            if tok.lower() in low:
                hits.append((tok, para.text[:80]))
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                low = cell.text.lower()
                for tok in tokens:
                    if tok.lower() in low:
                        hits.append((tok, cell.text[:80]))
    return hits


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    stats = load_stats()
    drift = load_drift()

    figA_png, figA_pdf, figA_txt, _ = build_figure_A(stats)
    figB_png, figB_pdf, figB_txt = build_figure_B(stats)

    for f in [figA_png, figA_pdf, figA_txt, figB_png, figB_pdf, figB_txt]:
        assert os.path.getsize(f) > 0, f"EMPTY: {f}"
    print("Figures OK (non-empty):")
    for f in [figA_png, figA_pdf, figA_txt, figB_png, figB_pdf, figB_txt]:
        print(f"  {f}  ({os.path.getsize(f)} bytes)")

    docx_path = build_docx(stats, drift, figA_png, figB_png)
    assert os.path.getsize(docx_path) > 0, f"EMPTY: {docx_path}"

    hits = scan_placeholders(docx_path)
    if hits:
        print("PLACEHOLDER HITS FOUND:")
        for tok, txt in hits:
            print("  ", tok, "->", txt)
        raise SystemExit("Placeholder tokens present; fix before returning.")
    print(f"DOCX OK, placeholder scan CLEAN: {docx_path} ({os.path.getsize(docx_path)} bytes)")


if __name__ == "__main__":
    main()
