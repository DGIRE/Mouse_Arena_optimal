# Trajectory Structure & Odor-Guided Orientation — Agent-Ready Analysis Request (Draft 2)

**Repo:** `C:\Projects\Repos\Mouse Arena` **Analysis:** `Analysis\trajectories`
**Supersedes:** `requests\request draft.docx` (original kept alongside; this Draft 2 is the binding spec).
**Author of revision:** prepared for David Gire, 2026-08-08.

This document rewrites the original free-text request into an unambiguous, agent-ready
specification that a Claude CLI agent team can execute end-to-end. Every quantity a
previous run left implicit is pinned down here. Where a choice is genuinely a judgement
call, it appears in **§2 Decisions** as an editable row: **David may edit any D-row before
launch; the planning-architect then treats §2 as binding.**

---

## §0 — How this analysis runs (read first)

**Pipeline (the `.claude` agent team in `Analysis\.claude`).** Launch with working
directory = `C:\Projects\Repos\Mouse Arena\Analysis`, `claude --permission-mode auto`, and
hand it this document. The team runs:

`planning-architect` → `data-analyst` → `code-verifier` **[Gate 1]** →
`figure-builder` + `report-writer` → `scientific-auditor` **[Gate 2]** → `lesson-archivist`.

**Interpreter.** Use the project analysis interpreter resolved from
`Analysis\.claude\settings.json` (referred to here as **`$AR_PY`**). Do **not** hardcode a
Python path in any script or command; call `$AR_PY`. Headless matplotlib (Agg).

**Read the prior lessons FIRST.** Before planning, read
`C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\learning\LESSONS.md`
(standing rules 1–7). They were earned on this exact dataset and this request depends on
them. Write new lessons to `Analysis\trajectories\learning\LESSONS.md` at the end.

**Data access is accessor-only.** Read the aggregate **only** through
`mouse_arena_aggregate_io.Aggregate` (see §1). Never open the `.h5` layout directly, never
modify it.

**One shared library.** Put every cleaning / clock-alignment / geometry / encounter /
tortuosity routine in a single `Analysis\trajectories\code\traj_common.py` imported by all
task scripts, so definitions cannot drift between hypotheses. (This is the "what worked"
lesson from the Plume-locations run.)

**Probe before planning.** Before writing `PLAN.md`, run a short `probe_data.py` that
confirms the data facts this request asserts (114 behavior trials; `_Loc(\d+)` groups
Loc1–Loc6 summing to 105 trials plus `anotherLoc` = 9; head ≈ 99 Hz vs sensor 500 Hz;
signal ranges) against the real aggregate, and write the confirmed numbers into `PLAN.md`.
If any assertion is wrong, STOP with a session note rather than planning around a false
premise.

**Bounded loops.** ≤2 fix iterations at Gate 1, ≤2 revise iterations at Gate 2, then STOP
with session notes. No self-approval; the auditor is independent.

**Determinism.** Global seed = **1234** everywhere randomness enters (bootstraps,
permutations). Record it in every output.

---

## §1 — Data & accessor

**Aggregate:** `C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5`
(schema 0.1, `Fs = 500` Hz, 163 MB, real data; behavior = 114 trials, all
`lighting = infrared`).

**Accessor (read-only):**

```python
import sys; sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\DATA\code")
from mouse_arena_aggregate_io import Aggregate
agg = Aggregate(r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5")
trials = agg.behavior(lighting="infrared")   # list of per-trial dicts (all 114)
```

**Per-trial fields** (one dict per trial from `agg.behavior(...)`):

| Key | Shape | Meaning |
|---|---|---|
| `body` | (Nb, 2) | body-centroid track, px, x=col0 y=col1 |
| `head` | (Nh, 2) | head (sensor) track, px — the ethanol sensor is head-mounted |
| `body_time` | (Nb,) | body-track timestamps, seconds |
| `head_time` | (Nh,) | head-track timestamps, seconds (≈ 99 Hz; often starts several s after 0) |
| `ethanol` | (Ne,) | raw ethanol sensor, a.u., ≈ [−0.28, 1.0] |
| `ethanol_time` | (Ne,) | sensor timestamps, seconds (500 Hz) |
| `ethdeconv` | (Ne,) | deconvolved ethanol, a.u., ≈ [−0.02, 0.14] |
| `endpoint` | (2,) | reward port = **odor source** for this trial, px |
| `file_name` | str (attr) | encodes end-location token `_Loc(\d+)` |
| `threshold` | float (attr) | per-trial threshold, **on the RAW `ethanol` scale** (median ≈ 0.20) |
| `lighting`, `trial_index` | attr | all `infrared`; 0-based index |
| `loc`, `duration` | attr | **all-NaN — NEVER use** |

