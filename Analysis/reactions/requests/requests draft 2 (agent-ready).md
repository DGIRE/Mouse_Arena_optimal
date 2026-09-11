# Nose Sweeps & Odor-Guided Search — Agent-Ready Analysis Request (Draft 2)

**Repo:** `C:\Projects\Repos\Mouse Arena` **Analysis:** `Analysis\reactions`
**Supersedes:** `requests\requests draft.docx` (original kept alongside; this Draft 2 is the binding spec).
**Prepared for David Gire, 2026-08-08.**

This rewrites the free-text request into an unambiguous, agent-ready specification a Claude
CLI agent team can execute end-to-end. Everything the original left implicit — what a "nose
sweep" is, how the nose/COM ratio is guarded, what "baseline-subtracted ethanol" means, what
"regions plausibly reached by the ethanol odor" means, and how each figure is built — is pinned
down here. Genuine judgement calls appear in **§2 Decisions** as editable rows: **David may edit
any D-row before launch; the planning-architect then treats §2 as binding.**

---

## §0 — How this analysis runs (read first)

**Pipeline (the `.claude` agent team in `Analysis\.claude`).** Launch with working directory =
`C:\Projects\Repos\Mouse Arena\Analysis`, `claude --permission-mode auto`, and hand it this
document. Team: `planning-architect` → `data-analyst` → `code-verifier` **[Gate 1]** →
`figure-builder` + `report-writer` → `scientific-auditor` **[Gate 2]** → `lesson-archivist`.

**Interpreter.** Use the project analysis interpreter resolved from `Analysis\.claude\settings.json`
(**`$AR_PY`**). Do not hardcode a Python path; call `$AR_PY`. Headless matplotlib (Agg).

**Read the prior lessons FIRST — both files.** Before planning, read
`Analysis\trajectories\learning\LESSONS.md` (standing rules **8–11**) and
`Analysis\Plume locations\learning\LESSONS.md` (standing rules **1–7**). This request depends on
them; §10 restates the ones that will bite here. Write new lessons to
`Analysis\reactions\learning\LESSONS.md` at the end.

**Data access is accessor-only.** Read the aggregate **only** through
`mouse_arena_aggregate_io.Aggregate` (§1). Never open the `.h5` layout directly or modify it.

**One shared library, reusing the validated primitives.** Put every routine in a single
`Analysis\reactions\code\reactions_common.py` that **imports and reuses** the already-validated
`plume_common` (`clean_track` advancing-reference de-jump, `mad`, `group_of`, signal alignment)
from the Plume-locations code — do not re-implement cleaning/alignment. This is the "what worked"
lesson from both prior runs (the fixed de-jump propagates for free; the smell test passed first try).

**Probe before planning.** Run a short `probe_data.py` confirming this request's premises against
the real aggregate before writing `PLAN.md`: 114 behavior trials, **all `lighting = infrared`**
(so "infrared only" excludes nothing); `_Loc(\d+)` groups Loc1–Loc6 = 105 trials, `anotherLoc` = 9;
head clock ≈ 99 Hz vs sensor 500 Hz; body/head/ethanol/ethdeconv ranges. Write the confirmed
numbers into `PLAN.md`. If any premise is false, STOP with a session note.

**Bounded loops, determinism, honesty.** ≤2 fix loops at Gate 1, ≤2 revise loops at Gate 2, then
STOP with session notes. Seed = **1234** everywhere randomness enters. Report **direction before
significance** and **headline null results honestly** — all three prior hypotheses in this repo
came back null and were reported as such; do not manufacture an effect.

---

## §1 — Data & accessor

**Aggregate:** `C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5`
(schema 0.1, `Fs = 500` Hz; behavior = 114 trials, **all `infrared`**).

```python
import sys; sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\DATA\code")
from mouse_arena_aggregate_io import Aggregate
agg = Aggregate(r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5")
trials = agg.behavior(lighting="infrared")   # all 114
```

**Per-trial fields:**

