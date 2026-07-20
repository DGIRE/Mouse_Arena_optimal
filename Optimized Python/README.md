# Mouse Arena — Python

Faithful Python port of the MATLAB Tariq et al. (2020) Mouse Arena reconstruction
(`C:\Projects\Mouse Arena\MATLAB`). Every numeric component is validated against
golden fixtures produced by one MATLAB run; see `VALIDATION_REPORT.md`.

## Layout
- `mouse_arena/` — the package: `config`, `io_labview`, `kernels`, `deconvolution`,
  `detection`, `tracking`, `lighting`, `metadata`, `optimize`, `tracking_dmd`, `dataio`,
  `stage1/` (s1a–s1e import), `figures/` (make_fig1–8), `pipeline` (RUN_ALL equivalent).
- `harness/` — the differential test engine (fixture loader + tolerance comparator).
- `tests/` — one pytest module per fixture stage (the equivalence contract).
- `translation_inventory.md`, `python_architecture.md`, `HAZARD_CATALOG.md` — design docs.
- `VALIDATION_REPORT.md` — machine-measured per-output errors.

## Quick start
```bash
pip install -r requirements.txt
MA_FIXTURES="/path/to/Gold Fixtures/fixtures" python -m pytest tests/ -q   # -> 17 passed, 1 skipped
python -m mouse_arena.pipeline                                              # run the pipeline
```

## Equivalence
The port matches the MATLAB to the documented per-output tolerance (constants/loader/masks
exact; deconvolution to ~5e-14; tracking to ~1e-11; KS p-values to 1e-15). Reproducing MATLAB
exactly required three non-obvious recipes — the kaiser FIR tap count, the `kstest2` Stephens
continuity correction, and the `filtfilt` pad length — all documented in `HAZARD_CATALOG.md`.
Translation and certification were done by separate agents (translator ≠ validator).
