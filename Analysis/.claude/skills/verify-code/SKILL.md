---
name: verify-code
description: Independently review and test analysis code to catch bugs fast and cheaply. Use in parallel with or right after writing analysis code, and before building the report. Static checks, tests, sanity checks, and one independent re-derivation.
---

# verify-code — skeptical second pass

1. Delegate to the `code-verifier` agent (it reads fresh; runs read + Bash only).
   Running it as a parallel `Task` while other work proceeds is encouraged.
2. It restates what the code ACTUALLY computes vs. the goal and flags: off-by-one,
   wrong axis/reduction, unit/scale errors, label leakage, silent NaN handling,
   seed gaps, shape mismatches.
3. It runs `"$AR_PY" -m compileall` and `"$AR_PY" -m pytest -q`, executes the job
   on a small slice, and checks outputs are sane (ranges/shapes, not all-NaN).
4. It re-derives ONE headline number a different way and checks agreement to
   tolerance.
5. Output: PASS, or a ranked defect list (file:line, failure, minimal fix) handed
   back to the analyst. Treat an unresolved plausible correctness issue as a
   blocker — fix before proceeding to figures/report.