**Arena extent:** `[0, 580] × [0, 280]` px (x × y). **Units are pixels throughout**
(no calibrated cm or ppm). All arrays 0-based; x = col 0, y = col 1.

**End location = source.** `loc` attr is NaN, so parse the `_Loc(\d+)` token from
`file_name` → **Loc1…Loc6 (105 trials)** each with one exact endpoint (zero spread), plus
**`anotherLoc` (9 trials)** with scattered endpoints. The trial's `endpoint` is that trial's
**odor source** and target for all orientation math. Approximate Loc endpoint centroids (px):
Loc1 (474, 61), Loc2 (506, 114), Loc3 (506, 191), Loc4 (453, 164), Loc5 (441, 129),
Loc6 (506, 61).

---

## §2 — Decisions made explicit (EDITABLE by David; planner treats as binding)

Each row is the default this request will run under. **Edit the “Decision” cell of any row
you disagree with before launch.**

| # | Question | Decision (default) |
|---|---|---|
| **D1** | Which track defines the trajectory geometry (path, tortuosity, distance-to-source, animal location)? | **Body-centroid track** (`body`), cleaned per §3.2. The head track is used for (a) the body-axis vector and (b) mapping ethanol contacts to positions, and as a robustness cross-check. *Rationale: the body centroid is the animal's location; the head carries the sensor and swings.* |
| **D2** | How is the **body axis** (orientation) defined? | Unit vector **from body to head**: `u = (head − body) / ‖head − body‖`, per frame, on the head clock (body interpolated onto `head_time`, §3.3). Head is anterior (nose/sensor), so this points "forward". Frames with ‖head − body‖ < 1 px are undefined and dropped. *(Editable alternative: instantaneous heading = smoothed body-velocity direction.)* |
| **D3** | What is the **direction toward source**, and from where? | From the animal's location `p(t)` (body centroid, D1) to the trial source `S = endpoint`: `s = (S − p(t)) / ‖S − p(t)‖`. |
| **D4** | How is the **angular difference** between body axis and to-source computed? | Absolute unsigned angle `θ(t) = degrees(arccos(clip(u·s, −1, 1))) ∈ [0, 180]`. 0° = perfectly aligned toward source; 180° = facing directly away. |
| **D5** | What counts as an **ethanol encounter** (for the H1 count and H3 contact times)? | Threshold-crossing detector on the head-clock-aligned **`ethdeconv`** trace, calibrated to a **physically meaningful false-positive rate** (LESSONS rule 3): threshold = `k · MAD(quiet, far-from-source baseline)`; scan `k ∈ {5,6,8,10}` and pick the **smallest k** whose pooled quiet-baseline FPR ≤ **0.05 /s** (≈ k=8 on this cohort); an encounter = an upward crossing (onset), with a **0.20 s refractory gap**. Encounter *time* = onset time (head clock). *Do not reuse a permissive threshold; that produced a noise-count artifact last run.* |
| **D6** | How is **tortuosity** defined? | `path_length / straight_line`, on the cleaned track (D1): `path_length = Σ‖Δp‖` over kept consecutive samples; `straight_line = ‖p_end − p_start‖`. Guard `straight_line ≥ 1 px`. *(Same definition Task-1 used; editable alternative: straight-line = start→source distance.)* |
| **D7** | Which trials enter "**all trials across all locations**"? | **Pool Loc1–Loc6 (n = 105).** `anotherLoc` (n = 9, heterogeneous, extreme path lengths/tortuosity) is analysed/plotted **separately** and excluded from the pooled statistics and pooled figures. |
| **D8** | **Replication unit** for statistics? | **Trial.** (Animal-aware summaries are degenerate on this cohort — `file_name` has no animal token — so animal is unavailable; do not attempt per-animal replication.) |
| **D9** | **Distance-to-source binning** for the H2 line plot (F3). | Fixed **20 px** bins from 0 to the max head–source distance observed; per bin, mean of `θ` pooled over all in-bin samples across pooled trials; shade **95% CI** (bootstrap over trials, seed 1234); require ≥ (a stated minimum, default 30) samples per plotted bin else drop the bin. |
| **D10** | **Peri-contact** window and averaging for H3 (F4). | Window **−1.0 s to +1.0 s** around each encounter onset, sampled on the head clock at a fixed grid (e.g. 50 ms steps). Pool all encounters across all pooled trials; per relative-time bin, mean `θ` with **95% CI** (bootstrap over **trials**, seed 1234). Contacts whose window runs past the track ends contribute only their in-range samples. Mark t = 0 with a vertical line. |
| **D11** | **Signal used for encounter detection** (D5) vs the raw threshold. | Detection uses `ethdeconv` (deconvolved), consistent with the calibrated-FPR method. The per-trial `threshold` attr (raw scale) is **not** used as the encounter detector here; if a comparison to the raw-`threshold` crossing count is wanted, report it as a secondary descriptive only. |
| **D12** | **F1 reference line.** | The original draft asked for a "dashed red unity line" on the encounters-vs-tortuosity scatter, but a y = x identity is meaningless across these incommensurable axes. Replace it with a **dashed red fitted trend line** (OLS of tortuosity on encounter count, or a LOWESS/robust fit) plus the Spearman ρ in the annotation. *(Editable: omit the line entirely.)* |
| **D13** | **F2 example count.** | Show the **3 most** and **3 least** tortuous trials (6 example paths), pooled Loc1–6. *(Editable: change N, or use 1 + 1.)* |

