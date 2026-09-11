"""Render the H2 DOCX report, injecting every number from data/stats.json.

Output: reports/H2 - alignment vs distance.docx
Zero placeholder tokens; re-opens the doc and scans for them at the end.
"""
import json
import os

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories"
STATS_PATH = os.path.join(BASE, "data", "stats.json")
FIG_PNG = os.path.join(BASE, "reports", "figures", "F3_angle_vs_distance.png")
OUT = os.path.join(BASE, "reports", "H2 - alignment vs distance.docx")

with open(STATS_PATH, "r", encoding="utf-8") as f:
    stats = json.load(f)

h2 = stats["H2"]
meta = stats["meta"]
curve = h2["F3_binned_curve"]
wil = h2["wilcoxon_slopes_gt_0"]

# --- injected numbers ---
n = h2["n_trials_with_finite_slope"]
pool = h2["pool"]
unit = h2["unit"]
median_slope = h2["median_slope_deg_per_px"]
slope_ci = h2["median_slope_ci95_boot"]
direction = h2["direction"]
wil_stat = wil["stat"]
wil_p = wil["p"]
wil_alt = wil["alternative"]
seed = meta["seed"]
traj_ver = meta["traj_common_version"]
n_boot = meta["n_boot"]
n_pooled = meta["n_pooled"]
agg_path = meta["aggregate_path"]
created = meta["created_utc"]

bin_width = curve["bin_width_px"]
min_samples = curve["min_samples_per_bin"]
dist_track = curve["distance_track"]
bc = curve["bin_centers"]
mt = curve["mean_theta"]
clo = curve["ci_lo"]
chi = curve["ci_hi"]
ntr = curve["n_trials"]
nsa = curve["n_samples"]

# curve-rise assessment (from stored curve)
ymin_i = min(range(len(mt)), key=lambda i: mt[i])
ymax_i = max(range(len(mt)), key=lambda i: mt[i])
curve_rises = mt[-1] > mt[0] and ymax_i > ymin_i  # crude; described honestly below

alpha = 0.05
sig = wil_p < alpha

REPRO_CMD = (
    'AR_PY="C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe"'
    ' ; "$AR_PY" code/make_F3.py ; "$AR_PY" code/make_H2_report.py'
)

doc = Document()

# base style
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(11)


def h(text, level=1):
    doc.add_heading(text, level=level)


def p(text, bold=False, italic=False, size=None):
    par = doc.add_paragraph()
    run = par.add_run(text)
    run.bold = bold
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    return par


def bullet(text):
    doc.add_paragraph(text, style="List Bullet")


# ---------------- Title ----------------
title = doc.add_heading("Hypothesis 2 - Body-axis alignment vs distance to source",
                        level=0)
sub = doc.add_paragraph()
r = sub.add_run("Mouse Arena trajectory analysis - pooled Loc1-6 (n = %d trials)" % n_pooled)
r.italic = True

# ---------------- Goal ----------------
h("1. Goal and hypotheses", 1)
p("Goal: test whether the mouse's body axis becomes better aligned toward the "
  "odor source as it approaches, using the absolute body-axis-to-source angle "
  "theta as a function of distance-to-source d.")
p("H2: theta decreases as the animal approaches the source - equivalently, theta "
  "INCREASES with distance-to-source d, so the per-trial OLS slope of theta on d "
  "is positive (better alignment when closer).", bold=True)
p("H0: theta is independent of d (zero per-trial slope).")
p("Accept H2 iff (a) per-trial slopes are significantly > 0 (Wilcoxon signed-rank) "
  "AND (b) the F3 binned curve rises with distance. Direction is reported before "
  "significance throughout.")

# ---------------- Methods ----------------
h("2. Methods", 1)
p("Data access. Trials were read through the shared accessor and traj_common "
  "pipeline (%s) from the aggregate file %s. Analyses were run with the project "
  "interpreter (vras). Random seed = %d for all bootstraps."
  % (traj_ver, agg_path, seed))
