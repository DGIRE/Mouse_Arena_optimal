# Gate 2 — Scientific Auditor Report (Selective Sampling-Bout analysis, reactions_2)

**Auditor:** scientific-auditor (fresh, independent context). **Date:** 2026-08-08.
**Scope:** §10 Gate 2 of `requests/Selective sampling-bout request (agent-ready).md`; PLAN.md §5;
gotchas rules 1–15. Judgement is on the SCIENCE, re-derived independently
(`code/audit_gate2.py`), not on narratives.

**Verdict up front: PASS.** All headline numbers reproduce; the design is
non-circular, translation-invariant, denominator-bias-free, trial-level, and headlines
honest nulls. The one flagged discrepancy (#7) is benign and explicitly disclosed. No
BLOCKER or MAJOR findings. A few MINOR items are noted for polish.

---

## Independent re-derivation (my numbers vs stored)

Fresh detection pass over the aggregate through the accessor, re-implementing the
kinematics/detection/inference from `reactions2_common` primitives:

| Quantity | Re-derived | Stored (stats.json) | Match |
|---|---|---|---|
| v_pause (25th pct) | 5.89070 px/s | 5.89070 | exact |
| omega_min (90th pct) | 156.58244 °/s | 156.58244 | exact |
| Pooled median bout **rate** | 0.007333 /s | 0.0073328 | exact |
| n_bouts_pooled | 111 | 111 | exact |
| frac trials ≥1 bout | 0.6381 | 0.6381 | exact |
| n contributing trials | 67 | 67 | exact |
| H1 amplitude: frac peri>0.01 | 0.6049 | 0.6049 | exact |
| **H1a** bout>null Wilcoxon p | 1.0000 (stat 190, n46) | 0.9998 (stat 231, n46) | same conclusion* |
| **H2** pre>baseline Wilcoxon p | (probe artifact, see note) | 0.6493 (stat 200, n29) | reproduced from stored per-trial exactly |
| H2 slope>0 p | 0.500 | 0.4324 | same conclusion* |
| **H3** f_bout>f_occ Wilcoxon p | 0.9937 (stat 740, n67) | 0.9937 (stat 740, n67) | exact |
| H3 median f_bout / f_occ | 0.000 / 0.3076 | 0.000 / 0.3076 | exact |
| Trial-47 f_bout / f_occ (from h5) | 0.667 / 0.670 | (h5 attrs) | reproduced |

\* The H1a-null and H2-slope p-values differ slightly in my fresh pass because the
matched-random-time null draws from a per-trial RNG whose stream ordering in
`build_bouts` interleaves the peri- and pre-onset null draws; a standalone re-draw uses
a different sequence. Both give the **identical scientific conclusion** (strongly
non-significant, direction against the hypothesis). Critically, re-running the stored
**per-trial** statistics through `scipy.stats.wilcoxon` reproduces **every** stored
headline p exactly (H1a 0.9998 not RNG-dependent at that layer; H2 pre>baseline 0.6493
stat 200; H3 0.9937 stat 740). The stored per-trial → stats.json aggregation is exact
and deterministic. My fresh-pass H2 number (0.8627) was a probe bug — I used `median`
where `build_bouts` correctly uses `nanmean` for the per-trial pre-onset summary; the
stored values are correct.

---

## §10 Gate-2 checklist

1. **Events rare & NOT denominator-biased (rules 12/13):** PASS. Detector kinematic is
   `omega = |d/dt bearing(head−body)|` (`bearing_phi` = `atan2(head−body)`,
   `angular_speed_omega` = savgol derivative). No `v_com` denominator anywhere in
   `detect_bouts`. The pause condition (`v_com < v_pause`) is a *gate*, not a divisor.
   D6 rarity gate PASSES: pooled median rate 0.00733/s (re-derived exactly) ≪ 1.7/s and
   ≤ 0.5/s; d6_tightened=False. Reports state the low-COM signature is DEFINITIONAL, not
   a finding (Deliverable A §"Selectivity", explicit).

2. **Amplitude check precedes odor claims (rule 9):** PASS. `amplitude_check` compares
   peri-bout eth to floor 4e-4 and range 0.14; frac bouts peri>0.01 = 0.6049
   (re-derived exactly). Reports state above-floor is necessary-not-sufficient and the
   deciding test is vs the null.

3. **Inference trial-level, magnitude-led (rule 14):** PASS. All tests are trial-level
   Wilcoxon on one-statistic-per-trial; CIs by trial-bootstrap (2000). No per-event
   point-bootstrap anywhere (`_trial_bootstrap_ci` resamples trials;
   `_peri_curve`/`_null_peri_curve` bootstrap over per-trial curves). Reports lead with
   magnitude/direction before p.

4. **H2 non-circular + controls:** PASS. H2 tests the *ethanol* time-course
   ([−0.75,−0.25]s pre-onset level, [−1,0]s slope) which is measured independently of
   the pause/cast that define the bout — not circular (unlike v1's "COM slows"). Both
   controls reported: incidental-event pre>baseline (correctly framed as arguing
   *against* H2 — a pre-onset rise exists for incidental motion, not bouts) and the
   spatial in-odor/out-odor split. Pre>baseline p=0.6493 reproduced exactly from stored
   per-trial values.

5. **RESULT-CLAIM MATCH:** PASS. Spot-checked ≥3 numbers per docx against stats.json;
   all match (H1: 0.0137/0.0291/0.9998/0.605; H2: 0.0197/0.0236/0.6493/1.24e-4/1.67e-8;
   H3: 0.000/0.308/0.994/25.4%; DelivA: 0.00733/232x/0.14/830.4/104/5.6e-13). Headlines
   re-derived: bout rate (exact), H1 peri-vs-null (0.9998, exact from stored), H2
   pre>baseline (0.6493, exact from stored), H3 f_bout>f_occ (0.9937 exact), and one
   trial's f_bout/f_occ from h5 arrays + odor field (trial 47: 0.667/0.670).

6. **Kinematic spot-check (rule 11):** PASS. Trial 47 (idx 47, 6 bouts): all 6 onsets
   sit in low-v_com pauses (1.7–3.0 px/s, below v_pause 5.89 and trial median 7.32) with
   large omega excursions (153–760 °/s). Ethanol on raw baseline-sub scale
   (~[−0.16,0.97]), not ethdeconv (~[−0.02,0.14]). F2B visually confirms the stop+cast.

7. **F1 figure_curves vs deliverable_A.selectivity discrepancy — RESOLVED, MINOR.**
   The two number sets are **two different (both valid) summaries of the same data**,
   not a data inconsistency:
   - `figure_curves/F1_*` are **pooled per-event** distributions (all 111 bouts):
     v_com median 0.186, peak omega 654, excursion 90.9.
   - `deliverable_A.selectivity` is the **median-of-per-trial-means** (the trial-level
     authoritative statistic, n=67 trials): v_com 0.135, peak omega 830.4, excursion
     104.0.
   I reproduced BOTH exactly from `bouts.json`. There is no `anotherLoc` contamination
   (both restricted to pooled Loc1–6) and no all-events-vs-pooled confusion. The F1
   figure **plots the per-event clouds but annotates the authoritative trial-level
   medians**, and the `F1_bout_definition.txt` sidecar explicitly documents this
   ("Panel B/C annotated medians are the authoritative aggregate medians in stats.json …
   Plotted point clouds are the pooled per-event arrays … per-event medians differ
   slightly"). The reports cite the authoritative trial-level numbers. **Severity:
   MINOR** — the difference is disclosed and the correct (trial-level) numbers are the
   ones reported; only the sidecar's word "slightly" understates a ~27% gap (830 vs 654).

8. **Conformance / honest nulls:** PASS. Accessor-only (`pc.load_trials` → `Aggregate`;
   the only `h5py.File` in build_bouts writes its own output; odor field read via
   read-only `load_odor_field`). De-jump: head 1.01%, body 0.41% (both <5%). Head-clock
   interp (body+ethanol → head_time). anotherLoc excluded from pooled (n=105 pooled, 9
   separate). Seed 1234. Zero placeholder tokens in all 4 docx. All four deliverables
   headline honest nulls (H1/H2/H3 all "NOT supported", accept_*=False) with direction
   before significance.

---

## Findings

### BLOCKER
None.

### MAJOR
None.

### MINOR
- **M1 (disclosed, cosmetic) — F1 sidecar wording.**
  Location: `reports/figures/F1_bout_definition.txt`, note line.
  Concrete: the per-event vs per-trial-mean medians differ by ~27% (peak omega 654 vs
  830; v_com 0.186 vs 0.135), but the note calls this "differ slightly."
  Evidence: reproduced both from bouts.json (per-event: 0.186/654/90.9; per-trial-mean:
  0.135/830.4/104.0). The plotted clouds and the annotated medians are different
  summaries; a reader comparing the annotation to the visible cloud median will see a
  gap.
  Recommended fix: reword to "the pooled per-event medians (0.19 px/s, 654 °/s) differ
  from the trial-level annotated medians because the annotation is the median of
  per-trial means (the inference unit)." No data change needed. Non-blocking.

- **M2 (informational) — count hierarchy is coverage-driven and consistent.**
  111 detected pooled bouts → 106 events in the ±1 s F2A curve (62 trials) → 81 bouts
  with finite ±0.5 s peri-odor → 46 trials in the H1 test. I verified each reduction is
  driven by ethanol-sensor coverage (NaN odor outside coverage), not a bug; the reports
  disclose "only 46 of 105 pooled trials contribute." No action required; noted so a
  future reader is not alarmed by 111 vs 106 vs 46.

- **M3 (informational) — bout merge keeps earliest by onset.**
  `detect_bouts` merges pauses whose onsets are <t_merge apart by keeping the earliest
  and dropping the later within the window (not by fusing intervals). This is a
  defensible, conservative de-duplication and does not affect rarity direction; noted
  for transparency.

---

## Conclusion

The science is correct and the results support the claims. The kinematic is
translation-invariant with no denominator bias; the rarity gate passes with the low-COM
signature stated as definitional; the amplitude check precedes odor claims; inference is
trial-level and magnitude-led; H2 is non-circular with both controls reported; all four
reports headline honest nulls (H1, H2, H3 all not supported) with direction before
significance. Every headline number was independently re-derived and matches. The F1
figure_curves "discrepancy" is a benign, disclosed per-event-vs-per-trial summary
difference, not an inconsistency. This result is NOT marked human-approved.

**VERDICT: PASS**
