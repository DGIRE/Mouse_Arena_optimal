# PLAN — Selective Sampling Bouts & Odor Reactions (reactions_2)

**Plan version:** 1.0 · **Prepared:** 2026-08-08 · **Architect:** planning-architect (Opus)
**Request:** `requests/Selective sampling-bout request (agent-ready).md` (binding; D1–D12 adopted).
**Redesign of:** `Analysis/reactions` v1 (replaces the R≥1.5 "sweep" with a rare pause+cast bout).
**Prior lessons read:** Plume (1–7), trajectories (8–11), reactions (12–15). New → `reactions_2/learning/LESSONS.md`.

Facts marked **[probed]** confirmed by `code/probe_data.py` → `data/_probe.json`.

## 0. Goal, deliverable, hypotheses (direction before significance; nulls headlined)

Define a **rare, deliberate sampling bout** (locomotor pause + head cast) via a
**translation-invariant** kinematic (head-body bearing angular speed ω), then test
whether these events — not incidental motion — are driven by / directed toward odor.

- **Deliverable A (required, not a hypothesis):** bout definition, **rarity** (rate ≪
  v1's 1.7/s), **selectivity** vs incidental motion, and a visual sanity check.
- **H1** — peri-bout baseline-subtracted ethanol > matched within-trial null AND >
  incidental-event peri-odor. Accept iff both.
- **H2** — odor **precedes** bout onset: pre-onset ethanol [−0.75,−0.25]s > trial
  baseline/null with positive onset-aligned slope over [−1,0]s, surviving
  incidental-event and spatial (odor-reached vs absent) controls. (Non-circular
  replacement for v1's definitional "COM slows".) Accept iff all hold.
- **H3** — bout onset locations enriched in odor-reached bins beyond occupancy
  (f_bout > f_occ and > within-trial permutation null). Accept iff enriched.

## 1. Data scope & exclusions [probed]

114 infrared trials; pooled **Loc1–6 (105)**; **anotherLoc (9) separate** (D10).
Accessor-only. Nose=head, COM=body. Excluded: loc/duration (all-NaN [probed]);
out-of-arena/non-finite; de-jump outliers; anotherLoc from pooled; frames outside
sensor coverage (NaN eth). Only trials with ≥1 bout enter bout-conditioned tests.

## 2. Shared library `code/reactions2_common.py`

Imports `plume_common` (clean_track advancing-ref de-jump, mad, group_of,
pooled_dejump_Q, align_signal) and **reuses** `reactions/code/reactions_common.py`
(speed_savgol, interp_xy_to_head, baseline_subtract_ethanol, load_odor_field,
is_in_odor, peri_event_matrix, robust_sd) — no re-implementation (rule 15). Adds:
- `bearing_phi(head, body_h)` = unwrapped deg atan2(head−body); `angular_speed_omega
  (phi, dt)` = |savgol deriv| (deg/s), smoothed **after** which we differentiate (rule 8).
- `detect_pauses(v_com, t, v_pause, tau_pause)` → contiguous runs of v_com<v_pause of
  length ≥ tau_pause (D3).
- `qualifying_cast(phi, omega, seg)` → cumulative |Δφ| over the pause ≥ Δφ_min AND
  peak ω ≥ ω_min (D4).
- `detect_bouts(v_com, phi, omega, t, params)` → pauses containing ≥1 cast, merged if
  onsets < t_merge apart; returns onset idx, peak-ω idx, duration, peak ω, excursion,
  mean v_com (D5).
- `detect_incidental(v_com, omega, t, params)` → high-ω events while **moving**
  (v_com ≥ v_pause), same ω/refractory logic (D7 contrast class).
- Odor-reached lookup reuses `is_in_odor` on the Plume `odor_fields.h5` (D9), cutoff
  `max(3·MAD,1e-3)` = **0.001** [Plume stats].

**Self-check:** reuse reactions_common self-check; bearing of a due-east head→0°, a
90° rotation gives ω≈90/dt·… (a synthetic constant-rotation trace gives constant ω);
a synthetic pause+cast is detected as one bout; a moving high-ω event is incidental
not a bout; ω differentiation sane.

## 3. Parameters (justified) [probed] — D6 rarity gate PASSES at defaults

| Param | Value | Source |
|---|---|---|
| v_pause | 25th pct pooled v_com = **5.89 px/s** | D3 [probed] |
| τ_pause | 0.30 s | D3 |
| Δφ_min | 40° | D4 |
| ω_min | 90th pct pooled ω = **156.6 °/s** | D4 [probed] |
| t_merge | 0.50 s | D5 |
| baseline eth | raw − rolling 10th-pct W=20 s → head clock (raw scale) | D8 |
| peri window | ±1.0 s, 50 ms grid; pre-onset [−0.75,−0.25]s; peri-odor [−0.5,+0.5]s | D11 |

**D6 gate [probed]:** default pooled **median bout rate ≈ 0.007/s** (median 1 bout/
trial, max 8; **65% of trials ≥1 bout**, 35% zero) — ≪ v1's 1.7/s and far below the
0.5/s tighten trigger → **gate PASSES; keep defaults, do NOT loosen** (loosening risks
re-admitting routine motion, rule 13). The rate is below the aspirational 0.05–0.3/s
target — accepted as maximally specific; the resulting **modest N (~68 contributing
trials) is a documented power caveat**. The analyst re-derives the achieved rate with
the real detector and applies D6 (tighten only if >0.5/s); report final params + rate.

**Stats [rules 8/9/14]:** lead with **rate** not counts; **absolute-amplitude check**
(peri-bout eth vs ~4e-4 floor & ~0.14 range; fraction of bouts peri-odor>0.01) before
any odor claim — above-floor necessary not sufficient; **trial-level inference only**
(Wilcoxon / trial bootstrap 2000, seed 1234), **never per-event point-bootstrap**;
lead with magnitude not p; per-test CIs, no family-wise correction; seed 1234.

## 4. Deliverables (paths under `Analysis/reactions_2/`)

| Artifact | Path |
|---|---|
| Shared lib + scripts + probe | `code/reactions2_common.py`, `code/build_bouts.py`, `code/probe_data.py` |
| Per-bout + per-trial + stats | `data/bouts.h5`, `data/bouts.json`, `data/stats.json` |
| Figures (png+pdf+txt) | `reports/figures/F1_bout_definition.*`, `F2_peri_bout.*`, `F3_spatial.*` |
| Reports (docx) | `reports/Sampling-bout definition and selectivity.docx`, `H1 - sampling bouts and odor.docx`, `H2 - odor precedes sampling.docx`, `H3 - sampling bouts in odor-reached regions.docx` |
| Plan/audit/notes | `PLAN.md`, `plan.json`, `audit_report.md`, `SESSION_NOTES.md` |
| Lessons | `learning/LESSONS.md` |

`bouts.h5`: per-bout (file_name, end_loc, onset_time, peak_time, duration, peak_ω,
excursion, v_com_during, in_odor, peri_onset_odor level+slope) + per-trial table (bout
count, **rate**, n_incidental, f_bout, f_occ, pre-onset-odor stats) + per-trial arrays
for figures (head/body tracks, v_com, ω, baseline-sub eth on head clock, bout onset/peak
times, incidental times). `stats.json`: every number the reports cite. **Reports inject;
never hardcode.** HDF5: gzip4+shuffle ≥256 elems, .tmp→os.replace, build_complete=1 last.

## 5. Acceptance / two gates (§10)

- **Gate 1 (code-verifier, fresh):** accessor-only; advancing-ref clean ≈0.5% (<5%);
  head-clock interp (never reverse); sweep kinematic **translation-invariant** (bearing
  of head−body, no v_com denominator); **D6 rarity gate passes** (median rate ≪1.7/s)
  with final params; rates alongside counts; **trial-level inference** (no point-
  bootstrap); ≥3 numbers/deliverable re-derived incl. the achieved bout rate (boundary);
  seed 1234; zero placeholders.
- **Gate 2 (scientific-auditor, independent):** (i) events rare & not ratio/denominator-
  biased — low-COM is **definitional not a result**; (ii) rarity gate satisfied, states
  most head motion isn't sampling; (iii) amplitude check precedes odor claims; (iv)
  inference leads with magnitude + trial-level CIs, not N-driven p; (v) **H2 precedence
  non-circular**, survives incidental + spatial controls; (vi) kinematic convention
  spot-check (bouts ↔ visible head casts during pauses); (vii) direction before
  significance, honest nulls. ≤2 revise loops then STOP with SESSION_NOTES.md.

## 6. Task graph
1. [me] plan + `reactions2_common.py` (+ self-check).
2. [data-analyst] `build_bouts.py` → kinematics/bout+incidental detection (D6 gate) →
   per-bout/per-trial + Deliverable-A + H1/H2/H3 stats. Slice-first.
3. [fresh code-verifier] Gate 1.
4. [figure+report agents ∥] Deliverable A (F1), H1 (F2A), H2 (F2A+F2B), H3 (F3), from saved objects.
5. [fresh scientific-auditor] Gate 2 → audit_report.md.
6. [me] archive → learning/LESSONS.md; SESSION_NOTES.md.

**Invariants:** no self-approval; verifier & auditor fresh/independent; never mark
human-approved; a bounded stop is success (SESSION_NOTES.md).