| Key | Shape | Meaning |
|---|---|---|
| `head` | (Nh, 2) | head (sensor) track, px — the **nose** proxy (sensor is head-mounted) |
| `body` | (Nb, 2) | body-centroid track, px — the **center of mass (COM)** |
| `head_time` | (Nh,) | head-track timestamps, s (≈ 99 Hz; often starts seconds after 0) |
| `body_time` | (Nb,) | body-track timestamps, s |
| `ethanol` | (Ne,) | raw ethanol sensor, a.u., ≈ [−0.28, 1.0], 500 Hz |
| `ethanol_time` | (Ne,) | sensor timestamps, s |
| `ethdeconv` | (Ne,) | deconvolved ethanol, a.u., ≈ [−0.02, 0.14] |
| `endpoint` | (2,) | reward port = **odor source** for this trial, px |
| `file_name` | str (attr) | encodes `_Loc(\d+)` **and** a mouse id (e.g. `…-205_…` → animal 205) and a date |
| `threshold` | float (attr) | per-trial threshold on the **raw `ethanol`** scale |
| `loc`, `duration` | attr | **all-NaN — NEVER use** |

**Arena extent:** `[0, 580] × [0, 280]` px (x × y); 0-based; x = col 0, y = col 1; units are pixels.
**End location = source** from `file_name` `_Loc(\d+)` → Loc1–6 (105 trials, one exact endpoint each)
+ `anotherLoc` (9, scattered). Each trial's `endpoint` is its odor source.

> **Note (for extensions, not the primary run):** `file_name` carries a 3-digit mouse id
> (e.g. `Mohammad-205_Trial1_Loc5`). The prior runs used **trial** as the replication unit because
> a *6-digit* animal token was absent; a 3-digit id is in fact present. Keep **trial** as the
> primary replication unit here for continuity, but the planner may parse animal id into
> `trajectory`/metrics for an optional animal-level robustness check (see §9).

---

## §2 — Decisions made explicit (EDITABLE by David; planner treats as binding)

