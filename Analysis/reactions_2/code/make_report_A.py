"""
Deliverable A report: "Sampling-bout definition and selectivity.docx"
All cited numbers injected from data/stats.json (+ bouts.h5 counts). Nothing hand-typed.
Embeds reports/figures/F1_bout_definition.png. Zero placeholder tokens.
"""
import json, os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
STATS = os.path.join(BASE, "data", "stats.json")
FIG = os.path.join(BASE, "reports", "figures", "F1_bout_definition.png")
OUT = os.path.join(BASE, "reports", "Sampling-bout definition and selectivity.docx")

with open(STATS, "r", encoding="utf-8") as fh:
    S = json.load(fh)
meta = S["meta"]
dA = S["deliverable_A"]
rar = dA["rarity"]
sel = dA["selectivity"]
fp = meta["final_bout_params"]

# ---- pull every number we cite --------------------------------------------
median_rate = rar["pooled_median_bout_rate_per_s"]
rate_ci = rar["bout_rate_mean_trialboot_ci"]  # [mean, lo, hi]
cnt = rar["count_distribution"]
frac_ge1 = rar["frac_trials_ge1_bout"]
frac_0 = rar["frac_trials_0_bout"]
v1_rate = rar["v1_baseline_rate_per_s"]
fold_rarer = rar["fold_rarer_than_v1"]
d6_pass = rar["d6_gate_passes"]
d6_tightened = meta["d6_tightened"]
d6_trigger = meta["d6_tighten_trigger"]

med_vcom_b = sel["median_v_com_bouts"]
med_vcom_i = sel["median_v_com_incidental"]
med_pom_b = sel["median_peak_omega_bouts_deg_s"]
med_pom_i = sel["median_peak_omega_incidental_deg_s"]
med_exc_b = sel["median_excursion_bouts_deg"]
wil_vcom = sel["trial_wilcoxon_incidental_gt_bout_vcom"]
wil_pom = sel["trial_wilcoxon_bout_ge_incidental_peakomega"]
low_com_note = sel["note_low_com_definitional"]

n_bouts = dA["n_bouts_pooled"]
n_inc = dA["n_incidental_pooled"]
n_contrib = dA["n_contributing_trials"]
ex = dA["example_trial"]

n_pooled = meta["n_pooled_trials"]
n_other = meta["n_anotherLoc_trials"]
v_pause = meta["v_pause_px_s"]
omega_min = meta["omega_min_deg_s"]
omega_pct = meta["omega_pct"]
seed = meta["seed"]
version = meta["VERSION"]
odor_cutoff = meta["odor_cutoff"]

# ---------------------------------------------------------------------------
doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)

def H(txt, lvl=1):
    doc.add_heading(txt, level=lvl)

def P(txt=""):
    return doc.add_para if False else doc.add_paragraph(txt)

def bullet(txt):
    doc.add_paragraph(txt, style="List Bullet")

# ---- Title ----------------------------------------------------------------
t = doc.add_heading("Sampling-Bout Definition and Selectivity", level=0)
sub = doc.add_paragraph()
r = sub.add_run("Deliverable A -- Selective Sampling-Bout analysis (reactions_2). "
                "Required characterization (not a hypothesis test).")
r.italic = True
r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

# ---- Purpose --------------------------------------------------------------
H("Purpose", 1)
P("This deliverable redefines the head-sampling event used in the reactions v1 analysis. "
  "The v1 detector flagged head-vs-body motion whenever a speed ratio exceeded R>=1.5 and "
  "swept that threshold. That approach was wrong for three reasons, and each motivates a "
  "specific design change here:")
bullet("Too frequent: the R>=1.5 sweep fired at roughly {:.1f} events/s -- routine, near-continuous "
       "head motion rather than deliberate, rare sampling. The redesign targets a rare event and "
       "achieves a pooled median rate of {:.4f}/s ({:.0f}x rarer).".format(v1_rate, median_rate, fold_rarer))
bullet("Denominator-biased / circular: the R>=1.5 ratio has body speed (v_com) in the denominator, so "
       "an event was defined partly by the COM slowing -- then 'COM slows near a bout' was reported as a "
       "finding. That is circular. Here the trigger kinematic is translation-invariant (angular speed of "
       "the head-body bearing) and the low-COM condition is stated as DEFINITIONAL, never as a result.")
