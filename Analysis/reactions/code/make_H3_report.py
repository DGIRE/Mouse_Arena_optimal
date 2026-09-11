"""Render the H3 DOCX report STRICTLY from saved result objects.

Every number is injected from data/stats.json (and the F3 example identifiers).
Nothing scientific is recomputed. Honest null framing: H3 NOT supported.
"""
import json
import os

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions"
STATS = os.path.join(BASE, "data", "stats.json")
FIG_PNG = os.path.join(BASE, "reports", "figures",
                       "F3_example_trajectory_and_timeseries.png")
OUT = os.path.join(BASE, "reports", "H3 - sweeps in odor-reached regions.docx")
AR_PY = (r"C:/Projects/Repos/Agentic Research/Research Setup/"
         r"vras/Scripts/python.exe")

with open(STATS, "r", encoding="utf-8") as fh:
    S = json.load(fh)

meta = S["meta"]
H3 = S["H3"]
ex = S["F3_example"]
amp = S["H1_amplitude_check"]

# ---- pull numbers (no hand typing) ----
p_fsweep_gt_focc = H3["test_f_sweep_gt_f_occ"]["p_value"]
W_fsweep_gt_focc = H3["test_f_sweep_gt_f_occ"]["statistic"]
p_fsweep_gt_null = H3["test_f_sweep_gt_null"]["p_value"]
W_fsweep_gt_null = H3["test_f_sweep_gt_null"]["statistic"]
med_fsweep = H3["median_f_sweep"]
med_focc = H3["median_f_occ"]
frac_enriched = H3["frac_trials_enriched"]
cutoff = H3["cutoff"]
n_trials_H3 = H3["test_f_sweep_gt_f_occ"]["n_trials"]

seed = meta["seed"]
n_perm = meta["n_permutations"]
n_trials_pooled = meta["n_trials_pooled"]
n_trials_processed = meta["n_trials_processed"]
version = meta["VERSION"]
created = meta["created_utc"]
noise_floor = amp["noise_floor_ref"]

ex_file = ex["file_name"]
ex_rate = ex["sweep_rate"]
ex_count = ex["sweep_count"]
ex_loc = ex["end_loc"]
ex_idx = ex["trial_index"]


def fnum(x, nd=3):
    return f"{x:.{nd}f}"


def pfmt(p):
    if p < 1e-3:
        return f"{p:.2e}"
    return f"{p:.3f}"


doc = Document()

# base style
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)


def H(text, level=1):
    doc.add_heading(text, level=level)


def P(text, bold=False, italic=False, size=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    return p


def bullet(text):
    doc.add_paragraph(text, style="List Bullet")


# ================= TITLE =================
title = doc.add_heading(
    "H3 - Nose sweeps are not spatially enriched in odor-reached regions "
    "beyond occupancy", level=0)

sub = P("Nose-Sweeps & Odor-Guided Search  |  Hypothesis 3 report", italic=True)
sub.alignment = WD_ALIGN_PARAGRAPH.LEFT

# headline verdict box
vp = doc.add_paragraph()
vr = vp.add_run(
    "VERDICT: H3 is NOT supported (null result). "
    "Nose sweeps track where the animal spends time (occupancy), not "
    "odor-reached regions specifically.")
vr.bold = True
vr.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)

# ================= GOAL =================
H("1. Goal and hypotheses", 1)
P("H3 asks whether nose sweeps are spatially enriched in odor-reached regions "
  "of the arena beyond what the animal's occupancy alone would predict. If "
  "sweeps are an odor-guided search behavior, they should concentrate in bins "
  "the odor plume has reached, over and above the time the animal spends there.")
P("Hypotheses (direction reported before significance; nulls headlined):",
  bold=True)
bullet(f"H3 (alternative): f_sweep > f_occ - the fraction of sweeps landing in "
       f"odor-reached bins exceeds the fraction of all kept head frames in "
       f"those bins (spatial enrichment beyond occupancy).")
bullet("H0 (null): f_sweep = f_occ - sweeps are distributed across "
       "odor-reached bins in proportion to occupancy (no enrichment).")

