"""Render 'H1 - sampling bouts and odor.docx' STRICTLY from saved objects.
Every cited number is injected from data/stats.json / data/bouts.h5 attrs.
Nothing is hand-typed. Honest null framing: H1 NOT supported."""
import json
import os

import h5py
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
STATS = os.path.join(BASE, "data", "stats.json")
H5 = os.path.join(BASE, "data", "bouts.h5")
FIG = os.path.join(BASE, "reports", "figures", "F2_peri_bout.png")
OUT = os.path.join(BASE, "reports", "H1 - sampling bouts and odor.docx")

with open(STATS) as fh:
    st = json.load(fh)
with h5py.File(H5, "r") as f:
    ATTR = {k: f.attrs[k] for k in f.attrs}

meta = st["meta"]
H1 = st["H1"]
dA = st["deliverable_A"]
lm = H1["lead_magnitude"]
an = H1["a_bout_vs_null"]
bi = H1["b_bout_vs_incidental"]
amp = H1["amplitude_check"]

# ---------- derived display numbers (all from saved objects) ----------
med_peri = lm["median_peri_bout_eth"]
med_null = lm["median_null_eth"]
delta = lm["delta_median_obs_minus_null"]
ci = lm["peri_bout_mean_trialboot_ci"]  # [mean, lo, hi]
pct_lower = 100.0 * (1.0 - med_peri / med_null)
frac_gt = amp["frac_bouts_peri_gt_0p01"]
floor = amp["eth_floor_ref"]
rng = amp["eth_range_ref"]
achieved_rate = float(ATTR["achieved_pooled_median_rate_per_s"])


def f(x, n=4):
    return "{:.{}f}".format(float(x), n)


def p_fmt(x):
    return "{:.4f}".format(float(x))


# ---------- doc scaffold ----------
doc = Document()
styles = doc.styles["Normal"]
styles.font.name = "Calibri"
styles.font.size = Pt(11)


def h(text, level=1):
    doc.add_heading(text, level=level)


def para(text, italic=False, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = italic
    r.bold = bold
    return p


title = doc.add_heading("H1 - Selective sampling bouts and odor", level=0)

sub = doc.add_paragraph()
r = sub.add_run("Do sampling bouts coincide with elevated odor? (Selective Sampling-Bout analysis, reactions_2)")
r.italic = True

# headline banner
banner = doc.add_paragraph()
rb = banner.add_run("Result: H1 is NOT supported.")
rb.bold = True
rb.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)
banner.add_run(
    "  Peri-bout baseline-subtracted ethanol (median {} a.u.) is LOWER than the matched "
    "within-trial random-time null (median {} a.u.; delta = {} a.u., ~{:.0f}% below null), "
    "and is not greater than incidental-event peri-odor. Sampling bouts are not accompanied "
    "by elevated odor.".format(f(med_peri), f(med_null), f(delta), pct_lower)
)

# ============================ Goal ============================
h("1. Goal and hypotheses", 1)
para(
    "A sampling bout is a rare, deliberate event defined by a locomotor pause plus a head "
    "cast (a translation-invariant head-body bearing angular speed, omega). This report tests "
    "whether such bouts - not incidental head motion - coincide with elevated odor at the head."
)
para("H1 (directional): peri-bout baseline-subtracted ethanol exceeds BOTH (a) a matched "
     "within-trial random-time null AND (b) incidental-event peri-odor. Accept only if both hold.",
     bold=False)
para("H0: peri-bout ethanol equals the matched random-time null and does not exceed the "
     "incidental-event peri-odor.")

