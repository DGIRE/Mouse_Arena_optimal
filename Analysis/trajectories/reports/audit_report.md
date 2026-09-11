# Gate 2 — Scientific Auditor Report (Trajectory analysis)

**Auditor:** scientific-auditor (fresh independent context) · **Date:** 2026-08-07
**Materials audited:** PLAN.md, request draft 2, LESSONS.md, code/traj_common.py,
code/build_metrics.py, data/stats.json, data/_probe.json, reports/H1–H3.docx, F1–F4.
**Method:** independent re-derivation from the accessor (code/audit_gate2.py,
code/audit_encounters.py), reusing only the *validated* `plume_common.clean_track`
and `plume_common.mad` primitives; all geometry, encounter detection, calibration
and statistics reimplemented from scratch and cross-checked against stats.json.

Interpreter: `"C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe"`.

---

## 1. Independent re-derivation vs stored (all headline numbers)

| Quantity | Re-derived (audit) | Stored (stats.json) | Match |
|---|---|---|---|
| Pooled de-jump Q body / head (px) | 2.29847 / 2.86329 | 2.29847 / 2.86329 | ✓ |
| De-jump removed **mean** body / head | 0.414% / 1.009% | 0.414% / 1.009% | ✓ (≪ 5% smell test) |
| De-jump removed **max** body / head | 5.19% / 28.95% | 5.19% / 28.95% | ✓ (high-motion trials, not a cascade) |
| MAD(quiet) | 1.4363e-4 | 1.4363e-4 | ✓ |
| k-scan FPR (k=5/6/8/10) | 9.48e-5 / 0 / 0 / 0 per s | identical | ✓ |
| Chosen k / threshold | k=5, thr=7.1816e-4 | k=5, thr=7.1816e-4 | ✓ |
| n_encounters pooled median | 28 | 28 | ✓ |
| **H1** ρ(n_enc, tort) | 0.6123, p=3.93e-12, CI[0.454,0.736] | 0.6122, p=3.93e-12, CI[0.454,0.736] | ✓ |
| **H1 exposure-normalized** ρ(enc_rate, tort) | **0.0767, p=0.437, CI[-0.104,0.247]** | 0.0767, p=0.437, CI[-0.107,0.260] | ✓ (CI ±RNG) |
| ρ(n_enc, path_length) | 0.7103, p=2.14e-17 | 0.7103 | ✓ |
| ρ(tort, path_length) | 0.9250, p=4.28e-45 | 0.9250 | ✓ |
| ρ(frac_above, tort) | -0.4189, p=8.7e-6 | -0.4189 | ✓ |
| **H2** Wilcoxon slopes>0 | W=3151, p=0.1194, med slope 0.0202, 64+/41- | W=3151, p=0.1194, 0.0202 | ✓ |
| **H3** paired Wilcoxon post<pre | W=3710, p=0.9985, med pre 70.01 / post 69.66 | W=3710, p=0.9985 | ✓ |
| θ global range | [0.0002°, 179.9999°] | in [0,180] | ✓ |
| Angle sanity: trial 2 near-source median θ | **22.15°** | ~23° [probed] | ✓ |

**Every headline re-derives to the stored value.** The plan/spec is conformed:
geometry on the body track (D1); u=unit(head−body), s=unit(endpoint−body),
θ∈[0,180] (D2–D4); body & signal interpolated onto the head clock (never reverse,
§3.3); Spearman for H1, Wilcoxon for H2/H3; trial replication; anotherLoc excluded
from pooled stats (n=105); seed 1234. Docx table values (H1 per-location, H2 F3 curve,
H3 key numbers) match stats.json exactly. No placeholder tokens in any docx (the only
`<` hits are legitimate math text "post<pre"/"rho<0"). Figures render and are
consistent with the sidecars.

## 2. Confounds / leakage — H1 exposure confound (KEY)

Confirmed and correctly handled. Raw ρ(n_enc, tort)=+0.612 is strongly POSITIVE
(opposite the H1 prediction). Both variables scale with path length
(ρ_n_enc,path=0.710; ρ_tort,path=0.925), and the **exposure-normalized**
ρ(encounter_rate, tort)=+0.077 with CI[-0.104,0.247] **collapses to null (spans 0)**.
The H1 report leads the honest interpretation: headline states H1 "NOT supported,"
foregrounds the path-length exposure artifact, and reports the normalized-null and
frac-above measures. `accept_H1=False`. **Direction reported before significance
throughout. No selective reporting.**