| # | Question | Decision (default) |
|---|---|---|
| **D1** | What is the **nose** and what is the **COM**? | Nose = `head` track (head-mounted sensor). COM = `body` track (body centroid). Both cleaned per §3.2. |
| **D2** | On which **clock** are all per-frame quantities computed? | The **head clock** (`head_time`). Interpolate `body` onto `head_time` (per-axis `np.interp`) and the ethanol trace onto `head_time`; never resample position onto the 500 Hz sensor clock. |
| **D3** | How are **velocities** computed? | Per-axis smoothed finite difference of the cleaned track on the head clock (default: Savitzky–Golay, window 7 frames ≈ 70 ms, poly order 2, deriv=1), then speed = `‖(vx, vy)‖` in **px/s**. `v_nose` from `head`, `v_com` from body-on-head-clock. Smoothing window is editable. |
| **D4** | What is **normalized head movement** `R(t)`? | `R(t) = v_nose(t) / max(v_com(t), v_floor)`. `v_floor` = the 10th percentile of pooled `v_com` (a small positive px/s), to stop the ratio blowing up when the COM is momentarily still. Report `v_floor` and the fraction of frames it binds. |
| **D5** | What is a **nose sweep**, and its "maximal nose sweep velocity" time? | A **local maximum of `R(t)`** (the normalized-head-movement signal), detected with: smoothing (D3 already applied), **minimum height `R ≥ 1.5`** (nose ≥ 1.5× COM speed), a **minimum prominence** (default 0.5 in `R` units), and a **refractory gap of 0.30 s** between peaks. The sweep *time* = the peak time; "maximal nose sweep velocity" = `R` at that peak. All height/prominence/refractory values are editable. |
| **D6** | **Circularity guard for H2** (critical — see §5). | Because `R` has `v_com` in its denominator, a sweep peak can arise from a COM slow-down rather than genuine nose motion. **Binding:** for every detected sweep, record both `v_nose` and `v_com` at the peak and classify it **nose-driven** (`v_nose` above its trial median) vs **COM-dropout-driven** (`v_com` below its trial median). H2 must be re-tested on a **numerator-only** sweep set — peaks of `v_nose` alone (body-frame nose speed, see D7) — and the report must state whether the COM slow-down survives that independent detector. |
| **D7** | **Numerator-only / body-frame** sweep detector (for the D6 robustness and as an editable primary). | Body-frame nose speed = `‖ d/dt(head − body) ‖` on the head clock (isolates nose motion from whole-body translation, matching the request's intent "nose moving independent of the body moving"). Detect peaks with the same height-in-SD/prominence/refractory logic. Default: `R`-based detector is primary (D5); this is the robustness set. *(Editable: promote this to primary.)* |
| **D8** | What is **baseline-subtracted ethanol**? | Raw `ethanol` minus a rolling baseline = the **rolling 10th-percentile over a W = 20 s window** on the sensor clock (the validated Plume-locations drift-removal), then interpolated onto the head clock for peri-sweep use. *(Editable: use `ethdeconv`, or a different W/percentile.)* Report on the raw a.u. scale. |
| **D9** | What defines **"regions plausibly reached by the ethanol odor"** (H3)? | **Primary (spatial):** reuse the Plume-locations odor-field maps `Analysis\Plume locations\data\odor_fields.h5`. For a trial's Loc, an arena bin is **odor-reached** if it is a valid (≥3-trial) bin whose **max-field** exceeds the odor report's above-background cutoff `max(3·MAD, 1e-3)`. A sweep is "in-odor" if the head position at the sweep maps to an odor-reached bin. **Fallback (if the odor field is unavailable for a Loc):** head within radius `r = 100 px` of the source **or** baseline-subtracted ethanol (D8) at the sweep ≥ a stated low threshold. State which was used per trial. |
| **D10** | **Replication unit** and grouping. | **Trial.** Pool **Loc1–Loc6 (n = 105)**; `anotherLoc` (n = 9) analysed separately and excluded from pooled stats/figures. Peri-sweep averages pool sweeps across pooled trials; 95% CIs by **bootstrap over trials** (2000 draws, seed 1234). |
| **D11** | **Scatter granularity** (Fig 2A/2B). | **One point per detected sweep** (values at the sweep peak), pooled Loc1–6, colored by trial or end-location. Report a Spearman ρ with 95% CI (bootstrap over trials) for each scatter. |
| **D12** | **Fig 3 example trial.** | The pooled Loc1–6 trial with the **highest sweep rate** (sweeps per second, to avoid the duration/exposure confound — LESSONS rule 8), tie-broken by raw count. Plot the **COM (body) track** colored by `R(t)`. *(Editable: use raw count, or the head track.)* |
| **D13** | **Peri-event windows.** | ±1.0 s around each sweep peak for the Fig 1 average traces (50 ms grid); the Fig 2B ethanol sum uses **[−0.5, +0.5] s**; the H2 "during-sweep" window is **[−0.25, +0.25] s**. All editable. |

---

## §3 — Shared definitions (single source of truth → `reactions_common.py`)

**3.1 Cleaning.** Clean `head` and `body` independently with `plume_common.clean_track`: drop
non-finite, keep inside `[0,580]×[0,280]`, advancing-reference global de-jump at the 99.5th-pctile
step (LESSONS rule 1). **Smell test:** ≈0.5 % removed (prior run removed 0.41 % body / 1.01 % head);
if > ~5 %, STOP.

**3.2 Clock alignment.** Interpolate `body` and the ethanol trace onto `head_time`
(`np.interp`, NaN outside support). All per-frame quantities live on the head clock (D2).

**3.3 Velocities.** Smoothed finite differences (D3) → `v_nose(t)`, `v_com(t)` in px/s. Also expose
the **body-frame nose velocity** `‖d/dt(head − body)‖` (D7).

**3.4 Normalized head movement** `R(t) = v_nose / max(v_com, v_floor)` (D4). **3.5 Sweep
detection** on `R` (D5) and the numerator-only set (D7). **3.6 Baseline-subtracted ethanol** (D8).

**3.7 Odor-reached lookup** (D9): map a head (x,y) to a Plume-locations field bin for the trial's
Loc; in-odor iff the bin is valid and max-field > cutoff. Load the odor field read-only.

**3.8 Statistics.** Replication unit = trial (D10). Peri-event mean traces with 95 % CI by trial
bootstrap. Correlations = **Spearman** (heavy-tailed speeds). Paired tests = **Wilcoxon
signed-rank** across trials. **Report any raw count as a rate too** (per-second), and lead with the
rate (LESSONS rule 8). **Pair every ethanol/amplitude claim with an absolute-amplitude check**
(compare event ethanol to the real signal range ≈0.14 and to the noise floor ≈4e-4; report the
fraction of events exceeding a physically meaningful 0.01 a.u.) — LESSONS rule 9. Seed 1234;
direction before significance; state the multiple-comparisons posture (per-test CIs, no family-wise
correction across H1–H3).

---

## §4 — Hypothesis 1: mice use nose sweeps to search during odor-guided navigation

**H1.** Nose sweeps are a real, prevalent behavior during navigation **and are temporally
associated with ethanol** — baseline-subtracted ethanol is elevated around sweeps, and sweep
magnitude relates to local odor.
**H0.** Peri-sweep ethanol is no higher than a within-trial time-shuffled baseline, and sweep `R`
is unrelated to local ethanol.
**Tests.** (a) Descriptive prevalence: sweep **rate** (sweeps/s) and count per trial, pooled Loc1–6,
with the per-trial distribution. (b) **Peri-sweep odor enrichment:** mean baseline-subtracted
ethanol in [−0.5, +0.5] s around sweeps vs a **matched-count random-time null** drawn from the same
trials (permutation, seed 1234); paired across trials (Wilcoxon), predicting sweep-window ethanol >
null. (c) Sweep-magnitude vs local odor: Spearman ρ(`R` at peak, summed baseline-subtracted ethanol
in [−0.5,+0.5] s), one point per sweep (Fig 2B). **Report direction before significance.**
**Absolute-amplitude check required** (rule 9): state the ethanol amplitude at sweeps vs the real
signal range, so a noise-floor association cannot masquerade as odor-driven search.
**Accept H1** iff peri-sweep ethanol significantly exceeds the time-shuffled null **and** the
sweep-magnitude/odor association is positive with a CI excluding 0 — otherwise report the honest
result.
**Figures:** F1A, F2B. **Report:** `reactions\reports\H1 - nose sweeps and odor.docx`.

---

## §5 — Hypothesis 2: mice slow the COM during nose sweeps

**H2.** Center-of-mass speed **decreases** around nose sweeps (the animal slows while sweeping).
**H0.** COM speed during sweeps equals its baseline.
**Primary test.** Per trial, mean `v_com` in the during-sweep window [−0.25,+0.25] s vs the trial's
baseline `v_com` (default baseline = median `v_com` over the whole trial; also report the ±1 s
window-edge baseline). Paired **Wilcoxon** across pooled Loc1–6 trials, predicting during < baseline.
Fig 1B shows the peri-sweep average `v_com` trace.
**Mandatory circularity control (D6).** Because sweeps are peaks of `R = v_nose/v_com`, a slow COM
mechanically inflates `R`; a COM dip around sweeps could therefore be partly definitional. The
report **must**: (i) give the nose-driven vs COM-dropout-driven split of sweeps (D6); (ii) **re-run
the H2 test on the numerator-only (body-frame) sweep set (D7)**, which does not contain `v_com` in
its detector; and (iii) headline H2 on that independent test. If the slow-down only appears for
`R`-detected sweeps and vanishes for numerator-only sweeps, report it as **definitional, not
behavioral**.
**Accept H2** iff COM speed is significantly lower during sweeps **for the numerator-only sweep
set** (the non-circular test) — otherwise report the honest/def­initional result.
**Figure:** F1B. **Report:** `reactions\reports\H2 - COM slowdown during sweeps.docx`.

---

## §6 — Hypothesis 3: sweeps occur in regions plausibly reached by ethanol

**H3.** Nose sweeps are **spatially enriched** in odor-reached regions (D9) relative to where the
animal simply spends its time.
**H0.** The in-odor fraction of sweeps equals the in-odor fraction expected from occupancy.
**Test.** Per trial, `f_sweep` = fraction of sweeps in odor-reached bins; `f_occ` = fraction of all
kept head frames in odor-reached bins (occupancy baseline). Also build a **within-trial permutation
null**: draw `n_sweeps` random frame times from the trajectory, compute their in-odor fraction, over
2000 draws → null distribution; the per-trial statistic is `f_sweep − mean(null)`. Aggregate across
pooled Loc1–6 trials with a **Wilcoxon** that `f_sweep > f_occ` (and that `f_sweep − null > 0`),
predicting enrichment. Report the fraction of trials enriched and the pooled effect.
**Accept H3** iff sweeps are significantly enriched in odor-reached bins beyond occupancy —
otherwise report the honest result. Note the odor-field cutoff and that ethanol amplitude at the
mapped bins is above the noise floor (rule 9).
**Figures:** F3A, F3B (illustrative). **Report:** `reactions\reports\H3 - sweeps in odor-reached regions.docx`.

---

## §7 — Figures (exact specifications)

All figures: save **`.png` + `.pdf` + `.txt`** sidecar (provenance + exact numbers drawn) to
`reactions\reports\figures`. Headless Agg; axes labelled with units; pooled = Loc1–6; `anotherLoc`
shown separately only where noted; vertical line at `t = 0` on every peri-sweep panel.

**Figure 1 — peri-sweep averages (two stacked panels, shared x-axis).**
- **F1A (top):** average **baseline-subtracted ethanol** (D8) vs **time to maximal nose-sweep
  velocity**, x ∈ [−1, +1] s (50 ms grid), y = mean ethanol (a.u.); **95 % CI band** (lighter
  shade, bootstrap over trials). Pool all sweeps across Loc1–6.
- **F1B (bottom):** average **`v_com`** (px/s) over the same peri-sweep window and grid, mean +
  95 % CI band. Same sweeps as F1A. Annotate n(sweeps), n(trials).
- File: `F1_peri_sweep_odor_and_com.*`.

**Figure 2 — per-sweep scatters (two panels).**
- **F2A:** `v_nose` (x) vs `v_com` (y), one point per sweep (peak values), pooled Loc1–6; Spearman ρ
  + 95 % CI + p in the annotation. `File: F2A_nose_vs_com.*`.
- **F2B:** `v_nose` at the sweep peak (x) vs **summed baseline-subtracted ethanol over [−0.5,+0.5] s**
  around the peak (y), one point per sweep; Spearman ρ + CI + p. `File: F2B_nose_vs_summed_odor.*`.
  *(May be saved as one 2-panel figure `F2_scatters.*` with A/B subpanels — either is acceptable
  provided both sidecars’ numbers are recorded.)*

**Figure 3 — example trial (two stacked parts).**
- **F3A (top):** the 2D **COM trajectory** of the highest-sweep-rate pooled trial (D12), within the
  arena box (equal aspect), the line **colored by normalized head movement `R(t)`** (colorbar), the
  source `endpoint` marked (×). Title = `file_name`, sweep rate, sweep count.
- **F3B (below A):** two stacked time series for that same trial on the head clock — (i)
  baseline-subtracted **ethanol**, (ii) below it **`R(t)`** — with **small vertical arrowheads at the
  detected sweep-peak times in BOTH series** (same event times). Shared x-axis (seconds).
- File: `F3_example_trajectory_and_timeseries.*`.

---

## §8 — Output paths

| Artifact | Path |
|---|---|
| Shared library + task scripts + probe | `Analysis\reactions\code\` |
| Result HDF5 / JSON (per-trial + per-sweep metrics, per-hypothesis stats) | `Analysis\reactions\data\` (create if absent) |
| Figures (`.png` + `.pdf` + `.txt`) | `Analysis\reactions\reports\figures\` |
| Per-hypothesis reports (`.docx`, one each for H1/H2/H3) | `Analysis\reactions\reports\` |
| New lessons | `Analysis\reactions\learning\LESSONS.md` |
| Plan / contract | `Analysis\reactions\` (`PLAN.md`, `plan.json`) |

Save a tidy `sweeps.(h5|json)` with, per sweep: trial `file_name`, `end_loc`, peak time, `R`,
`v_nose`, `v_com`, nose-driven/COM-dropout flag, summed peri-sweep ethanol, in-odor flag; and a
per-trial table (sweep count, sweep rate, duration, in-odor fractions, H2 during/baseline `v_com`).
Plus `stats.json` with every number the three reports cite. **Reports inject numbers from saved
objects — never hardcode.**

---

## §9 — Definition of done (two gates)

**Gate 1 (code-verifier, fresh context).** Independently re-derives ≥3 numbers per hypothesis from
the accessor + saved objects; confirms: accessor-only reads; both tracks cleaned with the
advancing-reference rule (≈0.5 % removed; the >5 % smell test); everything on the head clock (body &
signal interpolated onto it, never the reverse); the `R` ratio guarded by `v_floor` with the binding
fraction reported; sweep detector parameters and counts reproduce; **rates reported alongside raw
counts** (rule 8); seed 1234; zero placeholder tokens in reports.

**Gate 2 (scientific-auditor, independent).** Checks meaning, not just code: **(i)** the H2
**circularity control is present and headlined** — COM slow-down is validated on the numerator-only
sweep set, not just on `R`-detected sweeps; **(ii)** the **absolute-amplitude check** (rule 9) shows
peri-sweep ethanol is above the noise floor before any "odor-associated" claim; **(iii)** raw counts
are exposure-normalized (rule 8); **(iv)** the **angle/vector and velocity conventions pass a
physical spot-check** (rule 11 analogue: on a trial with an obvious sweep, `R` peaks coincide with a
visible nose excursion; `v_nose`/`v_com` have sane magnitudes in px/s); **(v)** direction before
significance and **honest nulls headlined** if found. No fabricated effects; no self-approval.

**Both gates must pass** (≤2 revise loops at Gate 2). Then `lesson-archivist` appends dated lessons
to `reactions\learning\LESSONS.md`. *(Optional robustness the auditor may request: re-run H1–H3 with
**animal** as a grouping factor using the 3-digit id parsed from `file_name`, to check the
trial-level nulls/effects survive animal-level aggregation.)*

---

## §10 — Gotchas (reuse of standing rules 1–11; do not relearn the hard way)

1. **Advancing-reference de-jump only** — an anchored reference cascades and deletes whole bouts
   (rule 1). Verify ≈0.5 % removed on each track.
2. **The `R = v_nose/v_com` ratio blows up as `v_com → 0`.** Guard with `v_floor` (D4); report how
   often it binds; never let a divide-by-near-zero create phantom "sweeps."
3. **H2 is circular if sweeps are detected on `R`** (COM speed is in the denominator). The
   numerator-only re-test (D6/D7) is mandatory and is what H2's acceptance rests on.
4. **A low quiet-baseline FPR does NOT make an ethanol association real — check absolute amplitude**
   (rule 9). Peri-sweep ethanol must sit above the deconvolved noise floor (~4e-4) and be a
   meaningful fraction of the real range (~0.14) before H1 is called odor-driven.
5. **Exposure/duration confound (rule 8):** report sweep **rate** (per second), not just count; pick
   the Fig 3 example by rate; normalize any count that accrues along a path.
6. **Two clocks:** interpolate body and ethanol onto the ~99 Hz head clock; never resample position
   onto the 500 Hz sensor clock.
7. **Baseline-subtracted ethanol** = raw `ethanol` − rolling 10th-pctile (W = 20 s), on the raw a.u.
   scale (D8); do not confuse with `ethdeconv`. The `threshold` attr is raw-scale.
8. **Differentiation is noisy on a ~99 Hz track** — smooth before/while differencing (D3); report the
   smoothing window; check `v_nose`/`v_com` magnitudes are physically sane (px/s).
9. **`loc`/`duration` attrs are all-NaN** — end location comes from the `file_name` `_Loc(\d+)` token;
   `anotherLoc` is separate.
10. **Replication unit = trial** for the primary run (animal-level is an optional robustness, §9).
11. **Report direction before significance; headline honest nulls.** Every prior hypothesis in this
    repo was null — do not assume these three will differ.