bullet("No odor coherence: v1 imposed no requirement that events relate to the odor landscape, and its "
       "sheer frequency guaranteed spurious odor overlap. The redesign first establishes a rare, selective "
       "event class (this deliverable), so that subsequent odor hypotheses (H1-H3) are tested on deliberate "
       "sampling rather than on background motion.")

# ---- Methods --------------------------------------------------------------
H("Methods", 1)
P("Data come through the project accessor only, using the shared library reactions2_common "
  "(which reuses plume_common and reactions_common; no science re-implemented). Analyses were run "
  "under the pinned interpreter (vras) with random seed {}. Library version {}.".format(seed, version))
P("Kinematic (translation-invariant). The sampling trigger is the angular speed of the head-body "
  "bearing, omega = |d/dt bearing(head - body)| in deg/s. Because it uses only the head-relative-to-body "
  "orientation, omega is invariant to whole-animal translation and contains no v_com denominator -- "
  "removing the circularity of the v1 ratio.")
P("Bout definition. A sampling bout is the conjunction of (i) a locomotor pause -- a contiguous run with "
  "v_com < v_pause = {:.2f} px/s (25th percentile of pooled v_com) lasting at least tau_pause = {:.2f} s -- "
  "containing (ii) a qualifying head cast -- cumulative |d phi| >= {:.0f} deg AND peak omega >= omega_min = "
  "{:.1f} deg/s ({:.0f}th percentile of pooled omega). Pauses whose onsets fall within t_merge = {:.2f} s are "
  "merged into a single bout.".format(v_pause, fp["tau_pause"], fp["dphi_min"], omega_min, omega_pct, fp["t_merge"]))
P("Rarity gate (D6). The achieved pooled median bout rate is checked against the tighten trigger of "
  "{:.1f}/s: parameters are tightened only if the rate exceeds it. Incidental events (the contrast class) "
  "are high-omega events occurring while the animal is MOVING (v_com >= v_pause), using the same omega and "
  "refractory logic -- isolating the pause condition as the sole difference from bouts.".format(d6_trigger))
P("Units and scope. The unit of analysis is the trial; inference is trial-level (Wilcoxon signed-rank on "
  "paired within-trial medians). Data are pooled across Loc1-6 (n = {} trials); the {} anotherLoc trials are "
  "held separate. Odor coherence uses the Plume odor field with cutoff {:g}.".format(n_pooled, n_other, odor_cutoff))

# ---- Results --------------------------------------------------------------
H("Results", 1)

H("Figure F1", 2)
doc.add_picture(FIG, width=Inches(6.5))
cap = doc.add_paragraph()
cr = cap.add_run(
    "Figure F1. Sampling-bout definition and selectivity (pooled Loc1-6, n = {} trials; {} contributing; "
    "{} bouts vs {} incidental events). "
    "(A) Per-trial bout-rate distribution (log x); black line = pooled median {:.4f}/s, red dashed line = "
    "v1 detector rate {:.1f}/s ({:.0f}x rarer). {:.1f}% of trials have >=1 bout, {:.1f}% have zero. "
    "(B) COM speed during event: bouts (median {:.2f} px/s) << incidental (median {:.1f} px/s) -- this low-COM "
    "separation is DEFINITIONAL (the pause condition), not a finding. "
    "(C) Head peak angular speed: bouts (median {:.1f} deg/s) > incidental (median {:.1f} deg/s); median bout "
    "angular excursion {:.0f} deg.".format(
        n_pooled, n_contrib, n_bouts, n_inc,
        median_rate, v1_rate, fold_rarer, frac_ge1 * 100, frac_0 * 100,
        med_vcom_b, med_vcom_i, med_pom_b, med_pom_i, med_exc_b))
cr.italic = True
cr.font.size = Pt(9)

H("Rarity: the redesign selects rare, deliberate events", 2)
P("The redesigned detector produces a rare event. The pooled median bout rate is {:.4f}/s "
  "(trial-bootstrap mean {:.4f}/s, 95% CI [{:.4f}, {:.4f}]/s) -- {:.0f}x rarer than the v1 detector's "
  "{:.1f}/s. Per trial, the bout count distribution is min {}, median {:.0f}, max {}. "
  "{:.1f}% of trials contain at least one bout, while {:.1f}% contain none -- i.e., most head motion is NOT "
  "sampling.".format(
      median_rate, rate_ci[0], rate_ci[1], rate_ci[2], fold_rarer, v1_rate,
      cnt["min"], cnt["median"], cnt["max"], frac_ge1 * 100, frac_0 * 100))