---

## §3 — Shared definitions (single source of truth → implement once in `traj_common.py`)

**3.1 End-location grouping & source.** Parse `_Loc(\d+)` from `file_name`. Trials with a
`Loc1…Loc6` token form the pooled set (n = 105); `anotherLoc` (n = 9) is separate (D7). Each
trial's `endpoint` is its source `S`.

**3.2 Track cleaning (both tracks).** For each track independently: (1) drop non-finite
samples; (2) clip/keep only samples inside the arena box `[0,580] × [0,280]` (the head track
carries large out-of-arena excursions — observed x ∈ [−607, 929]); (3) **advancing-reference
global de-jump** at the 99.5th-percentile step size (compare each sample to the **last
accepted** position, not the raw previous sample, so one outlier does not drag the reference
— this is LESSONS rule 1; the anchored variant cascades and deletes whole bouts). Reuse the
exact rule from `Plume locations\code\plume_common.clean_track`. **Smell test:** the de-jump
should remove ≈ 0.5 % of samples per track; if it removes > ~5 %, STOP — the reference rule
is wrong.

**3.3 Clock alignment (two clocks).** `ethanol_time`/`ethdeconv` are 500 Hz; `head_time`
≈ 99 Hz and may start seconds after t = 0; `body_time` is its own clock. Same seconds origin.
Bring signals and body onto the **head clock**:
`sig_h = np.interp(head_time, sensor_time, sig, left=nan, right=nan)`;
`body_h[:,k] = np.interp(head_time, body_time, body[:,k])` for k in {x, y}. **Never** resample
position onto the sensor clock. All per-frame geometry (D2–D4) is evaluated on the head clock
after cleaning both tracks and interpolating.

**3.4 Body-axis vector `u(t)`** — D2. **3.5 To-source vector `s(t)` & angle `θ(t)`** — D3–D4.

**3.6 Encounter detection** — D5. Define the "quiet, far-from-source baseline" as samples
whose head–source distance exceeds the 80th percentile *and* whose `ethdeconv` is below its
per-trial median (pool such segments across trials to estimate MAD), consistent with the
Plume-locations enhancement calibration. Report the chosen `k`, threshold, and the achieved
quiet FPR.

**3.7 Tortuosity & path length** — D6 (on the D1 track). Also expose per-trial
`n_encounters` (D5) and `frac_path_above_threshold` (fraction of kept samples whose aligned
`ethdeconv` exceeds the encounter threshold) for context.

**3.8 Distance-to-source** `d(t) = ‖p(t) − S‖` on the D1 track (and head–source distance for
the baseline definition in 3.6).

**3.9 Statistics conventions.** Replication unit = trial (D8). Report **direction before
significance** and **headline null results honestly** (LESSONS rule 6). Correlations:
**Spearman** ρ with 95% CI by trial bootstrap (the tortuosity distribution is heavy-tailed —
median ≈ 6, IQR ≈ [3.3, 12.8] — so use rank statistics, not raw-scale OLS, for H1). Per-trial
slopes tested across trials with **Wilcoxon signed-rank**. State the multiple-comparisons
posture explicitly (per-test CIs, no family-wise correction, direction first). Seed 1234.

---

## §4 — Hypothesis 1: more ethanol encounters ⇒ straighter (less tortuous) search

**H1.** Across pooled Loc1–6 trials, the number of ethanol encounters is **negatively**
associated with trajectory tortuosity (more encounters → straighter path).
**H0.** No monotonic association (ρ = 0).
**Test.** Spearman ρ(`n_encounters`, `tortuosity`), unit = trial, pooled Loc1–6 (n = 105);
95% CI by trial bootstrap (seed 1234); also report per-location ρ. Report `anotherLoc`
separately.
**Accept H1** if ρ < 0 with a 95% CI excluding 0; otherwise report the honest direction and
non-significance.