## 3. Direction / nulls — all three headlined honestly

- **H1** not supported (confounded positive; normalized null) — headlined. ✓
- **H2** positive direction but n.s. (W=3151, p=0.119); F3 curve is non-monotonic
  (63.5° @10px → min 44.7° @270px → 80.4° @530px), so the "rises with distance"
  acceptance criterion is not met. Report states "NOT supported," direction first. ✓
- **H3** null (W=3710, p=0.9985; post essentially unchanged/slightly *above* pre).
  Report headlines "NOT supported." ✓

H2 is not driven by a handful of trials (64 positive vs 41 negative slopes; modest
population tendency). H3 uses 105 trial-level pairs.

## 4. Angle convention — correct

θ∈[0,180] globally. Near-source median θ on trial 2 = 22.15° (small θ when the animal
faces the port), confirming u=head−body / s=endpoint−body and correct x/y order.

---

## FINDINGS (ranked)

### MAJOR — Encounter detector fires at the noise floor; "median 28 encounters/trial" is not physically interpretable as odor encounters
**Location:** `traj_common.calibrate_encounter_threshold` + `quiet_baseline_mask`;
threshold=7.18e-4 on ethdeconv (real signal range ~[-0.02, 0.14]); stats.json
`calibration`; reflected in all three reports' encounter counts.

**Evidence (code/audit_encounters.py):**
- Per-trial median ethdeconv ≈ 4.2e-4, i.e. the trace hovers *right around* the
  7.18e-4 threshold; only 2% of trials have a median above threshold.
- **ethdeconv AT detected onsets: median 7.4e-4; 0% of onsets exceed 0.01; 0% exceed
  0.05.** The signal reaches 0.14 (genuine odor excursions) but *no* detected
  "encounter" corresponds to a substantial ethanol value — they are threshold-scraping
  crossings at the noise floor.
- Spatial concentration is weak: onset head–source distance is only mildly enriched
  near the source (median distance percentile 35; 33% in the nearest 20%, but 13% in
  the *farthest* 20%).