# ================= METHODS =================
H("2. Methods", 1)
P("Pipeline and library.", bold=True)
P(f"All quantities were computed on the head clock via the accessor and the "
  f"shared library reactions_common (which imports plume_common), reusing the "
  f"advancing-reference de-jump cleaning, head-clock interpolation, and "
  f"velocity/R machinery. Version tag {version}. Interpreter: the project "
  f"virtual environment python (vras). Random seed {seed} throughout. "
  f"Results object created {created}.")

P("Odor-reached definition (D9).", bold=True)
P(f"A bin is 'odor-reached' if, in the reused per-location odor field "
  f"(Plume locations/data/odor_fields.h5, read-only), that bin has a valid "
  f"distinct-trial count >= 3 AND a maximum field value > {cutoff} "
  f"(the odor-field cutoff). The cutoff sits above the deconvolution noise "
  f"floor (~{noise_floor:g}); mapped-bin ethanol is above the noise floor, so "
  f"'odor-reached' bins reflect real signal rather than noise.")

P("Per-trial statistics.", bold=True)
bullet("f_sweep = fraction of a trial's detected sweep peaks that fall in "
       "odor-reached bins.")
bullet("f_occ = fraction of all kept head frames (occupancy) in that trial "
       "that fall in odor-reached bins.")
bullet(f"Within-trial permutation null: draw n_sweeps random frame times "
       f"({n_perm} draws per trial, seed {seed}); the per-trial statistic is "
       f"f_sweep - mean(null).")

P("Inference.", bold=True)
P(f"Unit of analysis = trial. Pooled sample = Loc1-6, n = {n_trials_pooled} "
  f"trials (of {n_trials_processed} processed; anotherLoc analysed separately "
  f"and excluded, D10). Two paired/one-sided Wilcoxon signed-rank tests: "
  f"(i) f_sweep > f_occ, and (ii) f_sweep - mean(null) > 0. Per-test "
  f"statistics; no family-wise correction across H1-H3.")

# ================= RESULTS =================
H("3. Results", 1)

P(f"H3 is not supported. Across the {n_trials_H3} pooled trials, the median "
  f"fraction of sweeps in odor-reached bins (f_sweep = {fnum(med_fsweep)}) is "
  f"essentially equal to - and in fact slightly below - the median occupancy "
  f"fraction in those bins (f_occ = {fnum(med_focc)}). The direction of the "
  f"effect is therefore against enrichment.")

P(f"The one-sided Wilcoxon test for enrichment beyond occupancy "
  f"(f_sweep > f_occ) is not significant: W = {fnum(W_fsweep_gt_focc, 1)}, "
  f"p = {pfmt(p_fsweep_gt_focc)}. The complementary test against the "
  f"within-trial permutation null (f_sweep - mean(null) > 0) is likewise "
  f"not significant: W = {fnum(W_fsweep_gt_null, 1)}, "
  f"p = {pfmt(p_fsweep_gt_null)}.")

P(f"Only {fnum(frac_enriched)} of trials "
  f"({100*frac_enriched:.1f}%) show f_sweep exceeding their occupancy-matched "
  f"expectation - close to the ~50% expected by chance. Taken together: "
  f"sweeps land in odor-reached bins about as often as the animal simply "
  f"happens to be there. Sweeps track occupancy, not odor-reached regions "
  f"specifically.")

# results table
P("Summary of H3 statistics (injected from stats.json):", bold=True)
tbl = doc.add_table(rows=1, cols=2)
tbl.style = "Light Grid Accent 1"
hdr = tbl.rows[0].cells
hdr[0].paragraphs[0].add_run("Quantity").bold = True
hdr[1].paragraphs[0].add_run("Value").bold = True

rows = [
    ("Median f_sweep (sweeps in odor-reached bins)", fnum(med_fsweep)),
    ("Median f_occ (occupancy in odor-reached bins)", fnum(med_focc)),
    ("Direction", "f_sweep < f_occ (against enrichment)"),
    ("Wilcoxon f_sweep > f_occ: statistic",
     fnum(W_fsweep_gt_focc, 1)),
    ("Wilcoxon f_sweep > f_occ: p-value", pfmt(p_fsweep_gt_focc)),
    ("Wilcoxon f_sweep - mean(null) > 0: statistic",
     fnum(W_fsweep_gt_null, 1)),
    ("Wilcoxon f_sweep - mean(null) > 0: p-value",
     pfmt(p_fsweep_gt_null)),
    ("Fraction of trials enriched", fnum(frac_enriched)),
    ("Odor-field cutoff", f"{cutoff:g}"),
    ("Permutation draws / trial", str(n_perm)),
    ("Unit of analysis / n", f"trial / {n_trials_H3} (pooled Loc1-6)"),
]
for k, v in rows:
    c = tbl.add_row().cells
    c[0].text = k
    c[1].text = v