# ============================ Methods ============================
h("2. Methods", 1)
para(
    "Data were read through the project accessor only and processed with the shared library "
    "code/reactions2_common.py (which reuses reactions/code/reactions_common.py; no science "
    "re-implemented). All computation used the pinned interpreter "
    "(vras/Scripts/python.exe), headless matplotlib (Agg), fixed seed {}.".format(int(meta["seed"]))
)
para(
    "Replication unit is the TRIAL (one statistic per trial), pooling Loc1-6 (n = {} trials); "
    "anotherLoc (n = {}) is held separate. Only trials with at least one bout contribute to the "
    "bout-conditioned tests.".format(int(meta["n_pooled_trials"]), int(meta["n_anotherLoc_trials"]))
)
para(
    "Bout detector (final parameters, D6 rarity gate PASSES; not loosened, d6_tightened = {}): "
    "v_pause = {} px/s ({}th pct of pooled COM speed), tau_pause = {} s, dphi_min = {} deg, "
    "omega_min = {} deg/s ({}th pct of pooled omega), t_merge = {} s. Achieved pooled median "
    "bout rate = {} /s (~{:.0f}x rarer than the v1 baseline of {} /s).".format(
        bool(meta["d6_tightened"]),
        f(meta["v_pause_px_s"], 2), int(meta["final_bout_params"]["v_pause_pct"]),
        f(meta["final_bout_params"]["tau_pause"], 2), f(meta["final_bout_params"]["dphi_min"], 0),
        f(meta["omega_min_deg_s"], 1), int(meta["final_bout_params"]["omega_pct"]),
        f(meta["final_bout_params"]["t_merge"], 2),
        f(achieved_rate, 5), dA["rarity"]["fold_rarer_than_v1"], f(meta["v1_baseline_rate"], 1),
    )
)
para(
    "Odor signal: baseline-subtracted ethanol on the raw scale (raw minus a rolling 10th-percentile, "
    "20 s window), on the head clock. Peri-odor per event is the mean baseline-subtracted ethanol in "
    "[-0.5, +0.5] s around bout onset. The H1 null is a matched-count random-time permutation drawn "
    "within the same trial. Inference is trial-level Wilcoxon (never per-event point-bootstrap); "
    "trial-bootstrap CIs use {} draws (permutation null {} draws), seed {}. No family-wise "
    "correction; per-test CIs.".format(int(meta["n_boot"]), int(meta["n_perm"]), int(meta["seed"]))
)

# ============================ Results ============================
h("3. Results", 1)

para(
    "Magnitude and direction first (the p-value is secondary). Per contributing trial, the median "
    "peri-bout ethanol is {} a.u. (trial-bootstrap mean {} a.u., 95% CI [{}, {}]). The matched "
    "within-trial random-time null has a median of {} a.u. - so the observed peri-bout odor is "
    "actually LOWER than chance by {} a.u. (~{:.0f}% below null). The direction is opposite to "
    "H1.".format(
        f(med_peri), f(ci[0]), f(ci[1]), f(ci[2]), f(med_null), f(delta), pct_lower
    )
)
para(
    "(a) Bout vs matched null: the trial-level Wilcoxon test of bout > null gives p = {} "
    "(one-sided; stat = {}, n = {} contributing trials) - i.e., no evidence that peri-bout ethanol "
    "exceeds the null; the direction is against it.".format(
        p_fmt(an["p_greater"]), f(an["wilcoxon_stat"], 1), int(an["n_trials"])
    )
)
para(
    "(b) Specificity vs incidental events: peri-bout ethanol (median {} a.u.) is not greater than "
    "incidental-event peri-odor (median {} a.u.); Wilcoxon bout > incidental p = {} "
    "(stat = {}, n = {}).".format(
        f(bi["median_bout_peri"]), f(bi["median_incidental_peri"]),
        p_fmt(bi["p_greater"]), f(bi["wilcoxon_stat"], 1), int(bi["n_trials"])
    )
)
para(
    "Absolute-amplitude check (necessary, not sufficient). Peri-bout ethanol does sit above the "
    "instrument noise floor (~{} a.u.) relative to the full range (~{} a.u.): {:.1f}% of bouts have "
    "peri-odor > 0.01 a.u. (above_floor = {}). But above-floor is necessary, not sufficient - the "
    "inferential comparison against the matched null is the deciding test, and it is null / negative. "
    "Both acceptance conditions fail, so H1 is rejected (accept_H1 = {}).".format(
        f(floor, 4), f(rng, 2), 100.0 * frac_gt, bool(amp["above_floor"]), bool(H1["accept_H1"])
    )
)

