# LESSONS — Selective Sampling Bouts (reactions_2)

Fed forward. Builds on Plume (rules 1–7), trajectories (8–11), reactions (12–15),
which still apply. New standing rules 16–19 below.

## Standing rules (new this project)

16. **To target rare, deliberate events, use a CONJUNCTION + a binding rarity gate.**
    A single kinematic threshold reproduces routine motion (v1: 1.7/s). Defining a
    "sampling bout" as the conjunction of independent conditions — a locomotor **pause**
    (v_com<25th-pct for ≥0.30 s) AND a large **head cast** (cumulative bearing excursion
    ≥40° with peak ω≥90th-pct) — plus a **rarity gate** (tighten until pooled median
    rate ≪ the over-detection baseline) cut the rate ~232× (1.7/s → 0.0073/s, median 1
    bout/trial). This is the reusable recipe for "rare deliberate behavior" detectors.
17. **Use a translation-invariant kinematic and PROVE the invariance.** The head-body
    bearing angular speed ω=|d/dt·atan2(head−body)| depends only on (head−body), so it
    is unaffected by whole-body translation — avoiding the ratio-detector denominator
    bias (rule 12). Verify numerically in the self-check (ω unchanged under a position
    offset and under adding a common COM-velocity ramp). Do NOT put v_com in the event
    kinematic; v_com belongs only in the pause condition.
18. **Label per-event vs per-trial summaries and cite the replication-unit one.** The
    per-event medians stored for the figure clouds differed ~27% from the authoritative
    median-of-per-trial-means (v_com 0.19 vs 0.14; peak ω 654 vs 830). Both are correct
    but answer different questions; reports must cite the **trial-level** (replication-
    unit) summary and label figure scatter as per-event. Don't call a 27% gap "slight."
19. **A clean null can be COHERENT and directional — that is a real result.** On genuine
    rare sampling bouts, all three odor hypotheses were null *and pointed the opposite
    way*: peri-bout ethanol was LOWER than a matched null (H1), odor did NOT rise before
    onset while **incidental** motion DID show pre-odor (H2 — a useful specificity
    contrast), and bouts were UNDER-represented in odor-reached regions (H3, f_bout 0.0
    vs f_occ 0.31). The pre-registered rarity gate + non-circular H2 + amplitude/trial-
    level rules kept this honest instead of manufacturing an effect.

## Repo-level observation (five analyses in)

Every hypothesis tested in this repo has returned a physically-meaningful **null** at
defensible thresholds: Plume enhancement; Trajectories H1–H3; Reactions v1 H1–H3; and
now Reactions_2 (sampling bouts) H1–H3 — where the events are, coherently, associated
with *less* odor, not more. The consistent reading: this single infrared cohort's
head-mounted ethanol signal does not support fine-grained odor-guided sensorimotor
structure. This is itself a robust, reportable finding; future requests should keep
pre-registering null-tolerant acceptance and guard against noise-floor / exposure /
ratio-circularity / N-driven artifacts.

## 2026-08-08 — Selective sampling bouts & odor reactions (Deliverable A + H1/H2/H3)

**Outcome:** Completed; PASSED Gate 1 (code) and Gate 2 (science) — **both gates on the
first pass** (Gate 2: no BLOCKER/MAJOR, 3 MINOR). The redesign of reactions v1 worked:
- **Deliverable A:** rare, selective bouts — median rate 0.0073/s (232× rarer than
  v1's 1.7/s), median 1/trial, 63.8% of trials ≥1; bouts vs incidental differ in
  defining kinematics (v_com 0.14 vs 52 px/s [definitional]; peak ω 830 vs 339 °/s).
- **H1** (odor-associated): NOT supported — peri-bout ethanol (0.014) *below* the
  matched null (0.029), p≈1.0; not > incidental. Above noise floor but the null test
  is negative.
- **H2** (odor precedes onset): NOT supported — no pre-onset rise (p=0.65), slope n.s.;
  incidental events *do* show pre-odor (p=1.7e-8), so bouts aren't the odor-triggered
  class. Non-circular (replaces v1's definitional COM-slows).
- **H3** (spatial enrichment): NOT supported — f_bout 0.0 < f_occ 0.31, p≈1.0; bouts
  under-represented in odor-reached bins.

**What worked:** conjunction+rarity-gate detector (rule 16); proven translation-
invariant kinematic (rule 17); reusing plume_common + reactions_common + the Plume
odor field; the non-circular H2 with incidental & spatial controls.

**New standing rules added:** 16–19 above.
