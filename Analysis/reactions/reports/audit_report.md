# Scientific Audit (Gate 2) — Nose-Sweeps analysis

**Auditor:** scientific-auditor (fresh, independent context). **Date:** 2026-08-08.
**Scope:** Judge whether the SCIENCE is correct and results support the claims, per
request §9 Gate 2 and PLAN.md §5. All numbers below were re-derived by the auditor
from `data/sweeps.h5` + the reused odor field, not copied from narratives.
Probes: this report's inline commands (no files written to `code/`; all read-only).

## Verdict summary

All three hypotheses are genuine nulls and all three reports headline the null honestly,
direction-before-significance. The H2 circularity control is correctly implemented and
headlined on the non-circular numerator-only detector. The absolute-amplitude and
exposure/rate checks are satisfied. Every re-derived headline reproduced the stored
value to full precision. No BLOCKER or MAJOR findings.

## Independent re-derivations (auditor value vs stored)

| Quantity | Re-derived | Stored (stats.json) | Match |
|---|---|---|---|
| H1b peri-vs-null Wilcoxon | stat=3150.0, p=0.12003 | 3150.0, 0.12003 | exact |
| H1b median obs / null | 0.032335 / 0.029514 | 0.032335 / 0.029514 | exact |
| H1c Spearman rho / p | -0.028090 / 3.362e-05 | -0.028090 / 3.362e-05 | exact |
| H1c CI (trial-bootstrap, seed 1234) | [-0.056508, -0.000280] | [-0.056508, -0.000280] | exact |
| frac peri-eth mean > 0.01 | 0.78623 | 0.78623 | exact |
| peri-eth mean median / p90 | 0.02178 / 0.07321 | 0.02178 / 0.07321 | exact |
| H2 numerator-only (bframe) during / baseline | 41.985 / 17.246 | 41.985 / 17.246 | exact |
| H2 numerator-only Wilcoxon (during<baseline) | stat=5553.0, p=1.0 | 5553.0, 1.0 | exact |
| H2 R-set during / Wilcoxon | 25.964 / stat=4880, p≈1.0 | 25.964 / 4880, ≈1.0 | exact |
| H2 driver split (nose/com/both) | 14432 / 18576 / 11178 | 14432 / 18576 / 11178 | exact |
| H3 trial-37 f_occ / f_sweep | 0.36060 / 0.37500 | 0.36060 / 0.37500 | exact |

## §9 Gate-2 checklist

**1. H2 circularity control (critical) — SATISFIED.** H2 report HEADLINES the
numerator-only body-frame set. `detect_sweeps_bframe` runs on `speed(head - body_h)`
and contains no v_com (verified in `code/reactions_common.py` L103-120). Re-derived
numerator-only during=41.98 vs baseline=17.25 px/s, Wilcoxon during<baseline p=1.0
(COM is HIGHER, not lower). 98.1% of pooled trials have COM faster during bframe
sweeps. `slowdown_survives_numerator_only=False` is correct and reported. The
nose-driven vs COM-dropout split is reported (14432 / 18576 / 11178). The R-set primary
is correctly flagged as potentially definitional: I confirmed v_com@peak median = 2.96
px/s vs 11.15 px/s trial-wide, i.e. the R detector selects low-COM frames by
construction — exactly why the non-circular headline is required. Handled correctly.

**2. Absolute-amplitude check (rule 9) — SATISFIED.** Peri-sweep baseline-subtracted
ethanol (median 0.0218 a.u.) is compared to the real range (~0.14) and noise floor
(~4e-4). Re-derived frac sweeps with peri-eth mean >0.01 = 0.7862 (matches). Report
explicitly states this is above the noise floor but "weak vs ~0.14 range" and does NOT
claim an odor-driven effect (H1b peri-vs-null p=0.120 n.s. is the headline). "Above
floor is necessary but not sufficient" is stated. Correct.

**3. Exposure/rate normalization (rule 8) — SATISFIED.** Sweep RATE (median 1.706/s) is
reported and LED WITH; counts are explicitly labeled duration-driven. The F3 example is
chosen by RATE — I confirmed trial 37 (rate 2.1202/s) is the max-rate pooled trial. The
report does not use counts to claim prevalence without the rate; it argues the high rate
means most events are routine nose motion, not discrete search.

