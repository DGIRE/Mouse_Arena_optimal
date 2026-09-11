# Scientific Audit (Gate 2) — Plume Locations: Odor-Field Mapping & Signal Enhancement

**Auditor:** scientific-auditor (fresh independent context). **Date:** 2026-08-07.
**Materials audited:** PLAN.md, plan.json, request text, code/plume_common.py,
code/build_odor_fields.py, code/build_enhancement.py, data/odor_fields.h5,
data/odor_field_stats.json, data/enhanced_ethanol.h5, data/enhancement_stats.json,
both .docx reports, all 9 figures. Aggregate read only via the accessor.
Probes written: code/audit_probe.py, audit_probe2.py, audit_probe3.py, audit_read_docx.py.

Nothing here is human-approved. Results are re-derived independently below.

---

## VERDICT: REVISE

The H5 no-fabrication hard gate PASSES (independently re-derived: after FPR ≤ before FPR).
Result↔claim traceability is excellent (every spot-checked number matches the saved
objects; zero placeholder tokens; reports are directionally honest). However there is
one BLOCKER-level plan-conformance/self-consistency defect (the bin-size selection rule
is inverted, and the Task-1 report's justification for it is factually false), plus
MAJOR scientific-validity concerns about what Task-2 "encounters" and "recovery"
actually measure. These are correctable in one scoped iteration; they do not require
discarding the pipeline, so REVISE rather than FAIL.

---

## Independently re-derived numbers vs stored (tolerances noted)

| Quantity | Re-derived | Stored | Match |
|---|---|---|---|
| Groups sum / counts | 114; Loc1..6 = 20/18/17/14/17/19; anotherLoc 9 | same | EXACT |
| Loc endpoint spread | all Loc1–6 = 0.0 px; anotherLoc [219,60] | same | EXACT |
| Q_head (99.5 pctile) | 2.86329 px | 2.86329 | EXACT |
| **T1 Loc1 bin mean[row2,col0]** (raw re-derive) | **0.00035437815** (count 19) | 0.00035437815 | **EXACT** |
| T1 pooled max exp λ | 48.760 px, CI [20.5, 77.0] | 48.760 | EXACT |
| T1 pooled max OLS slope | −0.0053853 /px, CI [−0.00710,−0.00367] | same | EXACT |
| T1 head-vs-body Pearson r | 0.8751 (98 bins) | 0.8751 | EXACT |
| **T2 baseline FPR before** (raw re-derive from H5 traces) | **0.484761 /s** (273 det / 563.2 s) | 0.484761 | **EXACT** |
| **T2 baseline FPR after** (raw re-derive from H5 traces) | **0.482985 /s** (272 det / 563.2 s) | 0.482985 | **EXACT** |
| **H5 GUARD after ≤ before** | **TRUE** (0.482985 ≤ 0.484761) | TRUE | **PASS (hard gate)** |
| T2 overall counts | before 46219 / after 45331 (DECREASE) | same | EXACT |
| T2 distal counts | before 22651 / after 22819 (INCREASE) | same | EXACT |
| T2 gain/lose/tie | 25 / 89 / 0 | same | EXACT |
| T2 per-trial spot-checks (t9,t94,t41) | n_before/after & snr_gain match H5 attrs & stats | same | EXACT |

The H5 hard gate is satisfied on independent recomputation from the stored traces — **not** an automatic FAIL.

---

## Findings (ranked)

### BLOCKER

**B1 — Bin-size selection rule is inverted; the report's justification for L=40 is false.**
- **Location:** `code/build_odor_fields.py::choose_L` (lines ~323–356); Odor field report Methods
  ("All locations resolved to L=40 px … finer bins fail the coverage rule … the largest candidate
  (=fallback) is chosen everywhere").
- **Plan contract (PLAN.md §2, plan.json task1.grid):** scan L ∈ {40,30,25,20,15,10} descending,
  **pick the SMALLEST L for which ≥60% of visited bins have ≥3 contributing trials**; fall back to
  L=40 only if none reach 60%.
- **Concrete failure:** `choose_L` iterates descending and locks in the FIRST L that meets the
  target with `if frac >= COVERAGE_TARGET and chosen is None`. Because L=40 already meets the target,
  it returns L=40 (the COARSEST) at every location — the opposite of "smallest L."
- **Evidence (re-derived, Loc1):** coverage at L=40/30/25/20/15/10 = 0.960/0.942/0.868/0.818/0.719/0.542.
  L=15 (cov 0.719) is the smallest L that satisfies ≥0.60; the plan-conformant choice is **L=15**, not L=40.
  Every location stores `chosen_L=40, L_fallback_used=False`, and coverage at 40 px is 0.85–0.96 — nowhere
  near a fallback condition. The report's claim that "finer bins fail the coverage rule" is contradicted by
  the stored `L_scan` tables in odor_field_stats.json (L=15–30 pass ≥0.60 at all six locations).
- **Impact:** fields are ~2.7× coarser (7×15 bins) than the data support. This inflates per-bin support,
  smooths the spatial gradient, and directly weakens the distance-dependence spatial-scale estimate (λ),
  which is the paper's leading result. The written rationale is not merely suboptimal — it is factually wrong.
- **Fix:** make `choose_L` return the smallest passing L (iterate ascending, or track the min L with
  frac≥target). Re-run Task 1, regenerate fields/figures/report. Re-audit λ and sparseness with the
  finer grid.

### MAJOR

**M1 — Task-2 "encounters" are noise counts, not biological encounters; "recovery" is over a noise-dominated statistic.**
- **Location:** detector calibration in `build_enhancement.py::main` (TARGET_FPR=0.5/s, thr_before=0.01558);
  Figure A; H4 in the enhancement report.
- **Evidence:** per-trial "encounter" counts are min 2 / median 192 / max 1985 on trials of only tens of
  seconds; totals are 46,219 before / 45,331 after across 114 trials. Figure A shows the before trace is
  dense high-frequency noise carpeted with hundreds of "after" detections. The "matched FPR" itself is
  0.485/s on the *quiet, far-from-source* baseline — i.e. the detector fires roughly every 2 s even where
  the plan defines the signal as absent. A statistic where the null/quiet region already produces ~0.5
  detections/s is not measuring discrete stereotyped ethanol encounters.
- **Why it matters:** H4's Wilcoxon "recovery" (distal +168 of 22,651 = +0.7%; overall −1.9%) is a
  difference between two very large noise-count distributions. The p-values (1.9e-6 etc.) reflect the huge
  N of noise crossings, not a biologically meaningful recovery of distal odor contacts. The pre-registered
  target FPR was never justified against a real false-positive definition; 0.5/s is implausibly permissive.
- **Fix:** define FPR against a plausible encounter rate (e.g. detections/min, or calibrate to a target
  count consistent with expected encounter density), tighten prominence/threshold so quiet-baseline
  detections approach ~0, and re-test H4 on counts that are physically interpretable. State the expected
  order-of-magnitude of true encounters per trial.

**M2 — The Task-2 core deliverable ("most improved distal SNR"/"recover distal encounters") is essentially not achieved.**
- **Location:** `distal_snr_gain` computation (`finalize_trial`); Figure A ("Top-10 most improved").
- **Evidence (re-derived):** distal SNR gain is **negative for 106 of 114 trials** (only 8 positive;
  min −18.80, max +2.18). The "top-10 most improved" panel therefore includes two trials with **negative**
  gain (−0.82, −0.92). Enhancement *degrades* distal SNR in 93% of trials.
- **Why it matters:** the request's stated Task-2 goal is to *recover small distal encounters* and show the
  *most improved distal SNR*. The saved results show the opposite for almost all trials. The report is
  honest that the SNR gain is "a cross-trial ranking, not an absolute delta" and that before/after live on
  different scales — but that caveat concedes the SNR-gain metric is not comparing like with like
  (drift-corrected raw amplitude vs. a unit-energy matched-filter correlation score in [−1,1]). An SNR
  "gain" computed across incommensurable scales is not a valid SNR improvement measure.
- **Fix:** compute before/after SNR on commensurable quantities (e.g. both on amplitude-calibrated traces,
  or report matched-filter detection sensitivity at fixed FPR rather than an amplitude-SNR delta). If the
  method genuinely does not improve distal SNR, say so as the headline result.

**M3 — H1 sparseness null is trivial (not a real null).**
- **Location:** `sparseness_stats` → `gini_uniform_null = pc.gini(np.ones(n_valid))`; H1 in report.
- **Evidence:** the "uniform-map null" Gini is `gini(ones)=0.0` by construction, so "Gini 0.139 > null 0.000"
  is vacuous. The plan asked for "Gini of a same-N uniform field" as the null, which is what was coded, but
  a constant field's Gini is analytically 0 with no sampling variability — it provides no significance
  statement, only a directional floor. The report does acknowledge the departure "is small in magnitude,"
  which is appropriately hedged, so this is MAJOR (weak test) not a fabrication.
- **Fix:** use a permutation/Poisson-sampling null (redistribute the observed total odor mass uniformly
  across the same N bins with realistic per-bin sample counts, recompute Gini many times → null
  distribution + CI), so H1 has an actual comparison with uncertainty.

### MINOR

**m1 — Report slightly over-generalizes max-OLS significance.** The report says OLS slopes are "negative and
significant … at most single locations," but Table 1 shows Loc4 CI [−0.00396, +0.00108] includes 0
(not significant). "Most" is defensible (5 of 6 exclude 0) but should explicitly note Loc4 as the exception.
Direction is otherwise correctly reported.

**m2 — Multiple-comparisons not addressed.** Six per-location distance fits + several Spearman tests are
reported without any correction or a stated family. Given the plan emphasized per-location + pooled with CIs
(not a single omnibus test) this is acceptable, but a one-line statement (CIs are per-test, no MC correction)
would be more rigorous.

**m3 — Per-location exp-decay λ for the mean field is degenerate** (e.g. Loc1 λ=2.41e6 px with an
absurdly tight SE) and is tabled with a "None (diluted)/completeness" caveat. Correctly flagged as
unreliable in the report, so informational only — but such non-physical values should be suppressed
(reported as NA) rather than printed as numbers.

**m4 — Plan/report say the drift-window autocorrelation "justifies" nothing** (median 1/e time 0.61 s,
W=20 s). The report is transparent that W is a pre-registered band choice and explicitly does *not* claim
the 0.61 s number justifies W. Honest, but the 20 s window vs a 0.61 s raw-autocorrelation time is never
validated against the actual *drift* timescale on any trial (plan risk item #3 asked for a 2–3 trial visual
residual check). No such validation artifact is present.

---

## Confounds / leakage / convention checks (all PASS)
- **Unit/scale:** Task-1 uses ethdeconv (global range re-derived ~[−0.022, 0.138]) with a data-derived MAD
  cutoff; Task-2 threshold 0.01558 is compared to drift-corrected RAW (raw range ~[−0.28, 1.0]), NOT to
  ethdeconv. No cross-scale leakage. PASS.
- **Map convention:** row=y, col=x, 0-based; verified in code (`bin_indices`) and in field_Loc1.png
  (endpoint white X at (474,61) sits on the max-map hotspot). PASS.
- **Endpoint marker / masking:** masked bins render blank (white), endpoint marked, 4 stacked panels,
  jet colormap, units labeled. PASS.
- **Exclusions:** anotherLoc excluded from the 6 fields and from the pooled set (pooled n=105, re-derived),
  reported separately; out-of-arena and out-of-coverage samples dropped; loc/duration attrs unused. PASS.
- **De-jump:** advancing-reference global Q (no cascade); Q_head=2.863 px re-derived exactly. PASS.
- **HDF5 contracts:** both files open on fresh h5py read, `build_complete=1`, documented groups/attrs
  present. PASS.
- **Reproducibility:** seed 1234 recorded; exact commands in both reports; numbers injected from result
  objects; zero placeholder tokens ({{,}},placeholder,TODO,XXX,FIXME,TBD) in either docx. PASS.

## Honest-directionality checks (PASS)
- Task-2 report states plainly: overall encounter count DECREASES (45331 < 46219) at matched FPR while the
  distal subset INCREASES (22819 > 22651); does not overclaim net recovery; H4 acceptance (counts +
  matched-FPR + distal/proximal split) is presented. PASS (directional honesty), subject to M1/M2 on what
  the counts mean.
- Task-1 report discloses mean-field dilution (OLS-log(mean) unavailable at all locations) and LEADS with
  the max-field distance result (λ≈49 px). PASS.

---

## Recommended scoped re-plan (≤1 iteration)
1. **[BLOCKER B1]** Fix `choose_L` to return the smallest passing L; re-run build_odor_fields.py; regenerate
   fields, figures, and the Task-1 report; re-derive λ/sparseness. Correct the false "finer bins fail" text.
2. **[M1/M2]** Recalibrate Task-2 detection to a physically meaningful FPR (approach 0 on quiet baseline),
   and either (a) report distal recovery on counts that are interpretable, or (b) headline that the method
   does not improve distal SNR (106/114 negative). Put before/after SNR on commensurable scales.
3. **[M3]** Replace the trivial uniform-null with a sampling/permutation null + CI for H1.
4. **[m1–m4]** Note Loc4 non-significance; state MC posture; suppress degenerate mean-λ values; add the
   2–3-trial drift-window residual validation the plan promised.

**VERDICT: REVISE**

---

## Re-audit (revision iteration 1)

**Auditor:** scientific-auditor (fresh independent context). **Date:** 2026-08-07.
Re-derived independently via `code/reaudit_probe.py` (FPR from stored H5 traces; choose_L
from the accessor), `code/reaudit_docx.py` (report text/tokens), plus direct JSON checks.
Nothing here is human-approved.

### H5 no-fabrication hard gate (re-derived from stored traces)
Recomputed the pooled quiet far-from-source baseline segments directly from
`enhanced_ethanol.h5` (`drift_corrected`/`enhanced`/`head`/`endpoint`), re-derived
head-endpoint distance, and re-ran the detector at the **stored** thresholds
(thr_before=0.046802, thr_after=0.323308):

| Quantity | Re-derived | Stored | Match |
|---|---|---|---|
| baseline FPR **before** | **0.031962 /s** (18 det / 563.2 s) | 0.031962 | EXACT |
| baseline FPR **after** | **0.028411 /s** (16 det / 563.2 s) | 0.028411 | EXACT |
| both ≤ 0.05/s | TRUE | — | **PASS** |
| **after ≤ before** | **TRUE** (0.028411 ≤ 0.031962) | TRUE | **PASS (hard gate)** |

H5 guard holds on independent recomputation → **not** an automatic FAIL.

### Findings status
- **B1 (was BLOCKER) — CLOSED.** `choose_L` now collects all L meeting the ≥60%/≥3-trial
  rule and returns `min(passing)` (finest). Independently re-derived coverage-vs-L:
  Loc1 {40:.960, 30:.942, 25:.868, 20:.818, 15:.719, 10:.542} → smallest passing **L=15**
  (matches stored `chosen_L=15`); Loc6 {40:.961, 30:.971, 25:.942, 20:.930, 15:.834,
  10:.679} → smallest passing **L=10** (matches stored `chosen_L=10`). Loc2–5 & anotherLoc
  store L=15, all `L_fallback_used=false`. Maps are finer: Loc1 mean grid (19×39) and Loc6
  (28×58) vs the prior 7×15. Report Methods now reads "choose the SMALLEST L … L=40 px is
  only a fallback … finer grids clear the rule at every location"; the false "finer bins
  fail"/"largest candidate" text is gone.
- **M1 — CLOSED.** BEFORE threshold = k·MAD(quiet baseline); k scanned {5,6,8,10}, smallest
  k with quiet-FPR ≤0.05 selected → **k=8**, thr_before=0.046802, quiet-FPR=0.0320/s (stored
  k_scan corroborated: k=5→0.114, 6→0.073, 8→0.032, 10→0.000). AFTER matched to the same low
  FPR (0.0284/s). Both physically meaningful and after≤before (see gate table). Per-trial
  counts dropped to a plausible range: n_before min0/median74/max1954 (was min2/median192);
  overall before totals 25651 (was 46219). Report cites 0.0320/s and the 16× reduction.
- **M2 — CLOSED.** distal_snr_gain is dimensionless peak/local-MAD each trace; stored record
  **27 positive / 87 negative** (0 zero), min −6.66 / median −1.45 / max +3.01 — the median
  is negative. The top-10 Figure-A trials all have positive gain (min 2.279; re-derived from
  stats). Report headline is "null / negative result" and states the method "does NOT improve
  distal SNR for most" trials and does not recover distal encounters; it also retains the
  cross-scale caveat. Honest.
- **M3 — CLOSED.** `gini_mc_null` present at every location and pooled with `null_gini_mean`,
  `null_gini_ci95`, `null_gini_std`, `pvalue`, `n_draws=2000`, `seed=1234`. Pooled: observed
  Gini 0.155 vs null mean 0.037, CI [0.035, 0.039], p=0.00. The report H1 and headline cite
  the MC null (mean/CI/p). The trivial `gini(ones)=0` floor is retained but explicitly
  labeled "Analytic floor only … significance comes from the Monte-Carlo null."
- **m1 — CLOSED.** Report: "max-OLS slope CI INCLUDES 0 (not significant) at: Loc4." Verified
  stored Loc4 max-OLS CI [−0.00237, +0.0000628] includes 0.
- **m2 — CLOSED.** "MULTIPLE-COMPARISONS POSTURE: … per-test … no family-wise correction …
  direction reported before significance."
- **m3 — CLOSED.** Degenerate exp-decay fits (λ non-finite/≤0/>arena-diagonal/no SE) return
  `lambda=null` with `degenerate_reason`; report reports mean-field λ as NA where flagged and
  leads with the MAX field.
- **m4 — CLOSED.** `data/drift_validation.json` exists (3 example trials): slow-trend slope
  reduced (e.g. 8.69e-5→2.48e-5, ×3.5) with fast encounter-band variance retained (≈1.000);
  report has the residual-validation section.

### Regression statement
No regression. Independently re-confirmed: fields & enhancement HDF5 both open on fresh h5py
read with `build_complete=1`; 6 fields + anotherLoc (7 groups) present, anotherLoc excluded
from the pooled set (pooled n=105); T2 threshold (0.046802) is on the drift-corrected RAW
scale (raw a.u.), not ethdeconv — no cross-scale leakage; map convention row=y/col=x preserved
in code (`bin_indices`) and H5 README; zero placeholder tokens ({{,}},placeholder,TODO,XXX,
FIXME,TBD) in either docx; seed=1234 and exact run commands present. Spot-checked ≥3 numbers
per docx against saved objects, all EXACT: (odor) pooled Gini 0.155, pooled max-OLS slope
−0.00300 / CI [−0.00359,−0.00241], head-vs-body r=0.600 (n=1310), pooled centroid (482.3,
115.9), Spearman tort-vs-frac-above ρ=−0.532/CI[−0.656,−0.378]/n=105; (enhancement) FPR
before 0.031962 / after 0.028411, k=8 / baseline_MAD 0.005850, counts 25651→23084 and
distal 12269→11536, 27/87 gain split.

**VERDICT: PASS**