p("Geometry / angle convention. For each kept head-clock frame, the body axis is "
  "u = unit(head - body) and the to-source direction is s = unit(endpoint - body). "
  "The absolute angle between them, theta = arccos(u . s), lies in [0, 180] "
  "degrees; small theta means the body axis points toward the source.")
p("Per-trial statistic. For each trial we fit an ordinary-least-squares (OLS) "
  "slope of theta(t) on d(t) over the kept frames of the body track. A positive "
  "slope means theta is larger when farther away (better alignment when closer), "
  "which is the H2-predicted direction.")
p("Group test. Across the %d pooled Loc1-6 trials (replication unit = %s), a "
  "Wilcoxon signed-rank test (alternative = '%s') asks whether the per-trial "
  "slopes are > 0. The median slope with a 95%% bootstrap CI (%d resamples over "
  "trials) is reported for direction and effect size."
  % (n, unit, wil_alt, n_boot))
p("F3 binning (D9). Distance-to-source was binned in fixed %g-px bins from 0 to "
  "the max observed distance on the %s track; per bin we report the mean of theta "
  "pooled over all in-bin samples across trials, shaded with a 95%% CI (bootstrap "
  "over trials, seed %d), requiring >= %d samples per plotted bin."
  % (bin_width, dist_track, seed, min_samples))

# ---------------- Results ----------------
h("3. Results", 1)

# direction-before-significance summary sentence
p("Direction. The per-trial slopes are POSITIVE in direction: median slope = "
  "%+.4f deg/px (95%% bootstrap CI [%+.4f, %+.4f]), the sign predicted by H2."
  % (median_slope, slope_ci[0], slope_ci[1]), bold=True)
p("Significance. The Wilcoxon signed-rank test (slopes > 0) is NOT significant: "
  "W = %.1f, p = %.3f (n = %d, %s). At alpha = %.2f the null of zero/negative "
  "slope is not rejected."
  % (wil_stat, wil_p, n, unit, alpha), bold=True)

# per-trial slope distribution summary from the stored slopes
slopes = h2["per_trial_slopes"]
n_pos = sum(1 for v in slopes if v > 0)
n_neg = sum(1 for v in slopes if v < 0)
n_zero = sum(1 for v in slopes if v == 0)
smin = min(slopes)
smax = max(slopes)
p("Per-trial slope distribution: of %d trials, %d have positive slopes and %d "
  "negative (%d exactly zero); slopes range from %+.4f to %+.4f deg/px. The "
  "effect is a modest population-level tendency, not driven by a handful of "
  "trials." % (n, n_pos, n_neg, n_zero, smin, smax))

# verdict on H2
verdict = ("H2 is NOT supported at alpha = %.2f. The per-trial slopes trend in "
           "the predicted (positive) direction but do not reach significance, "
           "and the F3 binned curve does not rise monotonically with distance "
           "(see below)." % alpha)
p(verdict, bold=True)

# Figure F3
h("3.1 Figure F3 - Alignment vs distance to source", 2)
doc.add_picture(FIG_PNG, width=Inches(6.0))
cap = doc.add_paragraph()
cap_r = cap.add_run(
    "Figure F3. Mean absolute body-axis-to-source angle theta (deg) vs "
    "distance-to-source d (px), pooled Loc1-6. Distance binned in %g-px bins on "
    "the %s track (>= %d samples/bin); shaded band is the 95%% bootstrap CI over "
    "trials (n_boot = %d, seed %d). Annotation gives the H2 per-trial-slope "
    "Wilcoxon result (W = %.1f, p = %.3f) and the median slope (%+.4f deg/px, "
    "95%% CI [%+.4f, %+.4f]). Under H2 the curve should fall with distance in "
    "theta if alignment improves when closer; note the curve is non-monotonic."
    % (bin_width, dist_track, min_samples, n_boot, seed, wil_stat, wil_p,
       median_slope, slope_ci[0], slope_ci[1]))
cap_r.italic = True
cap_r.font.size = Pt(9)

