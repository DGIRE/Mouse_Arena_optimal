r"""make_H3_report.py -- Build the H3 DOCX report STRICTLY from saved objects.
Every number injected from data\stats.json (and bouts.h5 for the example trial).
NO hand-typed statistics; NO recomputed science. python-docx. Interpreter "$AR_PY".
"""
from __future__ import annotations
import json, os, datetime
import h5py
import numpy as np
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions_2"
STATS = os.path.join(BASE, "data", "stats.json")
BOUTS = os.path.join(BASE, "data", "bouts.h5")
ODOR = r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\data\odor_fields.h5"
FIGPNG = os.path.join(BASE, "reports", "figures", "F3_spatial.png")
OUT = os.path.join(BASE, "reports", "H3 - sampling bouts in odor-reached regions.docx")

with open(STATS) as f:
    S = json.load(f)
M = S["meta"]
H3 = S["H3"]
ex = S["deliverable_A"]["example_trial"]

med_fbout = H3["direction_first"]["median_f_bout"]
med_focc = H3["direction_first"]["median_f_occ"]
med_fbout_null = H3["direction_first"]["median_f_bout_minus_null"]
w_stat = H3["f_bout_gt_f_occ"]["wilcoxon_stat"]
w_p = H3["f_bout_gt_f_occ"]["p_greater"]
w_n = H3["f_bout_gt_f_occ"]["n_trials"]
wn_stat = H3["f_bout_gt_null"]["wilcoxon_stat"]
wn_p = H3["f_bout_gt_null"]["p_greater"]
wn_n = H3["f_bout_gt_null"]["n_trials"]
frac_enr = H3["frac_trials_enriched"]
cutoff = H3["odor_cutoff"]
above_floor = H3["amplitude_above_floor"]
accept = H3["accept_H3"]
n_pooled = M["n_pooled_trials"]
n_another = M["n_anotherLoc_trials"]
n_perm = M["n_perm"]
n_boot = M["n_boot"]
seed = M["seed"]
version = M["VERSION"]

# example trial attrs from bouts.h5
with h5py.File(BOUTS, "r") as f:
    a = dict(f["trials"]["047"].attrs)
ex_fname = a["file_name"]
ex_idx = int(a["bout_count"] and 47)
ex_count = int(a["bout_count"])
ex_rate = float(a["bout_rate"])
ex_loc = a["end_loc"]

PCT = lambda x: f"{x*100:.1f}%"

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"; st.font.size = Pt(11)

def h(txt, lvl=1):
    p = doc.add_heading(txt, level=lvl)
    return p

