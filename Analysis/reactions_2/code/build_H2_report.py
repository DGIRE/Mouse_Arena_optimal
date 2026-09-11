"""Render 'H2 - odor precedes sampling.docx' STRICTLY from saved objects.
Every cited number is injected from data/stats.json / data/bouts.h5 attrs.
Nothing is hand-typed. Honest, non-circular framing: H2 is NOT supported.

H2 replaces v1's CIRCULAR 'COM slows during sweeps' (slowing is definitional
here) with a directional, non-circular test: does odor RISE before bout onset?
Odor is measured independently of the pause/cast that define the bout."""
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
OUT = os.path.join(BASE, "reports", "H2 - odor precedes sampling.docx")

with open(STATS) as fh:
    st = json.load(fh)
with h5py.File(H5, "r") as f:
    ATTR = {k: f.attrs[k] for k in f.attrs}

meta = st["meta"]
H2 = st["H2"]
dA = st["deliverable_A"]
df = H2["direction_first"]
pvb = H2["pre_vs_baseline"]
pvn = H2["pre_vs_null"]
slp = H2["onset_slope_gt0"]
cin = H2["control_incidental_pre_vs_baseline"]
csp = H2["control_spatial_split"]

# ---------- derived display numbers (all from saved objects) ----------
med_pre = df["median_pre_onset_eth"]
med_base = df["median_trial_baseline"]
med_slope = df["median_onset_slope_au_per_s"]
delta_pre = med_pre - med_base  # pre minus baseline (from saved medians)
achieved_rate = float(ATTR["achieved_pooled_median_rate_per_s"])


def f(x, n=4):
    return "{:.{}f}".format(float(x), n)


def sci(x):
    return "{:.2e}".format(float(x))


def p_fmt(x):
    x = float(x)
    return "{:.2e}".format(x) if x < 1e-3 else "{:.4f}".format(x)


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


doc.add_heading("H2 - Does odor precede sampling-bout onset?", level=0)

sub = doc.add_paragraph()
r = sub.add_run(
    "Directional, non-circular test of odor -> behavior at bout onset "
    "(Selective Sampling-Bout analysis, reactions_2)"
)
r.italic = True

# headline banner (null, honest)
banner = doc.add_paragraph()
rb = banner.add_run("Result: H2 is NOT supported.")
rb.bold = True
rb.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)
banner.add_run(
    "  In the pre-onset window [-0.75, -0.25] s the baseline-subtracted ethanol "
    "(median {} a.u.) is NOT above the trial baseline (median {} a.u.); if anything it is "
    "slightly lower (delta = {} a.u.). Wilcoxon pre > baseline p = {}; pre > matched-null p = {}; "
    "and the onset-aligned slope over [-1, 0] s is not positive (median {} a.u./s; slope > 0 "
    "p = {}). Odor does not rise ahead of deliberate sampling bouts.".format(
        f(med_pre), f(med_base), f(delta_pre),
        p_fmt(pvb["p_greater"]), p_fmt(pvn["p_greater"]),
        sci(med_slope), p_fmt(slp["p_greater"]),
    )
)

# ============================ Goal ============================
h("1. Goal and hypotheses", 1)
para(
    "A sampling bout is a rare, deliberate event defined by a locomotor pause plus a head cast "
    "(a translation-invariant head-body bearing angular speed, omega). H2 asks a directional "
    "question: does odor RISE before the animal initiates such a bout? A leading odor rise would "
    "be evidence that the odor drives the decision to sample, rather than the sample merely "
    "coinciding with odor."
)
para(
    "Non-circular by construction. This test replaces the v1 claim that 'COM slows during sweeps'. "
    "That claim was CIRCULAR here: a locomotor pause (low COM speed) is part of the very definition "
    "of a bout, so 'slowing' is definitional, not a finding. H2 instead measures the odor signal "
    "independently of the pause and the cast that define the bout, and asks only about its "
    "time course before onset.",
    bold=False,
)
para(
    "H2 (directional): pre-onset ethanol in [-0.75, -0.25] s exceeds BOTH (a) the trial baseline "
    "(trial median baseline-subtracted ethanol) AND (b) a matched random-time null, with a positive "
    "onset-aligned slope over [-1, 0] s; and this precedence is specific to deliberate bouts "
    "(surviving incidental-event and spatial controls). Accept only if all hold."
)
para(
    "H0: pre-onset ethanol equals the trial baseline / matched null, with no positive onset slope, "
    "and any pre-onset structure is not specific to bouts."
)