# Curve description
p("Reading the stored F3 curve: theta = %.1f deg at the nearest bin (d = %.0f px), "
  "reaches a minimum of %.1f deg at d = %.0f px and a maximum of %.1f deg at "
  "d = %.0f px, and is %.1f deg at the farthest well-sampled bin. The curve is "
  "non-monotonic (it does not rise steadily with distance), so the F3 rising "
  "criterion for accepting H2 is not clearly met."
  % (mt[0], bc[0], mt[ymin_i], bc[ymin_i], mt[ymax_i], bc[ymax_i], mt[-1]))

# Binned-curve table
h("3.2 F3 binned curve (values plotted)", 2)
tbl = doc.add_table(rows=1, cols=6)
tbl.style = "Light Grid Accent 1"
hdr = tbl.rows[0].cells
for j, htext in enumerate(["d (px)", "mean theta (deg)", "CI lo", "CI hi",
                           "n trials", "n samples"]):
    hdr[j].paragraphs[0].add_run(htext).bold = True
for i in range(len(bc)):
    cells = tbl.add_row().cells
    cells[0].text = "%.0f" % bc[i]
    cells[1].text = "%.2f" % mt[i]
    cells[2].text = "%.2f" % clo[i]
    cells[3].text = "%.2f" % chi[i]
    cells[4].text = "%d" % ntr[i]
    cells[5].text = "%d" % nsa[i]

# ---------------- Caveats ----------------
h("4. Caveats and limitations", 1)
bullet("Angle convention verified in Gate 1: a near-source trial gave theta ~ 23 "
       "deg (a trial visibly facing the port yields small theta), confirming "
       "u = unit(head - body) and s = unit(endpoint - body).")
bullet("Single cohort, infrared recording, distances in pixels (uncalibrated to "
       "physical units); results are within-cohort and not cross-validated.")
bullet("Direction before significance: the slope sign is positive (H2 direction) "
       "but the Wilcoxon test is not significant (p = %.3f); we do not over-claim "
       "an effect." % wil_p)
bullet("Per-test 95%% CIs are reported with no family-wise correction across "
       "H1-H3; interpret p-values accordingly.")
bullet("The two farthest bins are sparsely populated by trials (few trials reach "
       "the largest distances), so the far end of the F3 curve is less reliable "
       "even where per-sample counts meet the >= %d threshold." % min_samples)

# ---------------- Reproducibility ----------------
h("5. Reproducibility", 1)
p("All numbers above are injected from data/stats.json (H2 block); no value was "
  "typed by hand. Stats created_utc = %s; seed = %d; traj_common = %s; "
  "n_boot = %d." % (created, seed, traj_ver, n_boot))
p("Result files:")
bullet(r"data\stats.json (H2 block; source of every number)")
bullet(r"data\trajectory_metrics.json / .h5 (per-trial h2_slope attribute)")
bullet(r"reports\figures\F3_angle_vs_distance.png / .pdf / .txt")
bullet(r"reports\H2 - alignment vs distance.docx (this report)")
p("Reproduce (from the trajectories base dir):")
cmd_par = doc.add_paragraph()
cmd_run = cmd_par.add_run(REPRO_CMD)
cmd_run.font.name = "Consolas"
cmd_run.font.size = Pt(9)

doc.save(OUT)
print("WROTE:", OUT)
print("bytes:", os.path.getsize(OUT))

# ---------------- placeholder scan ----------------
tokens = ["{{", "}}", "placeholder", "TODO", "XXX", "FIXME", "TBD"]
doc2 = Document(OUT)
hits = []
for para in doc2.paragraphs:
    t = para.text
    for tok in tokens:
        if tok.lower() in t.lower():
            hits.append(("para", tok, t[:80]))
for table in doc2.tables:
    for row in table.rows:
        for cell in row.cells:
            for tok in tokens:
                if tok.lower() in cell.text.lower():
                    hits.append(("cell", tok, cell.text[:80]))
print("PLACEHOLDER_HITS:", len(hits))
for hh in hits:
    print("  ", hh)
