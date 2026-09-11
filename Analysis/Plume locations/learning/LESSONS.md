# LESSONS — Plume Locations analysis

Fed forward to the next run: the planning-architect reads this first. Append dated
entries; keep standing rules at the top current.

## Standing rules (read before planning)

1. **Head-track de-jump must use an ADVANCING reference.** Cleaning the ~99 Hz head
   track by dropping steps > Q (99.5th-pctile pooled) only works if the reference
   sample advances every frame (consecutive-difference rule). An *anchored*
   reference that advances only on a keep **cascades**: after one > Q jump, the
   mouse's slow drift away from the stale anchor accumulates past Q and deletes the
   whole movement bout (observed 42898 → 926 samples; ~84–98% loss). The correct
   rule removes ~0.5% of samples. See `plume_common.clean_track`.
2. **"Smallest bin meeting a coverage floor" means iterate for the MINIMUM passing
   parameter, not the first hit.** A descending scan that locks the first L meeting
   the target returns the *coarsest* grid — the opposite of the intent. Return
   `min(L : coverage(L) ≥ target)`. (Cost us a BLOCKER + a full Task-1 re-run.)
3. **Calibrate detectors to a PHYSICALLY MEANINGFUL false-positive rate.** A
   "matched FPR" is only meaningful if the target rate is low. Targeting 0.5/s made
   the quiet-baseline detector fire every ~2 s, so encounter counts were noise and
   a paired test's tiny p-value reflected N, not biology. Set the threshold at
   k·MAD of a quiet far-from-source baseline with k chosen so the quiet FPR → ~0
   (here k=8 → 0.03/s), then match the second detector to that same low rate.
4. **Cross-scale SNR must be dimensionless.** Compare before/after via
   peak_amp / local-MAD *of the same trace* (a unitless peak-to-noise ratio) so a
   drift-corrected-amplitude trace and a matched-filter score trace are
   commensurable. Never subtract raw amplitude from a correlation score.
5. **A null needs sampling variability.** `gini(ones)=0` is an analytic floor, not
   a test. Use a Monte-Carlo null (redistribute the observed mass across the same
   bins with realistic per-bin sample counts, many seeded draws → null
   distribution + CI + p).
6. **Report direction before significance, and headline null results.** At a
   meaningful FPR the enhancement did NOT recover distal encounters (Wilcoxon
   p≈0.885; distal SNR gain negative for 87/114 trials). That is the honest primary
   finding; the H5 no-fabrication guard holding (after FPR ≤ before) is the positive.
7. **Data facts to reuse:** ethdeconv ∈ ~[-0.02, 0.14]; raw ethanol ∈ ~[-0.28, 1.0];
   `threshold` attr is on the RAW scale (median 0.20), NOT ethdeconv. head ~99 Hz,
   sensor 500 Hz, ~2% of head samples out of the [0,580]×[0,280] box, head-in-sensor
   coverage mean 0.98. `loc`/`duration` trial attrs are all-NaN — never use them;
   end location comes from the `file_name` `_Loc(\d+)` token. `file_name` has no
   6-digit animal token → animal-aware summaries are degenerate this cohort.

---

## 2026-08-07 — Odor-field maps (Task 1) + signal enhancement (Task 2)

**Outcome:** Both tasks completed and PASSED Gate 1 (code) and Gate 2 (science,
after one scoped revision). Deliverables at the paths in PLAN.md §4.

**What worked**
- A single shared library (`plume_common.py`) imported by both tasks kept cleaning,
  clock-alignment, grouping and encounter-detection identical — no divergence, and
  one bug fix propagated to both.
- Probing the data (`probe_data.py`) before planning confirmed every request claim
  (7 groups summing to 114, scales, coverage) so the plan used ground truth.
- Independent Gate-1 re-derivation matched to 1e-19 (a Loc bin mean) / exactly (a
  trial's before-count); independent Gate-2 re-derivation of the baseline FPR from
  stored traces confirmed the H5 guard.

**What failed + root cause**
- *De-jump cascade* (root cause: anchored reference) — caught pre-Gate-1 by a
  92%-removal smell test → standing rule 1.
- *Bin-size inversion* (root cause: `if frac≥target and chosen is None` on a
  descending scan) — Gate 1 missed it (accepted L=40 as a "data limitation"); Gate 2
  caught it by re-deriving the L-vs-coverage table → standing rule 2. **Lesson for
  the verifier:** when a selection rule returns the boundary/extreme value, re-derive
  the full scan rather than accepting a plausible-sounding justification.
- *Noise-dominated "recovery"* (root cause: implausible 0.5/s target FPR) — Gate 2
  caught it → standing rules 3–4, 6. Recalibration flipped a spurious p≈1.9e-6
  "recovery" into an honest null (p≈0.885).
- *Trivial null* (gini(ones)) → standing rule 5.

**Standing rules added:** 1–7 above.