> **Prior evidence (read and reconcile).** The Plume-locations Task-1 run computed exactly
> this association on the same 105 trials and found `tortuosity vs n_encounters` **ρ = +0.176,
> 95% CI [−0.016, 0.356], p = 0.072** — i.e. weak, non-significant, and in the *opposite*
> (positive) direction to H1. It also found `tortuosity vs fraction-of-path-above-threshold`
> **ρ = −0.532 [−0.656, −0.378], p = 5.4e-9** (straighter paths spend a larger fraction of
> their shorter path in odor). The team must (a) reproduce these numbers as a sanity check
> under this request's encounter definition (D5), (b) report H1's true direction rather than
> assuming the negative prediction, and (c) note the encounter-count vs frac-above-threshold
> distinction. Encounter counts are low on this cohort (per-trial median ≈ 0–1), so state the
> limited dynamic range as a caveat.

**Figure F1** (§7). **Report:** `trajectories\reports\H1 - encounters vs tortuosity.docx`.

---

## §5 — Hypothesis 2: body axis aligns toward the source as the animal nears it

**H2.** The absolute body-axis-to-source angle `θ` **decreases as the animal approaches the
source** — equivalently `θ` increases with distance-to-source `d`.
**H0.** `θ` is independent of `d` (zero slope).
**Test.** Per trial, OLS slope of `θ(t)` on `d(t)` over kept head-clock frames; **Wilcoxon
signed-rank** that per-trial slopes are **> 0** across pooled Loc1–6 trials (positive slope =
larger angle when farther = better alignment when closer). Also report the pooled binned
relationship (F3) and a pooled OLS for the figure line. Direction before significance.
**Accept H2** if the per-trial slopes are significantly > 0 (Wilcoxon) **and** the F3 binned
curve rises with distance.

**Figure F3** (§7). **Report:** `trajectories\reports\H2 - alignment vs distance.docx`.

---

## §6 — Hypothesis 3: animals reorient toward the source upon an ethanol encounter (peri-contact)

**H3.** Following an ethanol encounter, the body axis **turns toward the source** — `θ`
decreases from before to after the contact onset.
**H0.** `θ` is unchanged across the contact (pre = post).
**Test.** For each encounter (D5), sample `θ` on the −1.0…+1.0 s peri-contact grid (D10).
**Inferential (replication = trial):** per trial with ≥1 encounter, mean `θ` in a **pre**
window (−1.0…0 s) vs a **post** window (0…+1.0 s); paired **Wilcoxon** across those trials
that post < pre. **Descriptive:** the pooled peri-contact mean-`θ` curve with 95% CI (F4).
Direction before significance; if encounters are too few for a stable estimate, say so and
report the contact-pooled curve as descriptive only.
**Accept H3** if the trial-level paired test shows post `θ` significantly below pre `θ`.

**Figure F4** (§7). **Report:** `trajectories\reports\H3 - peri-contact reorientation.docx`.

---

## §7 — Figures (exact specifications)

All figures: save **both** `.png` and `.pdf` plus a `.txt` sidecar (data provenance +
the exact numbers drawn) to `trajectories\reports\figures`. Headless Agg. Label axes with
units (px, degrees, seconds, counts). Pooled = Loc1–6; show `anotherLoc` separately where
noted.

**F1 — Encounters vs tortuosity scatter** (`F1_encounters_vs_tortuosity.*`). One point per
pooled Loc1–6 trial: x = `n_encounters`, y = `tortuosity`. Dashed **red fitted trend line**
(D12), Spearman ρ + 95% CI + p in the annotation. Optionally color points by end-location.
Plot `anotherLoc` points in a distinct marker or a small inset, excluded from the fit.

**F2 — Most/least tortuous example paths** (`F2_example_paths.*`). Two columns
(most-tortuous | least-tortuous) × D13 rows (default 3 each). **Each cell = a stacked pair:**
*top* = the x,y trajectory (cleaned track, D1) with **jet-colored ethanol contacts**
(scatter of encounter positions on the head track, colored by aligned `ethdeconv`); source
`endpoint` marked (e.g. white/red ×); equal aspect, arena box. *bottom* = that trial's
ethanol time series (`ethdeconv` on the head clock, with the encounter threshold line and
detected onsets). **Title each example with the trial `file_name`** and its tortuosity.

