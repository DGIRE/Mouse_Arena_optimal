# Selective Sampling Bouts & Odor Reactions — Agent-Ready Analysis Request

**Repo:** `C:\Projects\Repos\Mouse Arena` · **Analysis:** `Analysis\reactions_2`
**Relationship to prior work:** this is a **redesign** of `Analysis\reactions` (the "nose sweeps"
run). It keeps that request's rigor scaffolding but **replaces the event definition** so the
analysis targets *rare, deliberate sampling behaviors* rather than incidental head motion.
**Prepared for David Gire, 2026-08-08.**

Genuine judgement calls appear in **§2 Decisions** as editable rows: **David may edit any D-row
before launch; the planning-architect then treats §2 as binding.**

---

## §0 — How this analysis runs (read first)

**Pipeline (the `.claude` agent team in `Analysis\.claude`).** Launch with working directory =
`C:\Projects\Repos\Mouse Arena\Analysis`, `claude --permission-mode auto`, and hand it this
document. Team: `planning-architect` → `data-analyst` → `code-verifier` **[Gate 1]** →
`figure-builder` + `report-writer` → `scientific-auditor` **[Gate 2]** → `lesson-archivist`.

**Interpreter.** Use the project analysis interpreter from `Analysis\.claude\settings.json`
(**`$AR_PY`**). Do not hardcode a Python path; call `$AR_PY`. Headless matplotlib (Agg).

**Read the prior lessons FIRST — all three files (they build on each other):**
- `Analysis\Plume locations\learning\LESSONS.md` — standing rules **1–7** (cleaning/de-jump, clock
  alignment, calibrated FPR, cross-scale/amplitude, honest nulls).
- `Analysis\trajectories\learning\LESSONS.md` — rules **8–11** (exposure/count confound;
  FPR-low-but-noise-floor; smallest-k permissiveness; vector spot-check).
- `Analysis\reactions\learning\LESSONS.md` — rules **12–15** (ratio-detector denominator bias;
  permissive kinematic threshold → routine motion; huge-N pseudo-significance; reuse validated
  outputs). **§11 restates the ones that decide this design.**
Write new lessons to `Analysis\reactions_2\learning\LESSONS.md` at the end.

**Data access is accessor-only** through `mouse_arena_aggregate_io.Aggregate` (§1). Never open the
`.h5` layout directly or modify it.

**One shared library, reusing validated primitives.** Put routines in
`Analysis\reactions_2\code\reactions2_common.py`, which **imports and reuses** `plume_common`
(`clean_track` advancing-reference de-jump, `mad`, `group_of`, signal alignment) and may reuse the
validated kinematic helpers from `Analysis\reactions\code\reactions_common.py` (e.g. the
translation-invariant body-frame head motion). **Do not re-implement cleaning/alignment** (rule 15).

**Probe before planning.** Run `probe_data.py` confirming, against the real aggregate, *before*
writing `PLAN.md`: 114 behavior trials, **all `lighting = infrared`**; `_Loc(\d+)` groups Loc1–6 =
105, `anotherLoc` = 9; head ≈ 99 Hz vs sensor 500 Hz; ranges. **Also reproduce the prior
over-detection as the baseline to beat:** the reactions v1 `R ≥ 1.5` detector gave a *median ≈ 111
sweeps/trial (≈ 1.7/s)* — this request exists to replace that. Record the confirmed numbers in
`PLAN.md`. If a premise is false, STOP with a session note.

**Bounded loops, determinism, honesty.** ≤2 fix loops at Gate 1, ≤2 revise loops at Gate 2, then
STOP with session notes. Seed = **1234**. **Pre-register null-tolerant acceptance:** every prior
hypothesis in this repo (Plume enhancement; Trajectories H1–H3; Reactions H1–H3) returned a
physically-meaningful **null**. A clean null here is a valid, publishable result; report **direction
before significance** and **headline nulls honestly**. Do not manufacture an effect.

---

## §0.1 — Why this redesign (what changed from `reactions` v1)

