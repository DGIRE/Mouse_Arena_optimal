---
name: run-analysis
description: Write and run a data-analysis job end-to-end, safely and frugally. Use when the user asks to analyze data, compute statistics/models, or produce result objects. Enforces the venv interpreter, skeleton-then-scale, static checks, slice-first, and checkpointing.
---

# run-analysis — analysis code → saved results

1. **Confirm interpreter.** Use `"$AR_PY"` for every run. If unconfirmed, resolve
   with `/setup-venv` first.
2. **Plan in a few lines**: inputs, outputs, 2–4 real steps. No over-planning.
3. **Skeleton**: one `.py` file with `main()`, a fixed seed, and an assert-based
   self-check before heavy compute. Delegate to the `data-analyst` agent for
   nontrivial work; run independent analyses as **parallel** `Task` calls.
4. **Static-check**: `"$AR_PY" -m compileall <file>`; fast `pytest` on a small
   fixture. Fix before scaling.
5. **Slice first**: run on a subset, sanity-check ranges/shapes, then run full.
6. **Checkpoint**: write results to `results/…` (`.npz`/`.parquet`/`.json`);
   skip stages whose fresh output exists; log long output to a file.
7. **Verify**: hand the code to `code-verifier` (parallel is fine) — static
   checks, tests, and one independent re-derivation of a headline number.
8. Report: files changed, result locations, exact reproduce command, caveats.

Never `pip install` mid-run, never write to raw-data/kernel folders, never fall
back to a bare `python`.
