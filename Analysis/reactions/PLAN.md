# PLAN — Nose Sweeps & Odor-Guided Search

**Plan version:** 1.0 · **Prepared:** 2026-08-08 · **Architect:** planning-architect (Opus)
**Request:** `requests/requests draft 2 (agent-ready).md` (binding; D1–D13 adopted as-is)
**Prior lessons read:** `Plume locations/learning/LESSONS.md` (rules 1–7) +
`trajectories/learning/LESSONS.md` (rules 8–11). New lessons → `reactions/learning/LESSONS.md`.

Facts marked **[probed]** confirmed by `code/probe_data.py` → `data/_probe.json`.

## 0. Goal & hypotheses (all reported direction-before-significance; nulls headlined)

- **H1** — nose sweeps are prevalent AND temporally associated with ethanol.
  H0: peri-sweep ethanol ≤ time-shuffled null and sweep R ⊥ local ethanol. Tests:
  (a) prevalence = sweep **rate** (sweeps/s) + count/trial [rule 8]; (b) peri-sweep
  baseline-subtracted ethanol in [−0.5,+0.5]s vs matched-count random-time null
  (permutation, seed 1234), paired Wilcoxon (sweep>null); (c) Spearman ρ(R@peak,
  summed peri-sweep ethanol), one point/sweep. **Absolute-amplitude check [rule 9]:**
  peri-sweep ethanol vs real range (~0.14) & noise floor (~4e-4); fraction of sweeps
  with peri-ethanol >0.01. **Accept H1** iff peri-sweep ethanol > null AND ρ>0 with
  CI excluding 0.
- **H2** — COM speed decreases around nose sweeps. H0: during = baseline. Primary:
  per-trial mean v_com in [−0.25,+0.25]s vs trial baseline (median v_com; also ±1s
  window-edge baseline), paired Wilcoxon (during<baseline). **Mandatory circularity
  control [rule 3]:** R=v_nose/v_com, so a COM dip can be definitional. (i) split
  sweeps nose-driven (v_nose>trial median) vs COM-dropout (v_com<trial median);
  (ii) **re-run H2 on the numerator-only (body-frame) sweep set** (D7, no v_com in
  detector); (iii) **headline H2 on that independent test**. **Accept H2** iff v_com
  significantly lower during sweeps *for the numerator-only set*.
- **H3** — sweeps spatially enriched in odor-reached regions beyond occupancy.
  H0: f_sweep = f_occ. Per trial: f_sweep = fraction of sweeps in odor-reached bins;
  f_occ = fraction of all kept head frames in odor-reached bins; within-trial
  permutation null (n_sweeps random frame times, 2000 draws) → stat = f_sweep −
  mean(null). Pooled Wilcoxon (f_sweep>f_occ and f_sweep−null>0). **Accept H3** iff
  significantly enriched beyond occupancy. Note cutoff + amplitude above noise floor.

## 1. Data scope & exclusions [probed]

- 114 infrared trials (lighting excludes nothing). Pooled = **Loc1–6 (105)**;
  **anotherLoc (9) separate** (D10). Accessor-only. Nose = head, COM = body (D1).
- Excluded: loc/duration attrs (all-NaN [probed]); out-of-arena/non-finite;
  de-jump outliers; anotherLoc from pooled; frames outside sensor coverage (NaN eth).

## 2. Shared library `code/reactions_common.py` (imports plume_common; reuses
clean_track advancing-ref de-jump, mad, group_of, pooled_dejump_Q, align_signal)

Adds (all on the **head clock** after cleaning both tracks & interpolating body→head):
- `interp_xy_to_head(head_t, src_t, src_xy)` (np.interp per axis).
- `speed_savgol(xy, dt, win=7, poly=2)` → Savitzky–Golay deriv=1 per axis (delta=dt),
  speed=‖(vx,vy)‖ px/s (D3). Also body-frame nose speed ‖d/dt(head−body_h)‖ (D7).
- `v_floor` = 10th pctile of **pooled** v_com [probed ≈2.89 px/s]; `R=v_nose/max(v_com,
  v_floor)` (D4); report binding fraction [probed ≈9.7%].
- `baseline_subtract_ethanol(eth, eth_t, W=20s, pct=10)` = raw − rolling 10th-pctile
  (reuse Plume drift-removal), then align to head clock (D8); raw a.u. scale.
- `detect_sweeps_R(R, t, height=1.5, prom=0.5, refractory=0.30)` (D5, scipy find_peaks,
  distance=refractory/dt).
- `detect_sweeps_bframe(bframe, t, k=1.5, prom_frac=0.5, refractory=0.30)` (D7):
  height = per-trial median + k·robustSD, prominence = prom_frac·robustSD, where
  robustSD = 1.4826·MAD; refractory 0.30s. (Numerator-only; no v_com.)
