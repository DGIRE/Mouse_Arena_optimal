# PLAN — Trajectory Structure & Odor-Guided Orientation

**Plan version:** 1.0 · **Prepared:** 2026-08-07 · **Architect:** planning-architect (Opus)
**Request:** `requests/request draft 2 (agent-ready).md` (binding spec; D1–D13 adopted as-is)
**Prior lessons read:** `Analysis/Plume locations/learning/LESSONS.md` (standing rules 1–7).

> **REVISION v1.1 (scoped, from Gate-2 audit, REVISE → docs/diagnostics only, no claim
> re-analysis; all encounter-dependent results are already null). Iteration 1 of ≤2:**
> - **MAJOR — encounter noise-floor interpretability.** The D5 k·MAD calibration on the
>   very flat quiet baseline yields threshold 7.2e-4, at the deconvolved noise floor
>   (per-trial median ethdeconv ≈4.2e-4; detected-onset median ≈7.4e-4; **0% of onsets
>   exceed 0.01** while real odor reaches 0.14). So ~28 onsets/trial index noise/exposure
>   crossings, not discrete high-amplitude odor contacts. **Add diagnostics** to
>   `stats.json` (onset-amplitude median; fraction of onsets >0.01; a secondary
>   amplitude-threshold count at 0.01 → expect ~0–1/trial) and **state this plainly** in
>   the H1 & H3 reports + the calibration note. This *reinforces* the null/exposure story.
> - **MINOR — H3 direction label** in stats.json contradicts the trial-pair majority
>   (64/105 post>pre); fix the label to match (narrative already correct).
> - **MINOR — k-rule fragility note:** on this degenerate quiet baseline the "smallest k"
>   rule returns the most permissive threshold; harmless for these nulls but flag it (a
>   new lesson) so it is not used to support a positive claim in future.
**New lessons →** `Analysis/trajectories/learning/LESSONS.md` (on archive).

Facts marked **[probed]** were confirmed by `code/probe_data.py` → `data/_probe.json`
before planning. Runtime-recovered numbers supersede any value here.

## 0. Goal & hypotheses

Test three claims about how foraging mice structure trajectories and orient to the
odor source (reward port `endpoint`), pooled over Loc1–6 (n=105 [probed]);
`anotherLoc` (n=9) reported separately (D7).

- **H1** — more ethanol encounters ⇒ straighter (lower tortuosity) search.
  H0: no monotonic association (ρ=0). Test: Spearman ρ(n_encounters, tortuosity),
  unit=trial, pooled; 95% CI by trial bootstrap (seed 1234); per-location ρ too.
  **Accept H1** iff ρ<0 and 95% CI excludes 0; else report honest direction.
  *Prior evidence to reconcile (LESSONS): ρ=+0.176 [−0.016,0.356], p=0.072 — weak,
  non-significant, POSITIVE (opposite the prediction). Reproduce it under D5, do not
  overclaim.* Also report frac_path_above_threshold vs tortuosity (prior ρ=−0.532
  [−0.656,−0.378]).
  **Exposure-confound guard (added post-analysis, architect):** raw `n_encounters`
  scales with path length/time, so a positive ρ(n_encounters, tortuosity) may reflect
  exposure, not odor guidance. Also report ρ(n_encounters, path_length),
  ρ(tortuosity, path_length), and an **exposure-normalized** ρ(encounter_rate,
  tortuosity) with encounter_rate = n_encounters / path_length (+ CI, seed 1234). The
  report must foreground this confound and lead the honest interpretation with the
  normalized measures (encounter_rate, frac_path_above_threshold).
- **H2** — body axis aligns toward source as the animal nears it: θ increases with
  distance-to-source d. H0: zero slope. Test: per-trial OLS slope of θ(t) on d(t);
  Wilcoxon signed-rank that per-trial slopes >0 across pooled trials. **Accept H2**
  iff slopes significantly >0 AND the F3 binned curve rises with distance.
