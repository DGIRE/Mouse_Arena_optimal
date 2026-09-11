# LESSONS — Trajectory analysis

Fed forward to the next run. Builds on `Plume locations/learning/LESSONS.md`
(standing rules 1–7), which still apply. New standing rules 8–11 below.

## Standing rules (new this project)

8. **Exposure/path-length confound for event COUNTS.** Any raw count that accrues
   along a path (encounters, threshold crossings, samples) scales with path length /
   duration. Correlating such a count with another path-length-scaling quantity
   (tortuosity here scales with path length at ρ=+0.925) manufactures a spurious
   association. Observed: ρ(n_encounters, tortuosity)=+0.612 collapsed to
   ρ(encounter_rate, tortuosity)=+0.077 (CI spans 0, p=0.44) once normalized by path
   length. **Always report an exposure-normalized rate and/or a path-fraction measure
   alongside any raw count, and lead the interpretation with the normalized one.**
9. **A low quiet-baseline FPR does NOT make detections meaningful — check absolute
   amplitude.** Calibrating a detector to quiet-baseline FPR ≤ 0.05/s (rule 3) can
   still place the threshold at the NOISE FLOOR when the quiet baseline is near-silent
   (tiny MAD). Here threshold = k·MAD = 7.2e-4 sat at the deconvolved noise floor
   (per-trial median ethdeconv ≈4.3e-4); real odor reaches 0.14, yet **0% of detected
   onsets exceeded 0.01**, and an amplitude threshold of 0.01 collapsed counts to a
   median of 0/trial. **Pair the FPR calibration with an absolute-amplitude sanity
   check** (detected-event amplitude vs the real signal range) and report a
   secondary amplitude-threshold count. Refines rule 3.
10. **"Smallest k with FPR ≤ target" returns the MOST permissive threshold** when all
    candidate k pass on a degenerate quiet baseline. Harmless for a null result, but
    it maximizes sensitivity to noise — do not let it underpin a positive claim
    without the amplitude check (rule 9).
11. **Verify the angle/vector convention with a physical spot-check before trusting
    orientation results.** θ from u=unit(head−body), s=unit(source−body) gave a small
    θ (≈23°) when the animal was near/facing the port on a real trial — the required
    sanity check (§10.8). A systematically large near-source θ would mean a flipped
    convention (head−body vs body−head, or x/y order).

## What worked (reuse)

- **Reusing the validated `plume_common` library** (clean_track advancing-reference
  de-jump, group_of, align_signal, mad) inside a thin `traj_common.py` kept cleaning
  /alignment identical to the Plume run and let the fixed de-jump propagate for free.
  De-jump removed 0.41% (body) / 1.01% (head) — the smell test passed on the first try.
- **Probing every asserted fact before planning** (114 trials; Loc1–6=105; clocks;
  ranges) confirmed the request's premises so the plan used ground truth.
- **Proactively adding the exposure-normalized confound metric before Gate 1** turned
  a would-be Gate-2 blocker into a clean, pre-empted honest result.

## 2026-08-07 — Trajectory structure & odor-guided orientation (H1/H2/H3)

**Outcome:** Completed; PASSED Gate 1 (code) and Gate 2 (science, after 1 scoped
documentation revision). **All three hypotheses are NULL / not supported** — reported
honestly:
- **H1** (encounters → straighter): NOT supported. Raw ρ(n_encounters, tortuosity)
  =+0.612 is *opposite* the prediction and is a **path-length exposure artifact**
  (rule 8); exposure-normalized ρ=+0.077 (n.s.). Secondary frac-above vs tortuosity
  ρ=−0.419 reproduced the prior −0.532.
- **H2** (alignment improves near source): direction positive (median per-trial
  slope +0.020 deg/px) but **non-significant** (Wilcoxon p=0.119); F3 curve
  non-monotonic. Not supported at α=0.05.
- **H3** (peri-contact reorientation): **null** (paired Wilcoxon post<pre p=0.998;
  median pre 70.0° ≈ post 69.7°; 64/105 trials post>pre).

**What failed + root cause**
- *Encounter counts at the noise floor* (root cause: k·MAD calibration on a
  near-silent quiet baseline) — Gate 2 caught it; Gate 1's exact numeric
  re-derivation could not, because the code was correct — it's a *science*
  interpretability issue → rules 9–10. **Verifier/auditor division of labour
  confirmed:** code-correctness (Gate 1) and scientific-meaning (Gate 2) are distinct
  gates; a passing Gate 1 does not imply meaningful measurements.
- *H3 direction label* mismatched the trial-pair majority (cosmetic) — fixed.

**New standing rules added:** 8–11 above.