The v1 event ("nose sweep" = local maximum of `R = v_nose/v_com`, height `R ≥ 1.5`) was the wrong
target for **three** reasons the v1 run itself established:

- **Far too frequent to be sampling** (rule 13): median ≈ 111 events/trial (≈ 1.7/s). Discrete
  investigative acts should be rare (a handful per trial).
- **Denominator-biased** (rule 12): the ratio detector fired preferentially on **low-COM frames**
  (`v_com` at peaks ≈ 3 px/s vs ≈ 11 px/s trial-wide). Events were often just momentary body
  slow-downs, not deliberate head casts.
- **No behavioral coherence with odor** (v1 nulls): peri-event ethanol was flat (≈ 0.043 a.u.
  across the whole ±1 s window; peri-vs-null Wilcoxon p = 0.12), COM was *higher* not lower during
  events on the non-circular detector, and events tracked occupancy spatially.

**This request defines a rare, deliberate "sampling bout" = a locomotor pause combined with a
distinct head cast**, detected with a **translation-invariant** kinematic (the rotation of the head
relative to the body), and then asks whether *these* events — not incidental motion — are driven by
and directed toward odor.

---

## §1 — Data & accessor

**Aggregate:** `C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5` (schema 0.1,
`Fs = 500` Hz; behavior = 114 trials, **all `infrared`**).

```python
import sys; sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\DATA\code")
from mouse_arena_aggregate_io import Aggregate
agg = Aggregate(r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5")
trials = agg.behavior(lighting="infrared")   # all 114
```

Per-trial fields (px, 0-based, x=col0 y=col1): `head`(Nh,2) = head/nose (sensor); `body`(Nb,2) =
COM; `head_time`,`body_time` (s); `ethanol`(Ne,) raw a.u. ≈[−0.28,1.0] @500 Hz; `ethanol_time`;
`ethdeconv`(Ne,) ≈[−0.02,0.14]; `endpoint`(2,) = odor **source**; attrs `file_name`
(carries `_Loc(\d+)` **and** a 3-digit mouse id, e.g. `…-204_…`), `threshold` (raw scale). `loc`,
`duration` attrs are **all-NaN — never use.** Arena `[0,580]×[0,280]`. End location from
`file_name` `_Loc(\d+)` → Loc1–6 (105) + `anotherLoc` (9, separate).

---

## §2 — Decisions made explicit (EDITABLE by David; planner treats as binding)