# ============================ Methods ============================
h("2. Methods", 1)
para(
    "Data were read through the project accessor only and processed with the shared library "
    "code/reactions2_common.py (which reuses reactions/code/reactions_common.py; no science "
    "re-implemented). All computation used the pinned interpreter (vras/Scripts/python.exe), "
    "headless matplotlib (Agg), fixed seed {}.".format(int(meta["seed"]))
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
    "Odor signal and precedence measures. Ethanol is baseline-subtracted on the raw scale (raw minus "
    "a rolling 10th-percentile, 20 s window), on the head clock. Signals are onset-aligned (bout "
    "onset at t = 0) on a +/-1.0 s, 50 ms grid. Precedence is scored three ways, per trial: "
    "(i) pre-onset level = mean baseline-subtracted ethanol in the pre-onset window [-0.75, -0.25] s; "
    "(ii) the trial baseline = the trial median baseline-subtracted ethanol (the comparator for the "
    "pre-onset level); and (iii) the onset-aligned slope = the linear slope of the mean ethanol over "
    "[-1, 0] s. A matched random-time null draws same-count events at random times within the same "
    "trial."
)
para(
    "Controls (specificity). (1) Incidental-event control: the same pre-onset > baseline test is run "
    "on incidental high-omega-while-moving events (the contrast class). H2 is specific only if "
    "incidental events do NOT show a pre-onset odor rise. (2) Spatial split: pre-onset odor for bouts "
    "starting inside odor-reached space vs outside; a genuine odor-triggered process should show a "
    "higher pre-onset level for in-odor bouts."
)
para(
    "Inference is trial-level Wilcoxon (never per-event point-bootstrap); permutation null uses {} "
    "draws, trial-bootstrap {} draws, seed {}, odor cutoff {}. Direction and magnitude are reported "
    "before p-values; no family-wise correction (per-test).".format(
        int(meta["n_perm"]), int(meta["n_boot"]), int(meta["seed"]), f(meta["odor_cutoff"], 3)
    )
)

# ============================ Results ============================
h("3. Results", 1)

para(
    "Magnitude and direction first (the p-value is secondary). Averaged over contributing trials, "
    "the pre-onset ethanol is {} a.u. - which is not above but slightly below the trial baseline of "
    "{} a.u. (delta = {} a.u.). The direction is opposite to H2: there is no pre-onset rise.".format(
        f(med_pre), f(med_base), f(delta_pre)
    )
)
para(
    "(a) Pre-onset vs trial baseline: the trial-level Wilcoxon test of pre-onset > baseline gives "
    "p = {} (one-sided; stat = {}, n = {} contributing trials) - no evidence that pre-onset odor "
    "exceeds the trial baseline.".format(
        p_fmt(pvb["p_greater"]), f(pvb["wilcoxon_stat"], 1), int(pvb["n_trials"])
    )
)
para(
    "(b) Pre-onset vs matched null: pre-onset > null p = {} (stat = {}, n = {}) - again null, with "
    "the direction against H2.".format(
        p_fmt(pvn["p_greater"]), f(pvn["wilcoxon_stat"], 1), int(pvn["n_trials"])
    )
)
para(
    "(c) Onset-aligned slope: the median onset-aligned slope over [-1, 0] s is {} a.u./s, and the "
    "trial-level test of slope > 0 gives p = {} (stat = {}, n = {}). Odor is not ramping up into "
    "bout onset.".format(
        sci(med_slope), p_fmt(slp["p_greater"]), f(slp["wilcoxon_stat"], 1), int(slp["n_trials"])
    )
)

para("Controls strengthen the null.", bold=True)
para(
    "(d) Incidental-event control. The same pre-onset > baseline test on incidental high-omega "
    "events is strongly positive: p = {} (stat = {}, n = {} trials). So a pre-onset odor rise DOES "
    "exist - but for incidental, unstructured motion, not for deliberate sampling bouts. If anything, "
    "odor precedes incidental motion; deliberate bouts are not the odor-triggered class. This is the "
    "opposite of what H2 requires, and it rules out a mere sensitivity/power explanation for the null "
    "on bouts (the test can detect a pre-onset rise when one is present).".format(
        p_fmt(cin["p_greater"]), f(cin["wilcoxon_stat"], 1), int(cin["n_trials"])
    )
)
para(
    "(e) Spatial control. Splitting bouts by starting location, the pre-onset odor is NOT higher for "
    "in-odor bouts (median {} a.u., n = {} bouts) than for out-of-odor bouts (median {} a.u., "
    "n = {} bouts) - in fact it is slightly lower. A genuine odor-triggered process would predict the "
    "reverse.".format(
        f(csp["median_pre_onset_in_odor"]), int(csp["n_bouts_in_odor"]),
        f(csp["median_pre_onset_out_odor"]), int(csp["n_bouts_out_odor"]),
    )
)
para(
    "All three primary conditions fail and both controls point against precedence, so H2 is rejected "
    "(accept_H2 = {}). Because odor is measured independently of the pause and cast that define a "
    "bout, this is a non-circular test: the null is a real negative on odor -> behavior precedence, "
    "not an artifact of the bout definition.".format(bool(H2["accept_H2"]))
)