**4. Velocity convention spot-check (rule 11 analogue) — SATISFIED.** v_nose/v_com are
sane px/s (medians ~20/11, tens). On trial 37, 99.5% of R-set peaks are R local maxima
(detector correct). Baseline-sub ethanol pooled range = [-0.323, 0.995] — the RAW a.u.
scale, NOT ethdeconv (~0.14). v_floor guard (2.887 px/s) and binding fraction (9.7%)
are computed and reported. (Note: R peaks coincide with v_com minima, not v_nose
maxima, because R = v_nose/v_com — consistent with the convention, not a defect.)

**5. Stat validity / N-artifact (rules 8/9) — SATISFIED.** H1c Spearman rho=-0.028
(p=3.4e-05). The report LEADS WITH MAGNITUDE ("NEGLIGIBLE… essentially zero… negative,
the opposite of predicted") and states the small p is "an artifact of the enormous
number of sweeps, not a meaningful effect." A dedicated "Tiny-but-significant N
artifact" caveat is present. CI is trial-bootstrap (re-derived exactly). Direction is
reported before significance throughout. Multiple-comparisons posture stated: "per-test
CIs; no family-wise correction across H1-H3."

**6. Result-claim match — SATISFIED.** Spot-checked >3 numbers per docx against
stats.json/h5; all match. One headline per hypothesis re-derived a different way from
the h5 arrays (H1b Wilcoxon from frame peri-matrices; H2 numerator-only from v_com peri
means; H3 f_sweep/f_occ from head track + Loc3 odor field) — all exact. Figure sidecars
(F2A rho=0.459, F2B rho=-0.091) match the report annotations and are explicitly
distinguished from the pre-registered R-based rho.

**7. Conformance — SATISFIED.** Accessor-only (`Aggregate` from
`mouse_arena_aggregate_io`). Advancing-reference de-jump removes 0.50%/0.50%
(head/body), well under 5%; the 0.5% is the intended 99.5th-percentile threshold, not a
cap. Head-clock interpolation via np.interp (never reverses; `align_signal` NaNs outside
coverage). anotherLoc (n=9) all in_pooled=0, excluded from pooled (n=105); Loc1-6 counts
20/18/17/14/17/19 match probe. Seed 1234 confirmed by exact CI reproduction. Zero
placeholder tokens in all 3 docx. odor-reached = count>=3 AND max>0.001 (verified in
`is_in_odor`, L146-167).

**8. Honest nulls — SATISFIED.** All three reports open with an explicit "NOT
supported / null result" verdict, headline the direction (H1 no odor transient; H2 COM
faster not slower; H3 f_sweep < f_occ), and report direction before significance. No
fabricated effect. The single "significant" result (H2 R-set vs ±1s edge baseline,
p=1.6e-17) is honestly explained as an artifact of the window edges sitting on the
fastest part of the peri-trace, not a slowdown — not cherry-picked as support.

## Findings

### MINOR
- **M1 — De-jump accounting differs between probe and final pipeline.**
  `data/_probe.json` reports body/head removal 0.41%/1.01%, while the pipeline's pooled
  99.5th-pct Q yields 0.50%/0.50% (stats.json). Both <5% and scientifically fine; only
  a documentation inconsistency between the probe and the shipped numbers.
  *Fix (optional):* note in SESSION_NOTES that the probe used a different accounting.
- **M2 — H1a median count differs from probe (111 pooled vs 124 all-trials).**
  stats.json H1a median count = 111 (pooled Loc1-6); probe reported 124 (all 114
  trials). This is the correct pooled-vs-all distinction, not an error; reports quote
  111 consistently. Flag only so a reader does not confuse the two.
- **M3 — F2A/F2B annotation CI is bootstrap "over points," not over trials.** This is
  the figure-descriptive Spearman only; the pre-registered H1c inferential CI is
  correctly trial-bootstrap. Reports label the figure statistic as describing the
  plotted cloud, so no overclaim — but the point-bootstrap CI understates uncertainty
  and should not be read inferentially. Reports already say as much.

### Observations (not defects)
- v_com@peak median ~3 px/s for the R-set is definitional (R selects low-COM frames);
  this is precisely the circularity the numerator-only headline neutralizes. Correct.
- H3 within-trial permutation null and pooled Wilcoxons reproduce; direction is against
  enrichment (f_sweep 0.336 < f_occ 0.349), reported honestly.

## Conclusion

The analysis is scientifically sound. The three pre-registered nulls are correctly and
honestly reported, the mandatory H2 circularity control is implemented and headlined on
a detector containing no v_com, the amplitude and rate/exposure normalizations are in
place, and every re-derived headline reproduces the stored value exactly. Only three
MINOR documentation items remain, none affecting any conclusion. Not marked
human-approved.

**VERDICT: PASS**