| # | Question | Decision (default) |
|---|---|---|
| **D1** | Coordinate frame & clock. | All per-frame quantities on the **head clock**; interpolate `body` and the ethanol trace onto `head_time` (`np.interp`, NaN outside support); clean both tracks first (§3.1). Never resample position onto the 500 Hz sensor clock. |
| **D2** | The **sweep kinematic** (must be translation-invariant — rule 12). | The **head-relative-to-body bearing** `φ(t) = atan2(head − body)` (deg, unwrapped), and its **angular speed** `ω(t) = |dφ/dt|` (deg/s), smoothed (§3.3). This isolates nose rotation from whole-body translation. **Do NOT detect events on `v_nose/v_com`.** (Body-frame nose linear speed `‖d/dt(head−body)‖` is an editable alternative magnitude.) |
| **D3** | **Locomotor pause** condition (the "stop"). | `v_com < v_pause` sustained for ≥ `τ_pause`. Defaults: `v_pause` = 25th percentile of pooled `v_com` (report the absolute px/s); `τ_pause` = 0.30 s. |
| **D4** | **Head cast** condition (the "sample"). | Within/overlapping a pause, a contiguous interval where the head-body bearing sweeps a **cumulative angular excursion ≥ `Δφ_min`** with **peak `ω ≥ ω_min`**. Defaults: `Δφ_min` = 40°; `ω_min` = 90th percentile of pooled `ω`. |
| **D5** | **Sampling bout = conjunction.** | A **sampling bout** = a locomotor pause (D3) containing ≥1 qualifying head cast (D4). Merge bouts separated by < `t_merge` = 0.50 s. **Bout onset** = pause onset; **bout peak** = time of max `ω` in the bout (used for peak-aligned views). |
| **D6** | **RARITY GATE (binding acceptance criterion for the event definition itself).** | After detection, the pooled **median bout rate must be ≪ the v1 baseline of ≈ 1.7/s** — target **≈ 0.05–0.3 /s** (a few bouts per trial). **If the pooled median rate exceeds 0.5/s, the thresholds are too permissive:** tighten (raise `Δφ_min`, raise the `ω` percentile, and/or lengthen `τ_pause`) and re-detect until the gate passes; report the final parameters and rate. Report the fraction of trials with 0 bouts and with ≥1 bout. |
| **D7** | **Incidental-motion comparison set** (for specificity). | "Incidental head motion" = high-`ω` and/or high body-frame nose-speed events that occur **while the body is moving** (fail the pause condition D3). Used only as a contrast class — sampling bouts should differ from these in odor association / spatial pattern. |
| **D8** | **Baseline-subtracted ethanol.** | Raw `ethanol` minus a rolling 10th-percentile baseline (W = 20 s, sensor clock — the validated Plume drift-removal), interpolated onto the head clock. Report on the raw a.u. scale. *(Editable: `ethdeconv`, or a different W/percentile.)* |
| **D9** | **"Odor-reached" region** (H3). | Reuse `Analysis\Plume locations\data\odor_fields.h5`: for a trial's Loc, a bin is **odor-reached** iff valid (≥3 trials) and **max-field > `max(3·MAD, 1e-3)`** (the odor report's cutoff). A bout is "in-odor" if the head position at bout onset maps to an odor-reached bin. Fallback if a Loc field is missing: head within `r = 100 px` of source. |
| **D10** | **Replication unit & inference** (rule 14). | **Trial.** One statistic per trial; inference by **trial-level** Wilcoxon / trial bootstrap (2000 draws, seed 1234), **never per-event point-bootstrap**. Only trials with ≥1 bout contribute to bout-conditioned tests; report N contributing. Pool Loc1–6 (n = 105); `anotherLoc` (9) separate. |
| **D11** | **Event alignment.** | **Onset-aligned** for peri-bout odor (H1) and precedence (H2); **peak-`ω`-aligned** additionally for kinematic panels. Peri window ±1.0 s (50 ms grid). |
| **D12** | **Fig 3 example trial.** | A pooled Loc1–6 trial with a **representative handful of sampling bouts** (e.g. the trial with the most bouts, provided its rate is within the gate) — not the max-rate incidental trial. State the choice. |

---

## §3 — Shared definitions (single source of truth → `reactions2_common.py`)

**3.1 Cleaning.** Clean `head` and `body` with `plume_common.clean_track` (drop non-finite, arena
box, advancing-reference 99.5-pct de-jump — rule 1). **Smell test:** ≈0.5 % removed; if >~5 %, STOP.

**3.2 Clock alignment.** Interpolate `body` and ethanol onto `head_time` (rule 6).

**3.3 Kinematics.** `v_com(t)` = smoothed COM speed (px/s). Head-body bearing `φ(t)`; angular speed
`ω(t) = |dφ/dt|` (deg/s), smoothed (default Savitzky–Golay, ~70 ms window). Differentiate *after*
smoothing (rule: differentiation is noisy on a ~99 Hz track); sanity-check magnitudes.

**3.4 Sampling-bout detection** = D3 ∧ D4 ∧ D5, with the D6 rarity gate. **3.5 Incidental set** =
D7. **3.6 Baseline-subtracted ethanol** = D8. **3.7 Odor-reached lookup** = D9 (load the odor field
read-only).

