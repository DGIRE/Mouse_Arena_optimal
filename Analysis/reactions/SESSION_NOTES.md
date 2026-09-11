# SESSION NOTES — Nose-Sweeps / Reactions autonomous run

**Date:** 2026-08-08 · **Status:** COMPLETE — PASSED Gate 1 (code) and Gate 2 (science,
first audit, no revision needed). Not human-approved (no human sign-off).

## What ran (pipeline)
probe → plan (v1.0) → shared lib (`reactions_common.py`, reusing `plume_common` +
Plume `odor_fields.h5`) → analyze (`build_sweeps.py`) → **Gate 1 code-verifier: PASS**
→ figures (F1, F2A, F2B, F3) + 3 reports → **Gate 2 auditor: PASS** → archive.

## Headline results (all numbers from saved objects; ALL THREE HYPOTHESES NULL)
- **H1** (nose sweeps ↔ ethanol): **NOT supported.** Sweeps prevalent but the rate
  (median 1.71/s, ~111/trial, 21,841 pooled) is duration-driven and mostly routine
  nose motion. Peri-sweep baseline-subtracted ethanol NOT above the matched random-time
  null (Wilcoxon p=0.120; obs 0.032 vs null 0.030). Sweep-magnitude↔odor Spearman
  ρ=−0.028 [−0.057,−0.0003] — negligible & negative (the small p=3.4e-5 is an N
  artifact of 21,841 sweeps). Amplitude: peri-eth median 0.022, 78.6% >0.01, above the
  ~4e-4 floor but small vs the ~0.14 range.
- **H2** (COM slows during sweeps): **NOT supported — opposite holds.** COM is *higher*
  during sweeps on both detectors; headlined on the non-circular numerator-only
  (body-frame) set: during 42 vs baseline 17 px/s, Wilcoxon during<baseline p=1.0.
  Circularity split: nose-driven 14,432 / COM-dropout 18,576; the R-detector
  preferentially fires on low-COM frames (v_com@peak ≈3 vs ≈11 px/s) — which is exactly
  why the numerator-only headline was required. `slowdown_survives_numerator_only=False`.
- **H3** (sweeps in odor-reached regions): **NOT supported.** f_sweep 0.336 ≈ f_occ
  0.349 (Wilcoxon p=0.150; 54% of trials enriched ≈ chance) — sweeps track occupancy,
  not odor-reached bins (reused Plume odor field, cutoff 0.001).

## Method integrity (verified independently at both gates)
Accessor-only; nose=head/COM=body on the head clock (body & ethanol interpolated onto
it, never the reverse); advancing-reference de-jump 0.50%/0.50% (<5% smell test);
Savitzky–Golay velocities (win7 poly2), sane px/s; v_floor 2.89 px/s (binds 9.7%),
R=v_nose/max(v_com,v_floor); R-sweep detector (height 1.5, prom 0.5, refractory 0.30s)
AND numerator-only body-frame detector; baseline-subtracted ethanol = raw − rolling
10th-pctile W=20 s (raw scale, not ethdeconv); odor-reached = Plume field bin count≥3 &
max>0.001; unit=trial; anotherLoc (9) excluded from pooled (n=105); seed 1234.
Gate 1 re-derived sweep counts (3 trials) and all H1/H2/H3 numbers exactly; Gate 2
re-derived one headline per H exactly and confirmed the circularity/amplitude/rate
checks. Gate-2 MINORs (3) were documentation-only, no effect on conclusions.

## Outputs (under `Analysis/reactions/`)
- `PLAN.md`, `plan.json`, `reports/audit_report.md` (VERDICT: PASS),
  `learning/LESSONS.md` (new rules 12–15 + repo-level all-null observation).
- `data/sweeps.h5` (114 trial groups + /sweeps table, build_complete=1),
  `data/sweeps.json`, `data/stats.json`, `data/_probe.json`.
- `reports/H1 - nose sweeps and odor.docx`, `reports/H2 - COM slowdown during
  sweeps.docx`, `reports/H3 - sweeps in odor-reached regions.docx` (all placeholder-free).
- Figures: `reports/figures/F1_peri_sweep_odor_and_com.*`, `F2A_nose_vs_com.*`,
  `F2B_nose_vs_summed_odor.*`, `F3_example_trajectory_and_timeseries.*` (png+pdf+txt).
- Code: `code/reactions_common.py`, `build_sweeps.py`, `probe_data.py`, figure/report
  builders, `verify_gate1.py`, audit probes.

## Environment
Interpreter (`$AR_PY` NOT set in this shell; used full path):
`C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe`. Seed 1234.
MPLBACKEND=Agg. Data read-only via `mouse_arena_aggregate_io.Aggregate`. Reused
(read-only) `Plume locations/data/odor_fields.h5`.

## Reproduce (from `C:\Projects\Repos\Mouse Arena\Analysis\reactions`)
```
AR_PY="C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe"
"$AR_PY" code/build_sweeps.py        # -> data/sweeps.{h5,json}, stats.json
"$AR_PY" code/build_h1_figures.py ; "$AR_PY" code/build_h1_report.py
"$AR_PY" code/_build_F2A.py ; "$AR_PY" code/_build_H2_report.py
"$AR_PY" code/make_F3.py ; "$AR_PY" code/make_H3_report.py
```

## Scope / caveats
Single infrared cohort, 114 trials; uncalibrated a.u.; pixels. anotherLoc (9) separate,
excluded from pooled. All three hypotheses null — reported honestly; the fourth
consecutive all-null analysis in this repo (see LESSONS repo-level observation).
```