- At a physically meaningful threshold on the real deconvolved signal, encounter
  counts are ~0–1/trial (thr=0.005 → median 1; thr=0.01 → median 0), exactly the
  request's original guess. The 28/trial figure is an artifact of the degenerate
  quiet baseline (samples defined as *below their own per-trial median* have a
  minuscule MAD ⇒ threshold below the trace's own noise level) compounded by the
  "smallest-k" rule selecting the most permissive threshold that passes.

**Why this is MAJOR and not a BLOCKER:** unlike the prior run's rule-3 violation, the
noise-floor detector does **not manufacture a spurious positive**. Every
encounter-dependent result is reported as NULL (H1 not supported after normalization;
H3 null p=0.998), and the raw H1 positive is correctly attributed to the exposure
confound, not to odor guidance. So the noise counts inflate N but do not corrupt any
scientific *claim*. The reports do caveat it (H1: "limited dynamic range"; H3:
"contacts may be exposure-driven rather than discrete biological reorientation
events... does not guarantee that each is a distinct, behaviorally salient stimulus").

**However**, this is in tension with the pre-registered framing and with LESSONS rule
3 in substance: the reports present "pooled per-trial n_encounters median = 28" as a
descriptive quantity without stating that these crossings sit at the noise floor
(onset ethdeconv ≈ 7e-4, never near real odor levels ≥0.01), and that a physically
meaningful threshold yields ~0–1/trial. A reader could mistake 28 for 28 real odor
contacts.

**Recommended fix (revision, not re-run of the science):** add one explicit sentence
to the H1 and H3 reports (and the calibration note in stats.json / the F2/F4 captions)
stating that (a) detected onsets occur at ethdeconv ≈ noise floor (median ~7e-4; none
above 0.01), (b) at a threshold matched to the real signal excursions (~0.005–0.01)
the count is ~0–1/trial, and (c) therefore the encounter counts index low-level signal
fluctuation / exposure rather than discrete strong-odor contacts — which is *why* they
must not be over-interpreted and is consistent with the null H1/H3 findings. No
statistics change; the conclusions already stand.

### MINOR — H3 "Direction: post<pre" label is inconsistent with the trial-level test majority
**Location:** stats.json `H3.direction`="post<pre"; H3.docx table "Direction: post<pre".
**Evidence:** the label is set from median(post_trial_means) < median(pre_trial_means)
(69.66 < 70.01). But at the trial-pair level 64/105 pairs have post > pre (paired
Wilcoxon p=0.9985 for "less"), and the report narrative correctly says post is "if
anything, slightly ABOVE pre." The one-word `direction` field therefore contradicts
the inferential majority. **Impact:** cosmetic — the narrative, W, p, and the "NOT
supported" headline are all correct and unambiguous. **Fix:** relabel `direction` to
reflect the paired sign majority (post≥pre) or annotate that the median-of-means and
the paired-sign majority disagree by a fraction of a degree.

### MINOR — "smallest k passing FPR" rule is fragile on a degenerate quiet baseline
**Location:** `calibrate_encounter_threshold` (K_SCAN, "chosen = first k with fpr≤target").
**Evidence:** all four k pass (FPR 9.5e-5 → 0), so the rule returns the *most
permissive* threshold (k=5), which is the noise-floor threshold underlying the MAJOR
finding. The spec did say "smallest k … (≈k=8 expected)"; the analyst followed the
letter of the rule, but the expected k=8 vs actual k=5 divergence is itself a signal
that the quiet baseline is not behaving as the calibration assumed. **Fix:** none
required for correctness of the current (null) conclusions; if the detector is ever
used to support a *positive* claim, re-anchor the quiet baseline (do not condition on
"below own median") and/or add an absolute-signal floor so the threshold sits above
the trace noise level.

---

## Verdict rationale
All numbers re-derive exactly; de-jump, clock alignment, angle convention, statistics
and the H1 exposure-confound handling are correct; all three nulls are headlined
honestly with direction before significance. The single substantive issue (encounter
counts are noise-floor crossings, not odor contacts) does **not** drive any positive
claim and is partially caveated, but the reports should state the noise-floor nature
explicitly so "28 encounters/trial" is not mis-read. This is a bounded, low-risk
documentation revision, not a re-analysis. Per the Gate-2 posture (default to REVISE
when an interpretability concern is unresolved), one revise loop is warranted to add
the encounter-interpretability sentences.

**VERDICT: REVISE**

---

## Re-audit (revision iteration 1)

**Auditor:** scientific-auditor (fresh independent context) · **Date:** 2026-08-07
**Scope:** confirm the three prior findings are CLOSED and nothing regressed. The team
applied documentation/diagnostic fixes only (no claim re-analysis). Numbers below were
re-derived independently from `data/trajectory_metrics.h5` (probes
`code/reaudit_probe.py`, `code/reaudit_docx.py`) — the diagnostics were re-computed from
the stored per-trial `ethd_h`/`onset_idx` arrays and cross-checked against
`stats.json`, not trusted from `build_metrics.py`.

### MAJOR — noise-floor documentation → CLOSED
- **`stats.json.encounter_diagnostics` present and independently reproduced.**
  Re-derived from the h5 (ethd_h at `onset_idx`, pooled Loc1–6, n=105 trials):

  | Quantity | Re-derived (h5) | Stored (stats.json) | Match |
  |---|---|---|---|
  | n_onsets_pooled | 7814 | 7814 | ✓ |
  | **onset_ethd_median** | **7.4511e-4** | 7.4511e-4 | ✓ (exact) |
  | **frac_onsets_above_0.01** | **2.5595e-4** (~0%) | 2.5595e-4 | ✓ (exact) |
  | pertrial_ethd_median_median | 4.3384e-4 | 4.3384e-4 | ✓ |
  | calibrated_threshold | — | 7.1816e-4 | ✓ (= calibration.threshold) |
  | signal_max_ref | — | 0.14 | ✓ |
  | n_encounters_amp @0.01 (min/med/max/mean) | — | 0 / 0.0 / 5 / 0.352 | ✓ |

  All diagnostic fields re-derive to the stored values bit-for-bit.
- **H1 docx** now states the noise-floor nature explicitly (new §3.6 "Encounter
  diagnostics: the calibrated threshold sits at the noise floor"): threshold 7.18e-4 at
  the deconvolved noise floor, per-trial median 4.34e-4, median-at-onset 7.45e-4, real
  odor ~0.14, "only a fraction 2.56e-04 of onsets (~0%) exceed 0.01", and the secondary
  0.01-amplitude re-count "median 0 (min 0, max 5, mean 0.35) … ~0–1 real contacts per
  trial." Frames it as reinforcing the null.
- **H3 docx** now carries the same noise-floor caveat in Methods (~28 onsets/trial index
  noise/exposure crossings; threshold 7.18e-4 same order as noise floor 4.34e-4 and
  median-at-onset 7.45e-4 vs real 0.14; "fraction 2.6e-04 (~0%) exceed 0.01"; secondary
  count "collapse to ~0 (median; max = 5)"), tying it to the observed null.
  All injected numbers match `stats.json`.

### MINOR — H3 direction label → CLOSED
- `stats.json.H3.direction` = **"post>pre"** (was "post<pre"), with `n_pairs_post_gt_pre`
  = 64, `n_pairs_post_lt_pre` = 41 and a `direction_note` clarifying the pooled medians
  are essentially equal (NOT a decrease). Independently re-derived from the h5:
  64 post>pre / 41 post<pre, majority = post>pre — matches. Medians unchanged
  (pre 70.0056 / post 69.6613); Wilcoxon unchanged (W=3710, p=0.9985).
- H3 docx narrative and "Key numbers" table now report Direction = "post>pre" and state
  "the majority direction is post > pre (64 … versus 41 …)"; no wording implies a
  decrease/reorientation.

### MINOR — k-rule fragility note → CLOSED
- `stats.json.calibration.k_selection_note` present: "smallest-k rule returns the most
  permissive threshold on this degenerate (near-silent) quiet baseline; harmless here
  because all encounter-dependent results are null, but should not be used to support a
  positive claim." Both the H1 docx (§3.6) and the H3 docx (Methods) quote this note.

### REGRESSION — none (all headline numbers UNCHANGED)
Re-verified against `stats.json` and (for the diagnostics/H3 direction) the h5:
- **H1** ρ(n_enc,tort)=0.6123 (p=3.93e-12); normalized ρ(enc_rate,tort)=0.0767, p=0.437
  (CI spans 0). ✓
- **H2** Wilcoxon W=3151, p=0.1194; median slope +0.0202 deg/px; 64+/41− slopes;
  F3 non-monotonic (63.5°@10px → 44.7°@270px → 80.4°@530px). ✓
- **H3** paired Wilcoxon W=3710, p=0.9985; median pre 70.01 / post 69.66. ✓
- Calibration k=5, threshold 7.1816e-4, FPR 9.477e-5/s (≤0.05); k-scan {5,6,8,10} intact.
  De-jump removed mean body 0.414% / head 1.009%. θ∈[0.0002°,179.9999°]. anotherLoc
  excluded (pooled n=105, anotherLoc n=9). seed=1234. h5 `build_complete`=1;
  h5 attrs threshold/k/seed match. Zero placeholder tokens in all three docx (only
  legitimate math "<" e.g. "post<pre", "rho<0"). ≥3 numbers/docx spot-checked vs
  stats.json — all match.

**Note (non-blocking):** the H2 docx cites `stats.json` created_utc 2026-08-08T04:20:16Z
while the current file is 04:40:54Z (the diagnostics/H3-direction re-run bumped the
timestamp). Every H2 headline and F3-table value nonetheless matches the current
`stats.json` exactly, so H2 was unaffected — cosmetic timestamp drift only.

### Re-audit verdict
All three prior findings (MAJOR noise-floor documentation; MINOR H3 direction label;
MINOR k-rule note) are CLOSED with independently re-derived evidence. The
`encounter_diagnostics` block reproduces exactly from the h5 (onset_ethd_median
7.4511e-4; frac_onsets_above_0.01 2.5595e-4 ≈ 0%). No claim regressed; every H1/H2/H3
headline number is unchanged. This was a bounded documentation/diagnostics revision as
scoped. Results are NOT marked human-approved.

**VERDICT: PASS**