**3.8 Statistics.** Trial replication (D10). **Lead with the bout RATE** (per-second), not counts
(rules 8/13). **Pair every odor claim with an absolute-amplitude check** (rule 9): peri-bout ethanol
vs the noise floor (~4e-4) and the real range (~0.14); report the fraction of bouts whose peri-odor
exceeds 0.01 a.u. **Above-floor is necessary, not sufficient** — the inferential test is vs a null.
**Lead with effect magnitude, not p** (rule 14); a small p driven by many events is not an effect.
Seed 1234; direction before significance; state the multiple-comparisons posture (per-test CIs, no
family-wise correction across the hypotheses).

---

## §4 — Deliverable A (required): sampling-bout definition & selectivity

This is a mandatory characterization, not a hypothesis. Produce and report:
1. **Rarity:** pooled median bout **rate** (/s) and per-trial count distribution; the fraction of
   trials with ≥1 bout; the achieved rate shown **against the v1 baseline ≈ 1.7/s** to demonstrate
   the redesign selects far rarer events (D6 gate passed).
2. **Selectivity vs incidental motion (D7):** sampling bouts vs incidental events differ in the
   defining kinematics — report COM speed (bouts ≪ incidental, by construction) and head angular
   excursion / peak `ω` (bouts ≥ incidental). State plainly that the low-COM signature is
   **definitional** (so no "they slow down" claim is made — that was v1's circular H2).
3. **Sanity:** on an example trial, confirm detected bouts coincide with visible head casts during
   pauses (rule 11 analogue).
**Report:** `reactions_2\reports\Sampling-bout definition and selectivity.docx`. **Figure:** F1.

---

## §5 — Hypothesis 1: sampling bouts are odor-associated (reactive sampling)

**H1.** Baseline-subtracted ethanol is **elevated around sampling bouts** relative to a matched
within-trial null, and **more so than around incidental head-motion events** (odor specifically
accompanies deliberate sampling).
**H0.** Peri-bout ethanol equals the matched random-time null, and does not exceed the
incidental-event peri-odor.
**Tests.** (a) Per trial, mean peri-bout baseline-sub ethanol in [−0.5, +0.5] s vs a **matched-count
random-time null** drawn from the same trial (permutation, seed 1234); Wilcoxon across contributing
trials, predicting bout > null. (b) **Specificity:** the same peri-odor for sampling bouts vs
incidental events (paired/grouped across trials), predicting bouts > incidental. **Absolute-amplitude
check required** (rule 9). **Lead with magnitude** (rule 14).
**Accept H1** iff peri-bout ethanol significantly exceeds the matched null **and** exceeds
incidental-event peri-odor — else report the honest result.
**Figure:** F2A. **Report:** `reactions_2\reports\H1 - sampling bouts and odor.docx`.

---

## §6 — Hypothesis 2: odor encounters precede (trigger) sampling bouts

*(This replaces v1's circular "COM slows during sweeps" test — slowing is now definitional — with a
non-circular, directional odor→behavior test.)*
**H2.** Baseline-subtracted ethanol **rises in the window before bout onset** — an odor encounter
precedes the decision to stop and sample.
**H0.** Pre-onset ethanol is flat (no rise) relative to the trial baseline / to the post-onset level.
**Tests.** Onset-aligned peri-bout odor (F2A). Per trial: mean ethanol in a **pre-onset window
[−0.75, −0.25] s** vs the trial baseline (median over the trial) and vs a matched random-time null;
Wilcoxon across contributing trials, predicting pre-onset > baseline. Also report the onset-aligned
odor **slope** over [−1.0, 0] s (predict positive). Control for the spatial confound (pauses may
occur near the port) by also reporting the test **within odor-reached vs odor-absent locations** and
against the incidental-event onset-aligned odor.
**Accept H2** iff pre-onset ethanol significantly exceeds baseline/null with a positive onset-aligned
slope, surviving the incidental-event and spatial controls — else report the honest result.
**Figure:** F2A (odor) + F2B (kinematics, showing the stop at onset). **Report:**
`reactions_2\reports\H2 - odor precedes sampling.docx`.

---

## §7 — Hypothesis 3: sampling bouts are spatially enriched where odor is plausibly present

**H3.** Sampling-bout **locations** (head at bout onset) are enriched in odor-reached regions (D9)
relative to where the animal spends its time.
**H0.** The in-odor fraction of bouts equals the occupancy-based expectation.
**Test.** Per trial: `f_bout` = fraction of bouts in odor-reached bins; `f_occ` = fraction of all
kept head frames in odor-reached bins; and a **within-trial permutation null** (draw `n_bout` random
frame times, compute in-odor fraction, 2000 draws → per-trial `f_bout − mean(null)`). Wilcoxon across
contributing trials that `f_bout > f_occ` (and `f_bout − null > 0`), predicting enrichment. Report
fraction of trials enriched and the pooled effect; note ethanol amplitude at the mapped bins is above
the noise floor (rule 9).
**Accept H3** iff bouts are significantly enriched beyond occupancy — else report the honest result.
**Figures:** F3A/F3B. **Report:** `reactions_2\reports\H3 - sampling bouts in odor-reached regions.docx`.

---

## §8 — Figures (exact specifications)

All figures: save **`.png` + `.pdf` + `.txt`** sidecar (provenance + exact numbers drawn) to
`reactions_2\reports\figures`. Headless Agg; axes labelled with units; pooled = Loc1–6; `anotherLoc`
separate only where noted; vertical line at the alignment `t = 0` on every peri-bout panel.

**F1 — event definition & selectivity** (`F1_bout_definition.*`). (A) per-trial **bout-rate**
distribution (violin/hist), with the v1 detector rate (≈1.7/s) drawn as a reference line to show the
new events are far rarer; annotate pooled median rate, % trials with ≥1 bout. (B) sampling bouts vs
incidental events: paired comparison of **COM speed** and **head angular excursion / peak ω** (box or
paired points), showing the pause + large cast that define a bout.

**F2 — peri-bout odor & kinematics (onset-aligned)** (`F2_peri_bout.*`). (A) mean peri-bout
**baseline-subtracted ethanol** vs time-to-bout-onset, [−1,+1] s (50 ms grid), mean + **95 % CI band**
(trial bootstrap), with the **matched random-time null band** overlaid (H1) and the incidental-event
curve for contrast; shade the pre-onset window used for H2. (B) mean peri-bout **COM speed** and
**head angular speed ω** on the same axis/window (shows the stop at onset and the cast). Annotate
n(bouts), n(trials contributing).

**F3 — spatial** (`F3_spatial.*`). (A) example trial (D12): cleaned **COM trajectory** in the arena
box (equal aspect), the **odor-reached footprint** for that Loc lightly shaded, **sampling-bout
onset locations marked** (arrowheads/markers), source `endpoint` ×; below it two stacked time series
for that trial — baseline-subtracted **ethanol** and **ω(t)** — with bout onsets marked in both. (B)
per-trial **`f_bout` vs `f_occ`** scatter (identity line; point size ∝ n_bout; per-trial null band),
pooled Loc1–6 — the H3 result. Annotate the trial-level Wilcoxon and the % of trials enriched.

---

## §9 — Output paths (all under `Analysis\reactions_2`)

| Artifact | Path |
|---|---|
| Shared library + task scripts + probe | `Analysis\reactions_2\code\` |
| Result HDF5 / JSON (per-bout + per-trial metrics, per-hypothesis stats) | `Analysis\reactions_2\data\` (create if absent) |
| Figures (`.png` + `.pdf` + `.txt`) | `Analysis\reactions_2\reports\figures\` |
| Reports (`.docx`): bout-definition + H1 + H2 + H3 | `Analysis\reactions_2\reports\` |
| New lessons | `Analysis\reactions_2\learning\LESSONS.md` |
| Plan / contract | `Analysis\reactions_2\` (`PLAN.md`, `plan.json`) |

Save a tidy `bouts.(h5|json)` with, per bout: trial `file_name`, `end_loc`, onset & peak times,
duration, peak `ω`, angular excursion, `v_com` during, in-odor flag, peri-onset odor level/slope;
plus a per-trial table (bout count, **bout rate**, n incidental events, `f_bout`, `f_occ`,
pre-onset-odor stats); and `stats.json` with every number the reports cite. **Reports inject numbers
from saved objects — never hardcode.** Read the Plume `odor_fields.h5` **read-only**.

---

## §10 — Definition of done (two gates)

**Gate 1 (code-verifier, fresh context).** Re-derives ≥3 numbers per deliverable from the accessor +
saved objects; confirms: accessor-only reads; both tracks cleaned with the advancing-reference rule
(≈0.5 %; the >5 % smell test); everything on the head clock (never reversed); the sweep kinematic is
**translation-invariant** (bearing of `head−body`, contains no `v_com` denominator); the **D6 rarity
gate passes** (pooled median rate ≪ 1.7/s, target ≤ ~0.3/s) with final parameters reported; **rates
reported alongside counts**; inference is **trial-level** (no per-event point-bootstrap); seed 1234;
zero placeholder tokens.

**Gate 2 (scientific-auditor, independent).** Checks meaning: **(i)** events are genuinely rare and
**not detected via a ratio/denominator-biased signal** (rule 12) — the low-COM signature is stated as
definitional, not claimed as a result; **(ii)** the **rarity gate** (rule 13) is satisfied and the
report states most head motion is *not* sampling; **(iii)** the **absolute-amplitude check** (rule 9)
precedes any odor claim; **(iv)** inference leads with **magnitude and trial-level CIs**, not
N-driven p-values (rule 14); **(v)** H2's precedence test is **not circular** and survives the
incidental-event and spatial controls; **(vi)** kinematic/vector conventions pass a physical
spot-check (rule 11); **(vii)** direction before significance and **honest nulls headlined**. No
fabricated effects; no self-approval.

**Both gates must pass** (≤2 revise loops). Then `lesson-archivist` appends dated lessons to
`reactions_2\learning\LESSONS.md`. *(Optional robustness the auditor may request: re-run with
**animal** grouping via the 3-digit `file_name` id to check trial-level results survive.)*

---

## §11 — Gotchas (the standing rules that decide this design)

1. **Do not detect events on `v_nose/v_com`** (rule 12). The ratio is denominator-biased toward
   low-COM frames; use the translation-invariant head-body bearing angular speed (D2).
2. **Rarity gate is binding** (rule 13). A permissive kinematic threshold reproduces v1's
   routine-motion events (~1.7/s). Tighten until the pooled median rate is ≪ that; lead with rate.
3. **Low COM during bouts is definitional, not a finding.** Bouts require a pause, so "the animal
   slows" is built in — never present it as a result (this was v1's circular H2). H2 here is the
   non-circular **odor-precedes-sampling** test instead.
4. **Inference is trial-level** (rule 14). One statistic per trial; trial-bootstrap CIs; a tiny p
   from thousands of events is not an effect. Lead with magnitude.
5. **Amplitude check before any odor claim** (rule 9): peri-bout ethanol vs noise floor (~4e-4) and
   real range (~0.14); above-floor is necessary, not sufficient — the test is vs a null.
6. **Advancing-reference de-jump only** (rule 1); verify ≈0.5 % removed. **Two clocks:** interpolate
   onto the ~99 Hz head clock (rule 6). **Differentiate after smoothing.**
7. **`loc`/`duration` are all-NaN** (rule 9 of Plume set); end location from the `file_name`
   `_Loc(\d+)` token; `anotherLoc` separate. **Baseline-subtracted ethanol** is raw-scale (D8), not
   `ethdeconv`; the `threshold` attr is raw-scale.
8. **Reuse validated outputs** (rule 15): `plume_common`, the reactions v1 body-frame kinematic, and
   the Plume `odor_fields.h5` (read-only).
9. **Expect a possible null and pre-register for it.** Four analyses in, this cohort's head-mounted
   ethanol signal has not supported fine sensorimotor odor structure at defensible thresholds. A
   clean, well-powered null on *genuine* sampling events is a valuable result — report it honestly.
