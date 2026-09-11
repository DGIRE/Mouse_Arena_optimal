---
name: audit-science
description: Independently audit the SCIENCE (methodology, statistics, confounds, claim support) against the pre-registered plan, after results/figures/report exist and verify-code has passed. Complements verify-code; does not rewrite the analysis.
---

# audit-science — independent scientific audit (Gate 2)

1. Delegate to the `scientific-auditor` agent (Opus; fresh context;
   Read/Bash/Grep/Glob).
2. It reads the plan, saved results, code, figures, report, and data provenance —
   NOT the analyst's/verifier's self-justifications. Re-derive/inspect; don't
   trust the narrative.
3. Checklist: plan conformance; statistical validity (right test, assumptions,
   multiple comparisons, N/power, effect sizes with uncertainty); confounds &
   leakage (train/test leakage, circular analysis, batch/session confounds,
   baseline/normalization, units/scale); null adequacy (headline beats the RIGHT,
   destructive-enough null); result-claim match (spot-check numbers vs saved
   result objects); reproducibility (seed, versions, exact command, numbers
   injected not typed).
4. Output `audit_report.md`: findings ranked BLOCKER/MAJOR/MINOR (location,
   concrete failure, evidence, fix) + verdict PASS / REVISE / FAIL. Default to
   REVISE/FAIL if a correctness concern is plausible and unresolved.
5. REVISE/FAIL → `/plan-analysis` (scoped re-plan) → re-analyze → re-audit. Cap
   **2 iterations**, then STOP with `SESSION_NOTES.md`. Never self-approve; never
   mark results human-approved.
