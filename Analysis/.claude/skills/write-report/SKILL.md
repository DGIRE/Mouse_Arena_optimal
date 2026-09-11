---
name: write-report
description: Assemble a scientific report (DOCX by default, optional PDF) from saved result objects and figures. Use once results and figures exist. Injects every number from result files, embeds figures, and fails on leftover placeholders.
---

# write-report — results + figures → DOCX (optional PDF)

1. Build with python-docx via `"$AR_PY" build_report.py` (python-docx is in the
   venv). Default output `.docx`.
2. **Inject every statistic** (N, means, effect sizes, p-values, CIs, table
   cells) from saved result objects — never hand-typed. Resolve derived
   aggregates to literals.
3. Structure: Title; Methods (data source, interpreter/venv, seed, key params);
   Results (embed `figures/*.png` with captions); Discussion/Caveats;
   reproducibility footer (exact command + result-file names).
4. **No-placeholder gate**: after rendering, scan the document text; if any `{{`
   remains, FIX and re-render — do not report done.
5. PDF only if requested and a converter (or matplotlib `PdfPages`) is available;
   otherwise deliver the DOCX and say PDF was not produced.
6. For a multi-document report set, delegate to the `report-writer` agent.