- **H3** — animals reorient toward source upon an encounter: θ decreases from pre to
  post contact. H0: pre=post. Test: per trial with ≥1 encounter, mean θ in pre
  (−1..0 s) vs post (0..+1 s); paired Wilcoxon post<pre. **Accept H3** iff post θ
  significantly below pre θ. Descriptive: pooled peri-contact curve (F4).

## 1. Data scope & exclusions [probed]

- Aggregate `DATA/Mouse Arena Aggregate Data.h5` (schema 0.1, Fs=500), accessor-only.
- 114 infrared trials. **Pooled = Loc1–6 (105)**; **anotherLoc (9) separate** (D7).
- Geometry track = **body centroid** (D1); head track for the body-axis vector,
  contact positions, and a robustness cross-check.
- **Excluded:** `loc`/`duration` attrs (all-NaN [probed]); out-of-arena samples
  ([0,580]×[0,280]); non-finite; de-jumped outliers; frames with ‖head−body‖<1 px
  (undefined axis, D2) or ‖S−p‖<1 px; signal samples outside sensor coverage (NaN).

## 2. Shared library `code/traj_common.py` (single source of truth)

Imports the validated `Plume locations/code/plume_common.py` and reuses
`clean_track` (advancing-reference de-jump — LESSONS rule 1), `group_of`,
`pooled_dejump_Q`, `align_signal`, `mad`. Adds trajectory geometry, all evaluated
**on the head clock** after cleaning both tracks and interpolating body→head (§3.3):

- `interp_body_to_head(trial)` → body_h (Nh,2) via `np.interp` per axis (D1/§3.3).
- `body_axis_u(head, body_h)` = (head−body_h)/‖·‖; drop ‖·‖<1 px (D2).
- `to_source_s(body_h, S)` = (S−body_h)/‖·‖; drop ‖·‖<1 px (D3).
- `angle_theta(u,s)` = deg(arccos(clip(u·s,−1,1))) ∈ [0,180] (D4).
- `distance_to_source(body_h, S)` = ‖body_h−S‖ (D8/3.8).
- `tortuosity(p_clean)` = path_length/straight_line, straight_line≥1 px (D6).
- `detect_onsets(sig, time, thresh, refractory_s=0.20)` — **upward threshold
  crossings** (onsets), refractory 0.20 s (D5). (Distinct from plume_common's peak
  detector; onset = first sample where sig crosses from <thresh to ≥thresh.)
- `calibrate_encounter_threshold(trials)` — quiet far-from-source baseline = samples
  with head–source distance > 80th pctile AND ethdeconv < per-trial median (pooled);
  threshold = k·MAD(quiet); scan k∈{5,6,8,10}, pick **smallest k** with pooled
  quiet-baseline FPR ≤ 0.05/s (LESSONS rule 3; ≈k=8 expected). Return k, threshold,
  achieved FPR.
- `frac_path_above_threshold(sig_h_on_kept, thresh)` (context, 3.7).

**Self-check (before heavy compute):** reuse plume_common self-check; assert
θ∈[0,180]; a synthetic "facing source" frame → θ≈0; an "facing away" → θ≈180; an
onset detector finds the right crossings on a toy trace; de-jump removal on real
body track ≈0.4% (< the 5% smell-test STOP threshold, §3.2).

## 3. Parameters (each justified)

- **De-jump Q [probed]:** body 2.30 px, head 2.86 px (pooled 99.5th-pctile step).
  Advancing reference. Removal mean 0.4% body / 1.0% head [probed] — passes the
  ≈0.5% smell test; per-trial max (body 5.2%, head 29%) reflects high-motion trials,
  not a cascade (mean is the smell-test quantity).
- **Encounter detector (D5/D11):** on head-aligned `ethdeconv`; k-scan {5,6,8,10},
  smallest k with quiet FPR ≤0.05/s; refractory 0.20 s. Record k, thresh, FPR.
  *Caveat: encounter counts are low on this cohort (state per-trial median).*