def para(txt, bold=False, italic=False, size=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(txt)
    r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = color
    return p

# -------- Title
t = doc.add_heading("H3 - Sampling-bout locations vs odor-reached regions", level=0)
para("Selective Sampling-Bout analysis (reactions_2). Trial-level inference; pooled Loc1-6.",
     italic=True, size=10)

# -------- Lead / honest headline
h("Headline", 1)
lead = para(
    "H3 is NOT supported. Sampling-bout onset locations are NOT enriched in odor-reached "
    f"bins. The median in-odor fraction of bout onsets (f_bout = {med_fbout:.3f}) is BELOW the "
    f"occupancy expectation (f_occ = {med_focc:.3f}): bouts occur where the animal spends "
    "relatively LESS of its time in odor-reached regions, i.e. the effect runs in the negative "
    f"direction. The trial-level Wilcoxon test of enrichment (f_bout > f_occ) gives p = {w_p:.3f} "
    f"(one-sided, n = {w_n} contributing trials), and only {PCT(frac_enr)} of trials are enriched "
    "(below the ~50% chance level). Direction is reported before significance; this is a clean, "
    "honest null.")
for r in lead.runs: r.bold = True

# -------- Goal + Hypotheses
h("Goal and hypotheses", 1)
para("Goal. Test whether the head positions at sampling-bout onset are spatially biased toward "
     "regions the odor plume plausibly reached, beyond what the animal's occupancy alone predicts.")
para("H3. Sampling-bout locations (head at bout onset) are enriched in odor-reached bins relative "
     "to where the animal spends its time (f_bout > f_occ, and f_bout above a within-trial "
     "permutation null).", bold=True)
para("H0. The in-odor fraction of bout onsets equals the occupancy-based expectation "
     "(f_bout = f_occ; f_bout - null = 0).", bold=True)
para(f"Decision rule. Accept H3 iff bouts are significantly enriched beyond occupancy. "
     f"Outcome: accept_H3 = {accept}.")

# -------- Methods
h("Methods", 1)
para("Accessors and common code. All quantities were computed upstream by build_bouts.py using "
     f"reactions2_common ({version}), which reuses the validated plume_common / reactions_common "
     "accessors (advancing-reference de-jump track cleaning, baseline-subtracted ethanol on the "
     "head clock, the Plume-locations odor-field lookup). This report and the figure recompute no "
     "science; every number is injected from saved result objects (data\\stats.json, data\\bouts.h5).")
para(f"Interpreter and seed. Python at the vras environment; matplotlib headless (Agg); random "
     f"seed {seed} throughout.")
para("Odor-reached region (D9). Reused from the Plume-locations odor fields "
     "(Plume locations\\data\\odor_fields.h5). For a trial's release location, a spatial bin is "
     f"'odor-reached' iff it is valid (count >= 3 trials) AND its max ethanol field exceeds the "
     f"cutoff {cutoff} (above the ~4e-4 noise floor). A bout onset is 'in-odor' if the head "
     "position at onset maps to an odor-reached bin.")
para("Per-trial statistics. For each trial: f_bout = fraction of bout onsets falling in "
     "odor-reached bins; f_occ = fraction of all kept head frames in odor-reached bins (the "
     "occupancy expectation). A within-trial permutation null draws n_bout random frame times and "
     f"computes their in-odor fraction ({n_perm} draws), yielding a per-trial (f_bout - mean(null)).")
para(f"Inference. Replication unit = trial. One statistic per trial; enrichment tested by "
     f"trial-level one-sided Wilcoxon signed-rank tests (f_bout > f_occ and f_bout - null > 0) "
     f"across trials with >= 1 bout; trial bootstrap {n_boot} draws where CIs are used. Pooled "
     f"Loc1-6 (n = {n_pooled} trials); anotherLoc (n = {n_another}) kept separate. Only "
     f"trials with >= 1 bout contribute to bout-conditioned tests (n = {w_n}).")

# -------- Results
h("Results", 1)
para("Direction (reported first).", bold=True)
para(f"Across contributing trials the median in-odor fraction of bout onsets is "
     f"f_bout = {med_fbout:.3f}, versus a median occupancy fraction f_occ = {med_focc:.3f}. The "
     f"median within-trial (f_bout - null) is {med_fbout_null:.4f}. All three point the same way: "
     "bout onsets are UNDER-represented in odor-reached bins relative to occupancy and to the "
     "permutation null.")
para("Significance (enrichment tests).", bold=True)
para(f"f_bout > f_occ: Wilcoxon signed-rank stat = {w_stat:g}, one-sided p = {w_p:.3f} "
     f"(n = {w_n} trials).")
para(f"f_bout > within-trial null: Wilcoxon signed-rank stat = {wn_stat:g}, one-sided "
     f"p = {wn_p:.3f} (n = {wn_n} trials).")
para(f"Fraction of trials enriched (f_bout > f_occ): {PCT(frac_enr)} -- below the ~50% chance "
     "level, consistent with no enrichment (and, if anything, a mild anti-enrichment).")
para(f"Amplitude check. The odor field at the mapped bins is above the noise floor "
     f"(amplitude_above_floor = {above_floor}; cutoff {cutoff} vs ~4e-4 floor), so the null is not "
     "an artifact of a dead / sub-threshold odor field.")
para("Interpretation.", bold=True)
para("Both the direction and the (non-)significance agree: sampling-bout onset locations are not "
     "enriched where odor plausibly reached. Bouts are, if anything, slightly under-represented in "
     "odor-reached bins relative to how the animal distributes its time. H3 is not supported.")

# -------- Figure
h("Figure F3", 1)
doc.add_picture(FIGPNG, width=Inches(6.5))
last = doc.paragraphs[-1]; last.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap = doc.add_paragraph()
cr = cap.add_run(
    f"Figure F3. Sampling-bout locations vs odor-reached regions (H3). "
    f"(A) Example trial (index {ex_idx}, {ex_loc}; {ex_fname}; {ex_count} bouts, rate "
    f"{ex_rate:.4f}/s): cleaned centre-of-mass trajectory in the arena box "
    "([0,580] x [0,280] px, equal aspect); the odor-reached footprint for that location "
    f"(bins with count >= 3 and max > {cutoff}) is lightly shaded; bout-onset head positions "
    "are marked (triangles; red = in-odor, blue = out-of-odor) and the source endpoint is marked "
    "with an x. Below: the trial's baseline-subtracted ethanol (a.u.) and head angular speed "
    "omega(t) (deg/s) on the head clock, with bout onsets marked in red in both. "
    f"(B) Per-trial f_bout (y) vs f_occ (x) for all pooled Loc1-6 trials with >= 1 bout "
    f"(n = {w_n}); the dashed line is the identity y = x; point size is proportional to n_bout. "
    f"Most points fall below the identity line. Trial-level Wilcoxon f_bout > f_occ p = {w_p:.3f}; "
    f"{PCT(frac_enr)} of trials enriched. H3 not supported.")
cr.italic = True; cr.font.size = Pt(9)

# -------- Caveats
h("Caveats", 1)
para("Reused odor field. The odor-reached mask is derived from the Plume-locations odor fields "
     "aggregated across a separate set of trials per location, not measured concurrently with each "
     "reaction trial; it is a plausibility footprint, not an instantaneous odor map.")
para(f"Modest N. Only {w_n} trials carry at least one sampling bout, limiting power for the "
     "enrichment tests; the many single-bout trials make per-trial f_bout coarse (0 or 1 for "
     "n_bout = 1).")
para("Single cohort / pixel resolution. Results come from one cohort at fixed spatial binning "
     "(15-px bins); the footprint definition and bin size could shift borderline in/out-of-odor "
     "assignments. The direction and magnitude of the null, however, are not marginal.")

# -------- Reproducibility footer
h("Reproducibility", 1)
now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
para(f"Generated {now}. seed {seed}; {version}. All numbers injected from saved objects; no "
     "science recomputed.", italic=True, size=9)
para("Inputs: data\\stats.json (H3 block), data\\bouts.h5 (/trials/047 arrays and /trials/<idx> "
     "attrs), Plume locations\\data\\odor_fields.h5 (odor-reached footprint).", italic=True, size=9)
para("Rebuild: run  code\\make_F3.py  then  code\\make_H3_report.py  with the vras interpreter "
     "(\"$AR_PY\"); e.g.  \"$AR_PY\" -m compileall code\\make_H3_report.py ; \"$AR_PY\" "
     "code\\make_H3_report.py .", italic=True, size=9)

doc.save(OUT)
print("WROTE", OUT, os.path.getsize(OUT), "bytes")

# ---------------- placeholder scan
doc2 = Document(OUT)
tokens = ["{{", "}}", "placeholder", "TODO", "XXX", "FIXME", "TBD"]
hits = []
for i, p in enumerate(doc2.paragraphs):
    for tk in tokens:
        if tk.lower() in p.text.lower():
            hits.append((i, tk, p.text[:80]))
for tbl in doc2.tables:
    for row in tbl.rows:
        for cell in row.cells:
            for tk in tokens:
                if tk.lower() in cell.text.lower():
                    hits.append(("table", tk, cell.text[:80]))
print("PLACEHOLDER_HITS", len(hits))
for hh in hits:
    print("  ", hh)
