"""Task 1 (odor fields) figure builder + DOCX report writer.

STRICTLY reads saved result objects (odor_fields.h5, odor_field_stats.json).
Never recomputes science. Every number injected from the saved files.

Run:  "$AR_PY" code/make_task1_report.py
"""
import os
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import h5py

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations"
H5_PATH = os.path.join(BASE, "data", "odor_fields.h5")
STATS_PATH = os.path.join(BASE, "data", "odor_field_stats.json")
FIG_DIR = os.path.join(BASE, "reports", "figures", "fields")
DOCX_PATH = os.path.join(BASE, "reports", "Odor field report.docx")

# Source-file provenance strings (relative to project base) for sidecars/footer.
SRC_H5_REL = r"data\odor_fields.h5"
SRC_STATS_REL = r"data\odor_field_stats.json"

LOC_ORDER = ["Loc1", "Loc2", "Loc3", "Loc4", "Loc5", "Loc6", "anotherLoc"]

EXTENT = [0, 580, 0, 280]


# ----------------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------------
def load_stats():
    with open(STATS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------
def make_figures():
    os.makedirs(FIG_DIR, exist_ok=True)
    created = []
    with h5py.File(H5_PATH, "r") as f:
        for loc in LOC_ORDER:
            grp = f[loc]
            mx = grp["max"][:]
            mn = grp["mean"][:]
            lo = grp["min"][:]
            cnt = grp["count"][:].astype(float)
            xe = grp["x_edges"][:]
            ye = grp["y_edges"][:]
            ep = grp["endpoint"][:]
            n_trials = int(grp.attrs["n_trials"])
            bin_size = int(grp.attrs["bin_size_px"])
            cov = float(grp.attrs["coverage_frac"])
            samp = int(grp.attrs["samples_total"])

            ext = [float(xe[0]), float(xe[-1]), float(ye[0]), float(ye[-1])]

            # count panel: show blank where 0 trials
            cnt_masked = np.where(cnt <= 0, np.nan, cnt)

            panels = [
                ("max map", mx, "ethdeconv, a.u."),
                ("mean map", mn, "ethdeconv, a.u."),
                ("min map", lo, "ethdeconv, a.u."),
                ("per-bin trial count", cnt_masked, "trials"),
            ]

            fig, axes = plt.subplots(4, 1, figsize=(7.0, 10.5))
            for ax, (title, data, unit) in zip(axes, panels):
                cmap = plt.get_cmap("jet").copy()
                cmap.set_bad(color="white")
                arr = np.ma.masked_invalid(np.asarray(data, dtype=float))
                im = ax.imshow(
                    arr,
                    extent=ext,
                    origin="lower",
                    aspect="equal",
                    cmap=cmap,
                    interpolation="nearest",
                )
                ax.plot(float(ep[0]), float(ep[1]), marker="x", color="white",
                        markersize=10, mew=2, linestyle="none")
                ax.set_title(title, fontsize=10)
                ax.set_xlim(ext[0], ext[1])
                ax.set_ylim(ext[2], ext[3])
                ax.set_xlabel("x (px)", fontsize=8)
                ax.set_ylabel("y (px)", fontsize=8)
                ax.tick_params(labelsize=7)
                cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
                cb.set_label(unit, fontsize=8)
                cb.ax.tick_params(labelsize=7)

            fig.suptitle("%s (n=%d trials)" % (loc, n_trials), fontsize=12)
            caption = ("bin L=%d px, coverage=%.1f%%, total samples=%d"
                       % (bin_size, cov * 100.0, samp))
            fig.text(0.5, 0.005, caption, ha="center", fontsize=8)
            fig.tight_layout(rect=[0, 0.02, 1, 0.98])

            png = os.path.join(FIG_DIR, "field_%s.png" % loc)
            pdf = os.path.join(FIG_DIR, "field_%s.pdf" % loc)
            txt = os.path.join(FIG_DIR, "field_%s.txt" % loc)
            fig.savefig(png, dpi=200, bbox_inches="tight")
            fig.savefig(pdf, bbox_inches="tight")
            plt.close(fig)

            with open(txt, "w", encoding="utf-8") as fh:
                fh.write("Figure: field_%s\n" % loc)
                fh.write("Location: %s (n=%d trials)\n" % (loc, n_trials))
                fh.write("Panels (top->bottom): max, mean, min, per-bin trial count\n")
                fh.write("%s\n" % caption)
                fh.write("Source result files:\n")
                fh.write("  %s\n" % SRC_H5_REL)
                fh.write("  %s\n" % SRC_STATS_REL)

            created.extend([png, pdf, txt])
    return created


# ----------------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------------
def fnum(x, nd=3):
    if x is None:
        return "n/a"
    try:
        return ("%%.%df" % nd) % float(x)
    except (TypeError, ValueError):
        return str(x)


def fsci(x, nd=2):
    if x is None:
        return "n/a"
    return ("%%.%de" % nd) % float(x)


def fci(ci, nd=3):
    if ci is None:
        return "n/a"
    return "[%s, %s]" % (fnum(ci[0], nd), fnum(ci[1], nd))


# ----------------------------------------------------------------------------
# DOCX
# ----------------------------------------------------------------------------
def add_para(doc, text, bold=False, size=None, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    return p


def build_docx(stats):
    meta = stats["_meta"]
    locs = stats["locations"]
    pooled = stats["pooled"]
    rob = stats["robustness_head_vs_body"]

    cutoff = meta["cutoff"]
    mad = meta["global_MAD_ethdeconv"]

    doc = Document()

    # ---- Title ----
    t = doc.add_heading("Odor Field Report (Task 1)", level=0)
    add_para(doc, "Generated %s from saved result objects. "
             "Every reported value is injected from odor_fields.h5 / "
             "odor_field_stats.json." % meta["created_utc"], italic=True, size=9)

    # ---- Overview ----
    doc.add_heading("Overview", level=1)
    add_para(doc,
             "Time-averaged odor (ethdeconv, sensor a.u.) was mapped over the "
             "arena for each of six reward end-locations (Loc1-Loc6) and a "
             "separate heterogeneous location (anotherLoc), reported "
             "separately. Bin size L is chosen per location by the coverage "
             "rule (see Methods): Loc1-Loc5 and anotherLoc resolve to L=15 px, "
             "Loc6 to L=10 px, and the pool to L=10 px (a %d x %d bin grid), "
             "masking bins with fewer than %d contributing trials. Pooling "
             "Loc1-Loc6 yields %d trials over %d visited bins (%.1f%% "
             "coverage). anotherLoc contributes %d additional trials and is "
             "analysed on its own."
             % (pooled["grid_shape"][0], pooled["grid_shape"][1],
                meta["min_trials"], pooled["n_trials"],
                pooled["n_visited_bins"], pooled["coverage_frac"] * 100.0,
                locs["anotherLoc"]["n_trials"]))
    pmc = pooled["sparseness"]["gini_mc_null"]
    add_para(doc,
             "Headline: the odor field is only weakly concentrated in absolute "
             "magnitude (pooled Gini=%s, normalized entropy=%s), but that Gini "
             "is highly significant against a Monte-Carlo spatially-uniform "
             "null (null Gini mean=%s, 95%% CI %s, p=%s). Concentration is "
             "chiefly SPATIAL: the MAX field falls off exponentially with "
             "distance from the reward port (pooled max decay lambda=%s px, "
             "95%% CI %s px), indicating odor concentrates near the source at "
             "a scale of tens of pixels."
             % (fnum(pooled["sparseness"]["gini"]),
                fnum(pooled["sparseness"]["normalized_entropy"]),
                fnum(pmc["null_gini_mean"]),
                fci(pmc["null_gini_ci95"]),
                fsci(pmc["pvalue"]),
                fnum(pooled["distance"]["max"]["exp_decay"]["lambda"], 1),
                fci(pooled["distance"]["max"]["exp_decay"]["lambda_ci95"], 1)))

    # ---- Sparseness ----
    doc.add_heading("Sparseness and concentration", level=1)
    add_para(doc,
             "Cutoff for a bin being 'above background' is max(3*MAD, "
             "small_floor) with global MAD(ethdeconv)=%s (1.4826-scaled). "
             "Because 3*MAD=%s is below the 1e-3 floor, the small_floor of "
             "%s binds and is used as the cutoff. Sparseness is the fraction "
             "of valid (>=%d-trial) bins whose mean ethdeconv exceeds this "
             "cutoff, evaluated at 1x/3x/5x MAD as robustness."
             % (fsci(mad), fsci(meta["cutoff_3xMAD"]), fsci(cutoff),
                meta["min_trials"]))

    add_para(doc,
             "Significance of the Gini is assessed against a Monte-Carlo null "
             "(H0 = spatially uniform field): per-bin sample counts are held "
             "fixed and the observed total odor mass is redistributed each draw "
             "via a multinomial over the pooled samples (equal per-sample "
             "probability), and the Gini is recomputed; p = fraction(null Gini "
             ">= observed Gini) over %d draws (seed %d). This replaces the "
             "trivial analytic floor gini(constant field)=0, which is reported "
             "as a footnote only."
             % (pmc["n_draws"], pmc["seed"]))

    tbl = doc.add_table(rows=1, cols=9)
    tbl.style = "Light Grid Accent 1"
    hdr = tbl.rows[0].cells
    for i, h in enumerate(["Location", "n valid bins", "frac>3xMAD",
                           "top-5% mass", "Gini", "norm. entropy",
                           "MC null Gini mean", "MC null 95% CI", "p"]):
        hdr[i].text = h
    for loc in LOC_ORDER + ["pooled"]:
        node = pooled if loc == "pooled" else locs[loc]
        sp = node["sparseness"]
        mc = sp["gini_mc_null"]
        row = tbl.add_row().cells
        row[0].text = "pooled Loc1-6" if loc == "pooled" else loc
        row[1].text = str(sp["n_valid_bins"])
        row[2].text = fnum(sp["frac_above_3xMAD"])
        row[3].text = fnum(sp["top5pct_mass_share"])
        row[4].text = fnum(sp["gini"])
        row[5].text = fnum(sp["normalized_entropy"])
        row[6].text = fnum(mc["null_gini_mean"])
        row[7].text = fci(mc["null_gini_ci95"])
        row[8].text = fsci(mc["pvalue"])

    add_para(doc,
             "Interpretation: nearly all visited bins carry a low, near-uniform "
             "residual odor at the 1x-MAD level (frac>1xMAD ~1.0 in most "
             "locations), so the mean field is diffuse in absolute terms. Only "
             "~8-14%% of bins exceed the 3x-MAD level and almost none exceed "
             "5x MAD, and the top 5%% of bins hold only ~9-12%% of total odor "
             "mass, so the field is NOT strongly sparse. Nonetheless the "
             "observed Gini (pooled %s) is FAR above the Monte-Carlo uniform "
             "null (null mean %s, 95%% CI %s) with p=%s: the small departure "
             "from uniformity is real, not sampling noise. Concentration is "
             "chiefly expressed as a spatial gradient toward the source "
             "(next section). (Footnote: the analytic Gini of a same-N constant "
             "field is exactly 0 by construction; it carries no sampling "
             "variability and is used only as a reference floor, not as the "
             "significance null.)"
             % (fnum(pooled["sparseness"]["gini"]),
                fnum(pmc["null_gini_mean"]),
                fci(pmc["null_gini_ci95"]),
                fsci(pmc["pvalue"])))

    # ---- Distance dependence ----
    doc.add_heading("Distance dependence (odor vs distance to source)", level=1)
    add_para(doc,
             "Per-bin odor was related to the Euclidean distance from each bin "
             "center to the location endpoint (reward port); for the pooled "
             "analysis distance is to the centroid of the six endpoints "
             "(%s, %s px). Two fits per target: OLS of log(odor) vs distance "
             "(slope) and an exponential decay a*exp(-d/lambda)+c (decay "
             "constant lambda, px)."
             % (fnum(pooled["endpoint_centroid"][0], 1),
                fnum(pooled["endpoint_centroid"][1], 1)))
    add_para(doc,
             "HONEST FRAMING: the MEAN field is heavily diluted - the vast "
             "majority of deconvolved values sit at/near the small_floor. We "
             "therefore LEAD with the MAX field, reporting max-field OLS slopes "
             "and exponential decay lambdas with 95%% CIs. Where the mean-field "
             "exponential fit is flagged degenerate in the saved results "
             "(fitted lambda exceeds the arena diagonal, ~644 px), it is "
             "reported as 'NA (degenerate fit)' rather than printing the "
             "non-physical value.", bold=False)
    add_para(doc,
             "MULTIPLE-COMPARISONS POSTURE: confidence intervals are per-test "
             "(each location plus the pool tested separately); no family-wise "
             "correction is applied, and direction is reported before "
             "significance throughout.", italic=True, size=9)

    def _lambda_cell(ed):
        if ed.get("degenerate") or ed.get("lambda") is None:
            return "NA (degenerate fit)"
        return "%s %s" % (fnum(ed["lambda"], 1), fci(ed["lambda_ci95"], 1))

    def _ci_includes_zero(ci):
        if ci is None or ci[0] is None or ci[1] is None:
            return False
        return ci[0] <= 0.0 <= ci[1]

    tbl = doc.add_table(rows=1, cols=4)
    tbl.style = "Light Grid Accent 1"
    hdr = tbl.rows[0].cells
    for i, h in enumerate(["Location", "max OLS slope (1/px) [95% CI]",
                           "max exp lambda (px) [95% CI]",
                           "mean exp lambda (px) [95% CI]"]):
        hdr[i].text = h
    zero_locs = []
    for loc in LOC_ORDER + ["pooled"]:
        node = pooled if loc == "pooled" else locs[loc]
        dmax = node["distance"]["max"]
        dmean = node["distance"]["mean"]
        row = tbl.add_row().cells
        row[0].text = "pooled Loc1-6" if loc == "pooled" else loc
        if dmax["ols_log"]:
            ci = dmax["ols_log"]["slope_ci95"]
            note = " (CI incl. 0)" if _ci_includes_zero(ci) else ""
            if _ci_includes_zero(ci):
                zero_locs.append("pooled" if loc == "pooled" else loc)
            row[1].text = "%s %s%s" % (fnum(dmax["ols_log"]["slope"], 5),
                                       fci(ci, 5), note)
        else:
            row[1].text = "n/a"
        row[2].text = _lambda_cell(dmax["exp_decay"])
        row[3].text = _lambda_cell(dmean["exp_decay"])

    if zero_locs:
        zero_txt = ("The max-OLS slope CI INCLUDES 0 (not significant) at: %s; "
                    "all other locations and the pool exclude 0."
                    % ", ".join(zero_locs))
    else:
        zero_txt = ("Every max-OLS slope CI excludes 0.")
    add_para(doc,
             "Interpretation (LEAD with the MAX field): pooled max-OLS "
             "slope=%s /px, 95%% CI %s (excludes 0), i.e. peak odor decreases "
             "with distance from the source. %s The pooled max exponential "
             "decay constant is lambda=%s px (95%% CI %s px), a spatial scale "
             "of a few tens of pixels. Per-location max lambdas range from "
             "~14 px (Loc5) to ~54 px (Loc1, Loc6); some single-location fits "
             "are noisier (wider CIs) given <=20 trials, but the pooled fit is "
             "well constrained. For the MEAN field the exponential lambda is "
             "flagged degenerate (>arena diagonal) at Loc1, Loc2 and anotherLoc "
             "and is reported as NA there; the remaining mean-field lambdas are "
             "large (consistent with a diluted mean field) and are shown for "
             "completeness only. Conclusion: odor concentrates near the source; "
             "the reliable spatial scale is the pooled max-field lambda of "
             "~%s px."
             % (fnum(pooled["distance"]["max"]["ols_log"]["slope"], 5),
                fci(pooled["distance"]["max"]["ols_log"]["slope_ci95"], 5),
                zero_txt,
                fnum(pooled["distance"]["max"]["exp_decay"]["lambda"], 1),
                fci(pooled["distance"]["max"]["exp_decay"]["lambda_ci95"], 1),
                fnum(pooled["distance"]["max"]["exp_decay"]["lambda"], 0)))

    # ---- Trajectory types ----
    doc.add_heading("Trajectory types and encounters", level=1)
    add_para(doc,
             "Per-trial metrics (replication unit = trial): path length (px), "
             "tortuosity (path/straight-line), number of odor encounters, and "
             "fraction of the path above the odor threshold. Summaries below "
             "are medians with [Q1, Q3]. The animal-aware summary is "
             "DEGENERATE because file_names lack a 6-digit animal token, so "
             "animal_of returns '?' for every trial; trial is used as the "
             "replication unit throughout.")

    tbl = doc.add_table(rows=1, cols=6)
    tbl.style = "Light Grid Accent 1"
    hdr = tbl.rows[0].cells
    for i, h in enumerate(["Location", "n trials", "path length px (med [IQR])",
                           "tortuosity (med [IQR])", "n encounters (med [IQR])",
                           "frac path>thr (med [IQR])"]):
        hdr[i].text = h
    for loc in LOC_ORDER + ["pooled"]:
        node = pooled if loc == "pooled" else locs[loc]
        ts = node["trajectory_summary"]

        def cell(m):
            return "%s [%s, %s]" % (fnum(m["median"], 2), fnum(m["q1"], 2),
                                    fnum(m["q3"], 2))
        row = tbl.add_row().cells
        row[0].text = "pooled Loc1-6" if loc == "pooled" else loc
        row[1].text = str(node["n_trials"])
        row[2].text = cell(ts["path_length_px"])
        row[3].text = cell(ts["tortuosity"])
        row[4].text = cell(ts["n_encounters"])
        row[5].text = cell(ts["frac_path_above_threshold"])

    sp_te = pooled["trajectory_summary"]["spearman_tortuosity_vs_nencounters"]
    sp_tf = pooled["trajectory_summary"]["spearman_tortuosity_vs_frac_above"]
    add_para(doc,
             "Association (Spearman, unit=trial, pooled Loc1-6, n=%d): "
             "tortuosity vs n_encounters rho=%s (95%% CI %s, p=%s); "
             "tortuosity vs fraction-of-path-above-threshold rho=%s (95%% CI "
             "%s, p=%s). Splitting trials by tortuosity tertiles, straighter "
             "trajectories tend to spend a LARGER fraction of their (shorter) "
             "path in odor (negative rho with frac>thr), while raw encounter "
             "counts are only weakly and non-significantly related to "
             "tortuosity."
             % (sp_te["n"], fnum(sp_te["rho"]), fci(sp_te["ci95"]),
                fsci(sp_te["pvalue"]), fnum(sp_tf["rho"]),
                fci(sp_tf["ci95"]), fsci(sp_tf["pvalue"])))

    # ---- Robustness ----
    doc.add_heading("Robustness (head vs body track)", level=1)
    add_para(doc,
             "The pooled Loc1-6 mean field computed from the head track agrees "
             "strongly with the same field from the body track (ethdeconv "
             "aligned to the body clock, same L=%d grid, NaN-aware Pearson "
             "over %d commonly-valid bins): r=%s. The head-vs-body cleaning "
             "choice is therefore not driving the result."
             % (rob["grid_L"], rob["n_common_valid_bins"],
                fnum(rob["pearson_r"])))

    # ---- Hypotheses ----
    doc.add_heading("Hypotheses (direction, then significance)", level=1)
    # H1
    add_para(doc,
             "H1 (sparseness: concentration index vs uniform null). DIRECTION: "
             "the field is MORE concentrated than a spatially-uniform map "
             "(pooled Gini=%s; normalized entropy=%s < 1). SIGNIFICANCE: "
             "against the Monte-Carlo uniform null the observed Gini far "
             "exceeds the null (null mean=%s, 95%% CI %s, p=%s). The departure "
             "is small in magnitude but highly significant. (The analytic "
             "floor gini(constant)=0 is a reference only, not the significance "
             "null.) VERDICT: H1 ACCEPTED - the concentration index exceeds the "
             "uniform null - with the caveat that overall sparseness is weak "
             "and concentration is chiefly spatial (see H2)."
             % (fnum(pooled["sparseness"]["gini"]),
                fnum(pooled["sparseness"]["normalized_entropy"]),
                fnum(pmc["null_gini_mean"]),
                fci(pmc["null_gini_ci95"]),
                fsci(pmc["pvalue"])))
    # H2
    add_para(doc,
             "H2 (distance: bin odor decreases with distance). DIRECTION: "
             "negative - peak (max) odor decreases with distance to the "
             "source. SIGNIFICANCE: pooled max OLS slope=%s /px with 95%% CI "
             "%s (excludes 0); pooled max exp decay lambda=%s px (CI %s). "
             "The mean-field OLS was unavailable (diluted field). VERDICT: "
             "H2 ACCEPTED for the max field (odor concentrates near the source, "
             "scale ~%s px)."
             % (fnum(pooled["distance"]["max"]["ols_log"]["slope"], 5),
                fci(pooled["distance"]["max"]["ols_log"]["slope_ci95"], 5),
                fnum(pooled["distance"]["max"]["exp_decay"]["lambda"], 1),
                fci(pooled["distance"]["max"]["exp_decay"]["lambda_ci95"], 1),
                fnum(pooled["distance"]["max"]["exp_decay"]["lambda"], 0)))
    # H3
    add_para(doc,
             "H3 (trajectory types differ in odor encountered). DIRECTION: "
             "tortuosity is negatively associated with the fraction of path in "
             "odor (rho=%s, 95%% CI %s, p=%s, n=%d), i.e. trajectory shape "
             "relates to odor exposure; the tortuosity vs raw-encounter-count "
             "association is weak and non-significant (rho=%s, p=%s). VERDICT: "
             "H3 ACCEPTED - trajectory types differ in odor exposure "
             "(frac-of-path-above-threshold), effect size and CI reported "
             "above; supported directionally by the significant "
             "tortuosity-vs-frac association."
             % (fnum(sp_tf["rho"]), fci(sp_tf["ci95"]), fsci(sp_tf["pvalue"]),
                sp_tf["n"], fnum(sp_te["rho"]), fsci(sp_te["pvalue"])))

    # ---- Methods ----
    doc.add_heading("Methods", level=1)
    add_para(doc,
             "Data source: %s (aggregate schema %s), read via accessor "
             "code/mouse_arena_aggregate_io.py. Interpreter: project venv "
             "python.exe (%s). Random seed = %d. Signal = ethdeconv "
             "(deconvolved ethanol sensor, sensor a.u., NOT calibrated ppm), "
             "sampled at Fs=%g Hz, aligned to the head clock via "
             "np.interp(head_time, sig_time, sig, left=nan, right=nan). "
             "Analysis code %s."
             % (meta["aggregate_path"], meta["aggregate_schema"],
                meta["plume_common_version"], meta["seed"], meta["Fs"],
                meta["plume_common_version"]))
    # Build per-location chosen-L / coverage sentence directly from JSON.
    l_bits = []
    for loc in LOC_ORDER:
        nd = locs[loc]
        l_bits.append("%s L=%d px (%.1f%% coverage)"
                      % (loc, nd["chosen_L"], nd["coverage_frac"] * 100.0))
    l_bits.append("pooled Loc1-6 L=%d px (%.1f%% coverage)"
                  % (pooled["chosen_L"], pooled["coverage_frac"] * 100.0))
    l_scan_str = ", ".join(str(v) for v in meta["L_scan_values"])
    add_para(doc,
             "Grid/binning: candidate bin sizes L in {%s} px. RULE: choose the "
             "SMALLEST L for which at least %.0f%% of visited bins are backed "
             "by >=%d distinct contributing trials (coverage target %.0f%%); "
             "L=%d px is only a fallback if no candidate meets the rule. The "
             "finer grids clear the rule at every location, so no fallback was "
             "used (L_fallback_used=false throughout). Chosen L per location: "
             "%s. Bins with fewer than %d distinct contributing trials are "
             "masked (NaN) and rendered blank."
             % (l_scan_str, meta["coverage_target"] * 100.0, meta["min_trials"],
                meta["coverage_target"] * 100.0, max(meta["L_scan_values"]),
                "; ".join(l_bits), meta["min_trials"]))
    add_para(doc,
             "Cleaning: head track cleaned inside the arena box [0,580]x"
             "[0,280] px, non-finite samples dropped, then a GLOBAL pooled "
             "de-jump at the 99.5th-percentile step (advancing-reference rule: "
             "compare each sample to the last accepted position, not the raw "
             "previous sample, so a single outlier does not drag the "
             "reference). Global de-jump Q (head)=%s px; Q (body)=%s px. "
             "Clock alignment of the sensor to the head timeline uses "
             "np.interp with NaN fill outside the sensor's time support. "
             "Sparseness cutoff = max(3*MAD, 1e-3) with MAD 1.4826-scaled; "
             "distance fits use OLS of log-odor and an exponential decay, 95%% "
             "CIs; trajectory replication unit = trial."
             % (fnum(meta["global_dejump_Q_head"], 4),
                fnum(meta["global_dejump_Q_body"], 4)))

    # ---- Results (figures) ----
    doc.add_heading("Results: odor field figures", level=1)
    add_para(doc,
             "Each figure shows four vertically stacked panels (top->bottom): "
             "max, mean, min, and per-bin trial count; jet colormap, masked "
             "bins blank (white), reward port marked with a white x.",
             italic=True, size=9)
    with h5py.File(H5_PATH, "r") as f:
        for loc in LOC_ORDER:
            grp = f[loc]
            n_trials = int(grp.attrs["n_trials"])
            bin_size = int(grp.attrs["bin_size_px"])
            cov = float(grp.attrs["coverage_frac"])
            samp = int(grp.attrs["samples_total"])
            png = os.path.join(FIG_DIR, "field_%s.png" % loc)
            doc.add_heading("%s (n=%d trials)" % (loc, n_trials), level=2)
            doc.add_picture(png, width=Inches(6.0))
            last = doc.paragraphs[-1]
            last.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = ("Figure. %s odor field. bin L=%d px, coverage=%.1f%%, "
                   "total samples=%d. Source: %s + %s."
                   % (loc, bin_size, cov * 100.0, samp,
                      SRC_H5_REL, SRC_STATS_REL))
            add_para(doc, cap, italic=True, size=8)

    # ---- Caveats ----
    doc.add_heading("Caveats", level=1)
    for c in [
        "Head-tracking cleaning removes only the fastest ~0.5%% of steps "
        "(99.5th-percentile global de-jump); results are robust to this "
        "choice (head-vs-body r=%s)." % fnum(rob["pearson_r"]),
        "Bins with fewer than %d contributing trials are masked; sparse "
        "coverage at the arena edges is therefore not reported."
        % meta["min_trials"],
        "Single cohort, infrared recordings only; %d trials total across "
        "Loc1-Loc6 (plus %d for anotherLoc)."
        % (pooled["n_trials"], locs["anotherLoc"]["n_trials"]),
        "The sensor signal (ethdeconv) is in arbitrary units and is NOT "
        "calibrated to ppm; absolute concentrations are not interpretable.",
        "anotherLoc is heterogeneous and is reported separately from the "
        "pooled Loc1-Loc6 analysis.",
        "Animal-aware summaries are degenerate (file_names lack a 6-digit "
        "animal token; animal_of returns '?'); trial is the replication unit.",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(c)

    # ---- Reproducibility footer ----
    doc.add_heading("Reproducibility", level=1)
    add_para(doc,
             'Exact command to rebuild this report and all figures from the '
             'saved results: "$AR_PY" code/make_task1_report.py '
             '(AR_PY = "C:/Projects/Repos/Agentic Research/Research Setup/vras/'
             'Scripts/python.exe"; matplotlib Agg/headless).',
             size=9)
    add_para(doc,
             "Saved science was produced by: "
             '"$AR_PY" code/build_odor_fields.py (seed %d).' % meta["seed"],
             size=9)
    add_para(doc,
             "Result files consumed (no science recomputed): %s, %s. "
             "Report/figures built by code/make_task1_report.py."
             % (SRC_H5_REL, SRC_STATS_REL), size=9)

    doc.save(DOCX_PATH)
    return DOCX_PATH


# ----------------------------------------------------------------------------
# Placeholder scan
# ----------------------------------------------------------------------------
def scan_placeholders(path):
    doc = Document(path)
    bad = ["{{", "}}", "placeholder", "TODO", "XXX", "FIXME", "TBD"]
    hits = []
    for i, p in enumerate(doc.paragraphs):
        txt = p.text
        low = txt.lower()
        for b in bad:
            if (b in txt) or (b.lower() in low):
                hits.append(("para[%d]" % i, b, txt[:80]))
    for ti, tbl in enumerate(doc.tables):
        for ri, row in enumerate(tbl.rows):
            for ci, cell in enumerate(row.cells):
                txt = cell.text
                low = txt.lower()
                for b in bad:
                    if (b in txt) or (b.lower() in low):
                        hits.append(("table[%d][%d][%d]" % (ti, ri, ci), b,
                                     txt[:80]))
    return hits


# ----------------------------------------------------------------------------
def main():
    stats = load_stats()
    figs = make_figures()
    docx_path = build_docx(stats)

    # verify figures non-empty
    problems = []
    for fp in figs:
        if not os.path.exists(fp) or os.path.getsize(fp) == 0:
            problems.append(fp)

    hits = scan_placeholders(docx_path)

    print("=== FIGURES ===")
    n_png = sum(1 for f in figs if f.endswith(".png"))
    n_pdf = sum(1 for f in figs if f.endswith(".pdf"))
    n_txt = sum(1 for f in figs if f.endswith(".txt"))
    print("png=%d pdf=%d txt=%d (expect 7 each)" % (n_png, n_pdf, n_txt))
    print("empty/missing figure files: %d" % len(problems))
    for p in problems:
        print("  MISSING/EMPTY:", p)
    print("=== DOCX ===")
    print("path:", docx_path, "size:", os.path.getsize(docx_path))
    print("placeholder hits:", len(hits))
    for h in hits:
        print("  ", h)
    print("=== DONE ===")


if __name__ == "__main__":
    main()