# ---- Figure ----
doc.add_paragraph()
doc.add_picture(FIG, width=Inches(6.0))
last = doc.paragraphs[-1]
last.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap = doc.add_paragraph()
rc = cap.add_run(
    "Figure F2. Onset-aligned peri-bout signals (pooled Loc1-6; n(bouts) = {}, "
    "n(trials contributing) = {}; vertical line at bout onset, t = 0). (A) Mean peri-bout "
    "baseline-subtracted ethanol (a.u.) with 95% trial-bootstrap CI (blue), overlaid on the "
    "matched random-time null (grey dashed, 95% CI) and the incidental-event curve (red dotted); "
    "the shaded band marks the pre-onset window [-0.75, -0.25] s used by H2. The bout curve lies "
    "at or below both comparators throughout - peri-bout odor is not elevated. (B) Mean peri-bout "
    "COM speed (px/s, left axis) and head angular speed omega (deg/s, right axis), showing the "
    "locomotor stop at onset accompanied by the head cast. Shared with the H2 report.".format(
        int(st["figure_curves_meta"]["F2A_eth"]["n_events"]),
        int(st["figure_curves_meta"]["F2A_eth"]["n_trials"]),
    )
)
rc.italic = True
rc.font.size = Pt(9)

# ---- summary table ----
doc.add_paragraph()
h("3.1 Key numbers", 2)
tbl = doc.add_table(rows=1, cols=2)
tbl.style = "Light Grid Accent 1"
hdr = tbl.rows[0].cells
hdr[0].paragraphs[0].add_run("Quantity").bold = True
hdr[1].paragraphs[0].add_run("Value").bold = True
rows = [
    ("Median peri-bout ethanol (a.u.)", f(med_peri)),
    ("Peri-bout mean, 95% CI (a.u.)", "{} [{}, {}]".format(f(ci[0]), f(ci[1]), f(ci[2]))),
    ("Median matched random-time null (a.u.)", f(med_null)),
    ("Delta (observed - null) (a.u.)", f(delta)),
    ("Wilcoxon bout > null, p (one-sided)", p_fmt(an["p_greater"])),
    ("Median incidental-event peri-odor (a.u.)", f(bi["median_incidental_peri"])),
    ("Wilcoxon bout > incidental, p (one-sided)", p_fmt(bi["p_greater"])),
    ("Fraction of bouts with peri-odor > 0.01 a.u.", "{:.3f}".format(frac_gt)),
    ("Above noise floor?", str(bool(amp["above_floor"]))),
    ("Contributing trials (bout-conditioned tests)", str(int(an["n_trials"]))),
    ("Accept H1?", str(bool(H1["accept_H1"]))),
]
for k, v in rows:
    c = tbl.add_row().cells
    c[0].text = k
    c[1].text = v

# ============================ Caveats ============================
h("4. Caveats", 1)
para(
    "Modest N and sensor coverage. Only {} of the {} pooled trials contribute to the "
    "bout-conditioned tests: bouts are deliberately rare (achieved median rate {} /s) and some bout "
    "onsets fall outside ethanol-sensor coverage (NaN odor), so they cannot be scored. This limits "
    "statistical power; the negative result should be read as 'no detectable elevation at this N', "
    "not proof of exact zero.".format(int(an["n_trials"]), int(meta["n_pooled_trials"]),
                                      f(achieved_rate, 5))
)
para(
    "Above-floor is not sufficient. That most bouts sit above the noise floor tells us the signal is "
    "measurable, not that it is elevated relative to chance; the matched-null test is what "
    "adjudicates the odor claim, and it is null / negative."
)
para(
    "Single cohort, pixel units. Results are from one pooled cohort (Loc1-6); anotherLoc is held "
    "separate. Kinematics are reported in raw pixel and pixel/s units (no metric calibration applied), "
    "and ethanol is on the raw baseline-subtracted scale."
)

# ============================ Reproducibility ============================
h("5. Reproducibility", 1)
para(
    "Objects: data/stats.json (H1 block, figure_curves_meta) and data/bouts.h5 "
    "(/figure_curves/F2A_*, /figure_curves/F2B_*). Library version {}, created {} (UTC), seed {}, "
    "odor cutoff {}. Figure and report inject numbers from these objects; nothing is hardcoded.".format(
        meta["VERSION"], meta["created_utc"], int(meta["seed"]), f(meta["odor_cutoff"], 3)
    ),
    italic=True,
)
para(
    'Rebuild: "%AR_PY%" code\\build_F2.py ; "%AR_PY%" code\\build_H1_report.py '
    "(with AR_PY = the pinned vras interpreter). Outputs: reports\\figures\\F2_peri_bout.{png,pdf,txt} "
    "and reports\\H1 - sampling bouts and odor.docx.",
    italic=True,
)

doc.save(OUT)
print("WROTE:", OUT, os.path.getsize(OUT), "bytes")