- Odor-reached lookup (D9): `load_odor_field(loc)` from `Plume locations/data/
  odor_fields.h5` (read-only); `is_in_odor(field, x, y, cutoff=0.001)` iff the (x,y)
  bin has count≥3 AND max>cutoff. Fallback per trial if a Loc field is missing: head
  within r=100px of source OR baseline-sub ethanol ≥ a stated low threshold; record
  which was used. (All Loc1–6 fields present [probed], so primary applies for pooled.)

**Self-check (before heavy compute):** reuse plume_common self-check; savgol on a
linear ramp → constant speed; R guarded when v_com→0; sweep detector finds a synthetic
peak; odor lookup true/false on a synthetic field; robustSD sane.

## 3. Parameters (justified) [probed]

- Savgol win=7 (~70 ms), poly=2, deriv=1; velocities sane (v_com med 14, v_nose med 23,
  body-frame med 18 px/s) [probed]. De-jump Q body 2.30 / head 2.86; removed 0.41% /
  1.01% (<5% smell test) [probed].
- v_floor 2.89 px/s, binds ~9.7% [probed]. R median 1.17, 90th 4.7 [probed].
- Sweep detector R≥1.5, prom≥0.5, refractory 0.30s → **median 124 sweeps/trial (max
  1238) [probed]** — very high and duration-driven: **report rate (per s), lead with
  rate [rule 8]; treat prevalence honestly** (many are routine nose motion, not
  discrete search sweeps — an editable-threshold caveat).
- Baseline ethanol W=20s, 10th pctile (D8). Windows: peri ±1s (50ms grid) for F1;
  ethanol sum [−0.5,+0.5]s; H2 during [−0.25,+0.25]s (D13).
- Stats: Spearman (heavy-tailed); Wilcoxon paired; CIs by trial bootstrap (2000, seed
  1234); per-test CIs, no family-wise correction; seed 1234.

## 4. Deliverables (paths under `Analysis/reactions/`)

| Artifact | Path |
|---|---|
| Shared lib + scripts + probe | `code/reactions_common.py`, `code/build_sweeps.py`, `code/probe_data.py` |
| Per-sweep + per-trial + stats | `data/sweeps.h5`, `data/sweeps.json`, `data/stats.json` |
| Figures (png+pdf+txt) | `reports/figures/F1_peri_sweep_odor_and_com.*`, `F2A_nose_vs_com.*` (or `F2_scatters.*`), `F2B_nose_vs_summed_odor.*`, `F3_example_trajectory_and_timeseries.*` |
| Reports (docx) | `reports/H1 - nose sweeps and odor.docx`, `reports/H2 - COM slowdown during sweeps.docx`, `reports/H3 - sweeps in odor-reached regions.docx` |
| Plan/audit/notes | `PLAN.md`, `plan.json`, `audit_report.md`, `SESSION_NOTES.md` |
| Lessons | `learning/LESSONS.md` |

`sweeps.h5`: per-sweep (file_name, end_loc, peak_time, R, v_nose, v_com, driver flag,
summed peri-ethanol, in_odor) + per-trial table (sweep count, rate, duration, in-odor
fractions, H2 during/baseline v_com for R-set and numerator-only set) + per-trial
arrays for figures (head/body tracks, R, v_com, baseline-sub ethanol, sweep times).
`stats.json`: every number the reports cite. **Reports inject; never hardcode.** HDF5:
gzip4+shuffle ≥256 elems, .tmp→os.replace, build_complete=1 last, README, seed.

## 5. Acceptance / two gates (§9)

- **Gate 1 (code-verifier, fresh):** accessor-only; advancing-ref clean ≈0.5% (<5%);
  head-clock interp (never reverse); R guarded by v_floor + binding fraction reported;
  sweep params & counts reproduce; **rates alongside counts [rule 8]**; ≥3 numbers/hyp
  re-derived incl. a boundary (sweep count at the default params); seed 1234; zero
  placeholder tokens.
- **Gate 2 (scientific-auditor, independent):** (i) **H2 circularity control present &
  headlined** (numerator-only test); (ii) **absolute-amplitude check [rule 9]** —
  peri-sweep ethanol above noise floor before any odor claim; (iii) raw counts
  exposure-normalized [rule 8]; (iv) velocity convention physical spot-check (R peaks
  ↔ visible nose excursion; sane px/s) [rule 11 analogue]; (v) direction before
  significance; honest nulls. ≤2 revise loops then STOP with SESSION_NOTES.md.

## 6. Task graph

1. [me] plan + `reactions_common.py` (+ self-check).
2. [data-analyst] `build_sweeps.py` → velocities/R/sweeps (R + numerator-only),
   baseline-sub ethanol, odor lookup → per-sweep/per-trial + H1/H2/H3 stats. Slice-first.
3. [fresh code-verifier] Gate 1.
4. [figure+report agents ∥] H1 (F1A+F2B), H2 (F1B+F2A), H3 (F3A+F3B), from saved objects.
5. [fresh scientific-auditor] Gate 2 → audit_report.md.
6. [me] archive → learning/LESSONS.md; SESSION_NOTES.md.

**Invariants:** no self-approval; verifier & auditor fresh/independent; never mark
human-approved; a bounded stop is success (SESSION_NOTES.md).