- **F3 binning (D9):** 20 px bins, 0→max head–source d; ≥30 samples/bin else drop;
  mean θ per bin; 95% CI bootstrap over trials (seed 1234).
- **F4 peri-contact (D10):** −1.0..+1.0 s, 50 ms grid; mean θ per rel-time bin; 95%
  CI bootstrap over trials; edge windows contribute in-range samples only.
- **Stats (§3.9):** Spearman for H1 (heavy-tailed tortuosity, median≈6); Wilcoxon
  signed-rank for H2/H3; direction before significance; per-test CIs, no family-wise
  correction; seed 1234.

## 4. Deliverables (exact paths under `Analysis/trajectories/`)

| Artifact | Path |
|---|---|
| Shared lib + scripts + probe | `code/traj_common.py`, `code/build_metrics.py`, `code/probe_data.py` |
| Per-trial metrics + per-hyp stats | `data/trajectory_metrics.h5`, `data/trajectory_metrics.json`, `data/stats.json` |
| Figures (png+pdf+txt sidecar) | `reports/figures/F1_encounters_vs_tortuosity.*`, `F2_example_paths.*`, `F3_angle_vs_distance.*`, `F4_peri_contact_angle.*` |
| Reports (docx) | `reports/H1 - encounters vs tortuosity.docx`, `reports/H2 - alignment vs distance.docx`, `reports/H3 - peri-contact reorientation.docx` |
| Plan/audit/notes | `PLAN.md`, `plan.json`, `audit_report.md`, `SESSION_NOTES.md` |
| Lessons | `learning/LESSONS.md` |

`trajectory_metrics` holds per-trial: file_name, end_loc, n_encounters, tortuosity,
path_length, straight_line, frac_path_above_threshold, H2 slope, pre/post peri-contact
θ. `stats.json` holds every number the reports cite. **Reports inject from saved
objects — never hardcode.** HDF5: gzip4+shuffle on numeric ≥256 elems, `.tmp`→
`os.replace`, `build_complete=1` last, README attr, created_utc, generator+version.

## 5. Acceptance / two gates (§9)

- **Gate 1 (code-verifier, fresh):** accessor-only; both tracks advancing-reference
  cleaned (≈0.5%, <5% smell test); signals/body interpolated onto head clock (never
  reverse); encounter detector calibrated to quiet FPR ≤0.05/s with k-scan reported
  and **re-derived** (boundary value); θ∈[0,180]; unit=trial; anotherLoc excluded
  from pooled; seed 1234; ≥3 numbers/hypothesis re-derived; zero placeholder tokens.
- **Gate 2 (scientific-auditor, independent):** encounter counts physically
  interpretable (not noise); H1 direction honest vs prior +0.176; H2/H3 not driven by
  a few trials; **angle convention correct** (spot-check a trial facing the port →
  small θ; trial 2 near-source θ≈23° [probed] supports u=head−body/s=endpoint−body);
  CIs present; direction-before-significance; nulls headlined honestly.
- ≤2 fix loops (Gate 1), ≤2 revise loops (Gate 2), then STOP with SESSION_NOTES.md.

## 6. Task graph

1. [me] plan + `traj_common.py` (+ self-check).
2. [data-analyst] `build_metrics.py` → per-frame geometry (shared) → per-trial
   metrics + H1/H2/H3 stats → `trajectory_metrics.*` + `stats.json`. Slice-first.
3. [fresh code-verifier] Gate 1.
4. [figure+report agents, parallel] F1+F2 & H1 report; F3 & H2 report; F4 & H3 report.
5. [fresh scientific-auditor] Gate 2 → `audit_report.md`.
6. [me] archive → `learning/LESSONS.md`; `SESSION_NOTES.md`.

**Invariants:** no self-approval; verifier & auditor fresh/independent; never mark
human-approved; a bounded stop is success (hand off via SESSION_NOTES.md).