# figure
doc.add_paragraph()
P("Figure 3.", bold=True)
if os.path.exists(FIG_PNG):
    doc.add_picture(FIG_PNG, width=Inches(6.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

cap = doc.add_paragraph()
cr = cap.add_run(
    f"Figure 3 (illustrative for H3). Example trial with the highest pooled "
    f"sweep rate: {ex_file} ({ex_loc}, trial index {ex_idx}; "
    f"sweep rate {fnum(ex_rate)}/s, {ex_count} sweeps). "
    f"(A) Center-of-mass (body) trajectory within the arena box "
    f"[0,580] x [0,280] px, equal aspect, colored by R = v_nose/v_com; the red "
    f"x marks the odor source endpoint. (B) Two stacked time series on the head "
    f"clock: (i) baseline-subtracted ethanol (a.u.) and (ii) R(t), with markers "
    f"at the detected sweep-peak times (identical event times in both panels). "
    f"This single-trial example is illustrative only; the H3 verdict rests on "
    f"the pooled statistics above, which do not support enrichment.")
cr.italic = True
cr.font.size = Pt(9)

# ================= CAVEATS =================
H("4. Caveats", 1)
bullet("Sweeps track occupancy. The near-identity of f_sweep and f_occ (with "
       "f_sweep marginally lower) indicates sweeps are distributed like time "
       "spent, not preferentially in odor-reached bins. This is the honest, "
       "direction-first reading: the point estimate favors the null.")
bullet("Reused odor field. Odor-reached bins come from a per-location odor "
       "field aggregated across trials (reused from the Plume-locations "
       "analysis), not a per-trial plume map; this smooths over trial-to-trial "
       "plume variability.")
bullet("Single cohort / infrared / pixels. One imaging cohort, infrared "
       "tracking, spatial units in pixels; no cross-cohort replication.")
bullet(f"Direction before significance. Even setting aside the non-significant "
       f"p-values (p = {pfmt(p_fsweep_gt_focc)} and "
       f"p = {pfmt(p_fsweep_gt_null)}), the effect direction and the "
       f"near-chance enriched-trial fraction ({fnum(frac_enriched)}) argue "
       f"against H3 on their own.")
bullet(f"Detector threshold. Sweep detection is threshold-dependent and many "
       f"detected sweeps are routine nose motion; the odor-field cutoff "
       f"({cutoff:g}) is above the deconvolution noise floor "
       f"(~{noise_floor:g}), so mapped-bin ethanol reflects real signal.")

# ================= REPRODUCIBILITY =================
H("5. Reproducibility", 1)
P("All numbers above are injected from the saved results object; nothing was "
  "recomputed or hand-typed in this report.")
P("Result files:", bold=True)
bullet(r"data\stats.json  (H3 block, F3_example, meta)")
bullet(r"data\sweeps.h5  (/trials/<idx> per-frame arrays; /sweeps per-sweep table)")
bullet(r"reports\figures\F3_example_trajectory_and_timeseries.{png,pdf,txt}")
P("Regenerate the figure and this report (project interpreter; headless Agg):",
  bold=True)
code = doc.add_paragraph()
cc = code.add_run(
    f'"{AR_PY}" code\\make_F3.py\n'
    f'"{AR_PY}" code\\make_H3_report.py')
cc.font.name = "Consolas"
cc.font.size = Pt(9)

foot = P(f"Seed {seed}; permutation draws {n_perm}; pooled n = "
         f"{n_trials_pooled} (Loc1-6); library {version}; results created "
         f"{created}.", italic=True, size=9)

doc.save(OUT)
print("WROTE:", OUT, f"({os.path.getsize(OUT)} bytes)")