**F3 — Alignment vs distance-to-source** (`F3_angle_vs_distance.*`). x = distance to source
`d` (px, 20-px bins, D9); y = mean absolute angle `θ` (degrees); line + **95% CI band**
(bootstrap over trials). Pooled Loc1–6. Annotate the H2 per-trial-slope Wilcoxon result.
Optional faint per-location lines.

**F4 — Peri-contact reorientation** (`F4_peri_contact_angle.*`). x = peri-contact time
(−1.0…+1.0 s, D10); y = mean absolute angle `θ` (degrees); line + **95% CI band** (bootstrap
over trials); **vertical line at t = 0** (contact onset). Pooled over all encounters across
Loc1–6. Annotate n(contacts) and n(trials contributing) and the H3 pre-vs-post Wilcoxon.

---

## §8 — Output paths

| Artifact | Path |
|---|---|
| Shared library + task scripts + probe | `Analysis\trajectories\code\` |
| Result HDF5 / JSON (per-trial metrics, per-hypothesis stats) | `Analysis\trajectories\data\` (create if absent) |
| Figures (`.png` + `.pdf` + `.txt`) | `Analysis\trajectories\reports\figures\` |
| Per-hypothesis reports (`.docx`) | `Analysis\trajectories\reports\` |
| New lessons | `Analysis\trajectories\learning\LESSONS.md` |
| Plan / contract | `Analysis\trajectories\` (`PLAN.md`, `plan.json`) per the pipeline |

Save a single tidy `trajectory_metrics.(h5|json)` with per-trial `file_name`, `end_loc`,
`n_encounters`, `tortuosity`, `path_length`, `straight_line`, `frac_path_above_threshold`,
per-trial H2 slope, and per-trial pre/post peri-contact `θ`; plus a `stats.json` with every
number the reports cite. **Reports inject numbers from saved objects — never hardcode.**

---

## §9 — Definition of done (two gates)

**Gate 1 (code-verifier, fresh context).** Independently re-derives ≥3 numbers per hypothesis
from the accessor + saved objects; confirms: accessor-only reads; both tracks cleaned with the
advancing-reference rule (≈0.5 % removed — the >5 % smell test); signals interpolated onto the
head clock (never the reverse); encounter detector calibrated to quiet-FPR ≤ 0.05/s with the
`k`-scan reported; `θ ∈ [0,180]`; replication unit = trial; `anotherLoc` excluded from pooled
stats; seed 1234 recorded; zero placeholder tokens in reports. **Re-derive any
boundary/extreme selection** (e.g. the chosen `k`) rather than accepting a plausible
justification (LESSONS "lesson for the verifier").

**Gate 2 (scientific-auditor, independent).** Checks scientific validity, not just code:
encounter counts are physically interpretable (not noise), H1 direction reported honestly
against the prior +0.176 evidence, H2/H3 slopes and peri-contact effects not driven by a
handful of trials, angle conventions correct (spot-check a trial where the animal visibly
faces the port → small `θ`), CIs present, direction-before-significance throughout, and
**null results are headlined honestly** if found. No fabricated effects.

**Both gates must pass** (≤2 revise loops at Gate 2) before the run is done. Then
`lesson-archivist` appends dated lessons to `trajectories\learning\LESSONS.md`.

---

## §10 — Gotchas (reuse of standing rules; do not relearn the hard way)

1. **Advancing-reference de-jump only** — an anchored reference cascades and can delete
   84–98 % of a track (LESSONS rule 1). Verify ≈0.5 % removed.
2. **Calibrate the encounter detector to a low, physically meaningful FPR** (≤0.05/s on quiet
   baseline). A permissive threshold turns noise crossings into "encounters" and manufactures
   spurious significance (LESSONS rule 3).
3. **Two clocks:** interpolate signal (and body) onto the head clock with `np.interp`,
   NaN outside support; never resample position onto the 500 Hz sensor clock.
4. **`ethdeconv` ≈ [−0.02, 0.14]; raw `ethanol` ≈ [−0.28, 1.0]; `threshold` attr is RAW-scale.**
   Do not compare `threshold` to `ethdeconv`.
5. **Never use `loc`/`duration` attrs (all-NaN).** End location comes from the `file_name`
   `_Loc(\d+)` token; `anotherLoc` is separate.
6. **Replication unit = trial;** animal is unavailable on this cohort.
7. **Report direction before significance; headline honest nulls.** H1's prior evidence is a
   weak *positive* (opposite the prediction) non-significant ρ — do not overclaim.
8. **Angle sanity check:** `θ` must be small when the body axis visibly points at the port on
   an example trial; if it is systematically large, the vector convention (head−body vs
   body−head, or x/y order) is flipped.
