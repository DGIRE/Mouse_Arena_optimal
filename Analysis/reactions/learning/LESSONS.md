# LESSONS — Nose-Sweeps / Reactions analysis

Fed forward to the next run. Builds on `Plume locations/learning/LESSONS.md` (rules
1–7) and `trajectories/learning/LESSONS.md` (rules 8–11), which still apply. New
standing rules 12–15 below.

## Standing rules (new this project)

12. **A ratio-triggered detector is biased toward its denominator — validate on a
    numerator-only detector.** Sweeps were peaks of `R = v_nose/v_com`; the R-detector
    preferentially fired on low-COM frames (v_com@peak median ≈3 vs ≈11 px/s
    trial-wide). Any claim about the denominator (H2: "COM slows during sweeps") is
    then partly definitional. **Re-run the denominator test on an independent
    numerator-only detector** (here body-frame nose speed ‖d/dt(head−body)‖, no v_com).
    It showed COM is *higher*, not lower, during sweeps → the effect was not merely
    definitional, it was absent. Concrete instance of rule 3.
13. **A permissive kinematic threshold makes "events" that are mostly routine motion.**
    "Sweep" = R≥1.5 gave a median of 111 sweeps/trial (rate ≈1.7/s) — far too frequent
    to be discrete search acts. Report the **rate**, pick examples by rate, and state
    plainly that most detected events are routine nose motion, not the hypothesized
    behavior. Extends rule 8.
14. **Huge-N-of-events significance is not an effect.** H1c Spearman ρ=−0.028 had
    p=3.4e-5 only because there were 21,841 sweeps (one point per sweep). **Lead with
    effect magnitude (≈0), and do inference with TRIAL-bootstrap CIs, not
    point-bootstrap.** A per-point CI is a figure-descriptive of the scatter, never the
    inferential statistic. Extends rules 8/9.
15. **Reusing prior validated outputs across analyses works and is cheap.** `plume_common`
    (clean_track, mad, align_signal, group_of) and the Plume `odor_fields.h5`
    (read-only, for the H3 odor-reached lookup) both propagated cleanly; the de-jump
    smell test passed first try. Keep a thin per-project `*_common.py` that imports the
    validated primitives rather than re-implementing them.

## Repo-level observation (four analyses in)

Every hypothesis tested in this repo so far has returned **null** at physically
meaningful thresholds: Plume Task-2 enhancement (no distal recovery), Trajectories
H1–H3 (encounters↔tortuosity is a path-length artifact; no alignment-with-distance;
no peri-contact reorientation), and Reactions H1–H3 (no peri-sweep odor enrichment; no
COM slowdown; no odor-reached spatial enrichment). The honest reading is that this
single infrared cohort's head-mounted ethanol signal, at defensible detection
thresholds, does **not** support fine-grained odor-guided sensorimotor structure.
Future requests should pre-register null-tolerant acceptance criteria and beware
noise-floor / exposure / ratio-circularity artifacts that manufacture apparent effects.

## 2026-08-08 — Nose sweeps & odor-guided search (H1/H2/H3)

**Outcome:** Completed; PASSED Gate 1 (code) and Gate 2 (science) — **Gate 2 passed on
the first audit** (no BLOCKER/MAJOR; 3 MINOR doc notes). **All three hypotheses null**,
reported honestly:
- **H1** (sweeps ↔ ethanol): peri-sweep baseline-sub ethanol not above the matched
  random-time null (Wilcoxon p=0.120); sweep-magnitude↔odor ρ=−0.028 (negligible,
  negative). Peri-sweep ethanol is above the noise floor (median 0.022; 78.6% >0.01)
  but small vs the 0.14 range. Not supported.
- **H2** (COM slows during sweeps): NOT supported and opposite — COM is *higher* during
  sweeps on both the R-set and the non-circular numerator-only set (during 42 vs
  baseline 17 px/s; Wilcoxon during<baseline p=1.0). `slowdown_survives_numerator_only
  =False`.
- **H3** (sweeps enriched in odor-reached regions): NOT supported — f_sweep 0.336 ≈
  f_occ 0.349 (Wilcoxon p=0.150; 54% of trials enriched ≈ chance). Sweeps track
  occupancy.

**What worked:** the shared-library + probe-first + two-gate pattern; the mandatory
numerator-only control (D6/D7) cleanly resolved the H2 circularity; reusing the Plume
odor field for H3.

**What to watch (root causes):** ratio-detector denominator bias (rule 12); permissive
threshold → routine-motion "events" (rule 13); N-driven pseudo-significance (rule 14).

**New standing rules added:** 12–15 above.
