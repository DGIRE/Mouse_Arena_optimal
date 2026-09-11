---
name: make-figures
description: Render publication-quality figures (PNG + PDF) from saved result objects. Use after results are computed and you need plots. Headless matplotlib; both raster and vector outputs; provenance sidecars.
---

# make-figures — results → PNG + PDF

1. Run figure code with `"$AR_PY"`; matplotlib is headless (`MPLBACKEND=Agg`).
2. **Read saved result objects** and plot them — never recompute science in plot
   code. If a value is missing, ask the analyst to add it to the results.
3. Save EACH figure as BOTH `figures/<name>.png` (dpi=200,
   `bbox_inches="tight"`) and `figures/<name>.pdf` (vector). Write a `.txt`
   sidecar naming the source result file.
4. Label every axis with units; add a legend where needed; state N and any
   exclusions; use a colorblind-safe palette; keep panels visually consistent.
5. Confirm each file exists and is non-empty before reporting done.
6. For many independent figures, delegate to the `figure-builder` agent and/or
   run them as parallel `Task` calls.