# ---- Figure ----
doc.add_paragraph()
doc.add_picture(FIG, width=Inches(6.0))
last = doc.paragraphs[-1]
last.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap = doc.add_paragraph()
rc = cap.add_run(
    "Figure F2. Onset-aligned peri-bout signals (pooled Loc1-6; n(bouts) = {}, "
    "n(trials contributing) = {}; vertical line at bout onset, t = 0). (A) Mean onset-aligned "
    "baseline-subtracted ethanol (a.u.) with 95% trial-bootstrap CI, overlaid on the matched "
    "random-time null and the incidental-event curve; the shaded band marks the pre-onset window "
    "[-0.75, -0.25] s tested by H2. The ethanol trace shows no rise approaching onset - it sits at "
    "or below the trial baseline through the pre-onset window (pre-onset median {} a.u. vs baseline "
    "{} a.u.; slope over [-1, 0] s ~ {} a.u./s). (B) Mean onset-aligned COM speed (px/s) and head "
    "angular speed omega (deg/s), showing the locomotor stop at onset accompanied by the head cast "
    "that define the bout - the behavioral signature is clear even though the odor does not lead it. "
    "Shared with the H1 report.".format(
        int(st["figure_curves_meta"]["F2A_eth"]["n_events"]),
        int(st["figure_curves_meta"]["F2A_eth"]["n_trials"]),
        f(med_pre), f(med_base), sci(med_slope),
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
    ("Median pre-onset ethanol, [-0.75,-0.25] s (a.u.)", f(med_pre)),
    ("Median trial baseline ethanol (a.u.)", f(med_base)),
    ("Delta (pre-onset - baseline) (a.u.)", f(delta_pre)),
    ("Wilcoxon pre > baseline, p (one-sided)", p_fmt(pvb["p_greater"])),
    ("Wilcoxon pre > matched null, p (one-sided)", p_fmt(pvn["p_greater"])),
    ("Median onset-aligned slope, [-1,0] s (a.u./s)", sci(med_slope)),
    ("Wilcoxon slope > 0, p (one-sided)", p_fmt(slp["p_greater"])),
    ("Control - incidental pre > baseline, p (one-sided)", p_fmt(cin["p_greater"])),
    ("Control - spatial pre-onset, in-odor (a.u.)", f(csp["median_pre_onset_in_odor"])),
    ("Control - spatial pre-onset, out-of-odor (a.u.)", f(csp["median_pre_onset_out_odor"])),
    ("Contributing trials (primary tests)", str(int(pvb["n_trials"]))),
    ("Accept H2?", str(bool(H2["accept_H2"]))),
]
for k, v in rows:
    c = tbl.add_row().cells
    c[0].text = k
    c[1].text = v

# ============================ Caveats ============================
h("4. Caveats", 1)
para(
    "Non-circular, but modest N and sensor coverage. This test is not confounded by the bout "
    "definition (odor is measured independently of the pause/cast). However only {} of the {} pooled "
    "trials contribute to the primary pre-onset tests: bouts are deliberately rare (achieved median "
    "rate {} /s) and some onsets fall outside ethanol-sensor coverage (NaN odor). The negative result "
    "should be read as 'no detectable pre-onset rise at this N', not proof of an exact zero - though "
    "the incidental-event control (n = {}) shows the same test readily detects a pre-onset rise when "
    "one is present, which argues against a pure power explanation.".format(
        int(pvb["n_trials"]), int(meta["n_pooled_trials"]), f(achieved_rate, 5),
        int(cin["n_trials"]),
    )
)
para(
    "Spatial split is small. The in-odor / out-of-odor comparison rests on {} vs {} bouts; the "
    "direction (in-odor not higher) is consistent with the null, but this stratum is descriptive "
    "rather than powered.".format(int(csp["n_bouts_in_odor"]), int(csp["n_bouts_out_odor"]))
)
para(
    "Single cohort, pixel units. Results are from one pooled cohort (Loc1-6); anotherLoc is held "
    "separate. Kinematics are in raw pixel and pixel/s units (no metric calibration), and ethanol is "
    "on the raw baseline-subtracted scale."
)

# ============================ Reproducibility ============================
h("5. Reproducibility", 1)
para(
    "Objects: data/stats.json (H2 block, figure_curves_meta) and data/bouts.h5 root attributes. "
    "Library version {}, created {} (UTC), seed {}, odor cutoff {}. The figure and this report inject "
    "numbers from these objects; nothing is hardcoded.".format(
        meta["VERSION"], meta["created_utc"], int(meta["seed"]), f(meta["odor_cutoff"], 3)
    ),
    italic=True,
)
para(
    'Rebuild: "%AR_PY%" code\\build_H2_report.py '
    "(with AR_PY = the pinned vras interpreter; the embedded figure "
    "reports\\figures\\F2_peri_bout.png is prebuilt). Output: "
    'reports\\H2 - odor precedes sampling.docx.',
    italic=True,
)

doc.save(OUT)
print("WROTE:", OUT, os.path.getsize(OUT), "bytes")