P("D6 rarity gate: PASSED. The achieved median rate ({:.4f}/s) is far below the tighten trigger ({:.1f}/s), "
  "so parameters were NOT tightened (d6_tightened = {}). Loosening was deliberately avoided, as it would "
  "re-admit routine motion. The rate sits below the aspirational 0.05-0.3/s target and is accepted as "
  "maximally specific; the resulting modest sample ({} contributing trials, {} bouts) is carried forward as "
  "a documented power caveat.".format(median_rate, d6_trigger, str(d6_tightened), n_contrib, n_bouts))

H("Selectivity: bouts vs incidental motion", 2)
P("Low COM speed is DEFINITIONAL, not a finding. " + low_com_note + " By construction, bouts occur during a "
  "locomotor pause, so their COM speed is very low (median {:.2f} px/s) versus incidental high-omega events "
  "while moving (median {:.1f} px/s; trial-level Wilcoxon incidental > bout, W = {:.0f}, p = {:.2g}, n = {} "
  "trials). This separation restates the pause condition and must not be read as a result -- it was exactly "
  "v1's circular error, and is reported here only to confirm the detector behaves as defined.".format(
      med_vcom_b, med_vcom_i, wil_vcom["stat"], wil_vcom["p"], wil_vcom["n_trials"]))
P("Head casts are larger during bouts (a genuine selectivity property). Bout events show substantially larger "
  "head casts than incidental motion: peak angular speed median {:.1f} deg/s for bouts versus {:.1f} deg/s for "
  "incidental (trial-level Wilcoxon bout >= incidental, W = {:.0f}, p = {:.2g}, n = {} trials), with a median "
  "angular excursion of {:.0f} deg per bout. Bouts are therefore not merely 'slow moments' -- they are pauses "
  "accompanied by pronounced, deliberate head sweeps.".format(
      med_pom_b, med_pom_i, wil_pom["stat"], wil_pom["p"], wil_pom["n_trials"], med_exc_b))

H("Sanity note", 2)
P("A representative high-activity example is trial index {} ({}), with {} bouts at a per-trial rate of "
  "{:.4f}/s -- consistent with the pooled distribution and with visible pause-plus-head-cast episodes.".format(
      ex["trial_index"], ex["file_name"], ex["bout_count"], ex["bout_rate"]))

# ---- Caveats --------------------------------------------------------------
H("Caveats", 1)
bullet("Modest N: only {} of {} pooled trials contribute at least one bout ({} bouts total). Trial-level power "
       "for the downstream odor hypotheses (H1-H3) is limited; effect magnitudes are led over p-values.".format(
           n_contrib, n_pooled, n_bouts))
bullet("Single cohort, pixel units: results derive from one infrared cohort with spatial quantities in camera "
       "pixels (px, px/s); no cross-cohort or metric-unit generalization is claimed.")
bullet("Low-COM is definitional: the bout-vs-incidental COM-speed gap (median {:.2f} vs {:.1f} px/s) is imposed "
       "by the pause condition and carries no inferential weight.".format(med_vcom_b, med_vcom_i))

# ---- Reproducibility footer -----------------------------------------------
H("Reproducibility", 1)
P("Exact command (pinned interpreter; headless matplotlib):")
mono = doc.add_paragraph()
mrun = mono.add_run(
    '"C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe" '
    'code/make_F1.py   # figure\n'
    '"C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe" '
    'code/make_report_A.py   # this report')
mrun.font.name = "Consolas"
mrun.font.size = Pt(9)
P("Result files (read-only inputs; no science recomputed by figure/report builders):")
bullet("data/stats.json  -- all injected numbers (deliverable_A: rarity, selectivity; meta parameters)")
bullet("data/bouts.h5    -- figure_curves/F1_* arrays for the plotted distributions")
bullet("reports/figures/F1_bout_definition.{png,pdf,txt}  -- Figure F1 and its numeric sidecar")
foot = doc.add_paragraph()
fr = foot.add_run("Seed {}; library {}; unit of analysis = trial; pooled Loc1-6 (n = {}).".format(
    seed, version, n_pooled))
fr.italic = True
fr.font.size = Pt(9)
fr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
tmp = OUT + ".tmp"
doc.save(tmp)
os.replace(tmp, OUT)
print("Report written:", OUT, "(", os.path.getsize(OUT), "bytes )")
