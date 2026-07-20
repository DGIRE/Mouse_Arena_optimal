# Python Architecture — Mouse Arena

## Package layout
```
Python/
  mouse_arena/                # the shipped package
    config.py                 # constants (ma_paths) + Params dataclass
    io_labview.py             # read_labview_dat
    kernels.py                # doe_kernel
    deconvolution.py          # design_lowpass_fir, deconvolve_eth, convolve_pid
    detection.py              # schmitt_trigger, find_contacts, matlab_kstest2_p
    tracking.py               # lowpass_jitter, clean_track, compute_speed, normalize_dxdx
    lighting.py               # classify_lighting, lighting_for_trial, filter_lighting
    metadata.py               # parse_trial_meta, extract_pulse_metrics, ma_first
    optimize.py               # optimize_kernel
    tracking_dmd.py           # track_body_head_dmd (skeleton)
    dataio.py                 # load_mat (v7.3), load_data_mat_struct
    stage1/  s1a..s1e.py      # import → pulses/frequency/spatial/calcium/DATA_MAT
    figures/ make_fig1..8.py  # numeric panel computation (+ optional matplotlib)
    pipeline.py               # RUN_ALL equivalent
  harness/                    # differential test engine (NOT shipped logic)
    fixtures.py  compare.py
  tests/                      # pytest: one module per fixture stage
  config/lighting_sessions.csv
  translation_inventory.md  HAZARD_CATALOG.md  python_architecture.md
  requirements.txt  README.md  VALIDATION_REPORT.md (generated)
```

## Conventions (locked by the pilot)
- **Arrays**: NumPy float64. Vectors returned as column `(N,1)` where the MATLAB
  fixture is `[N x 1]`; the harness squeezes for value comparison but asserts element
  count + orientation first. Coordinate arrays are `[N x 2]` (coords in columns).
- **I/O vs compute separation**: numeric functions take arrays + params and return
  arrays (pure, testable); file loading lives in `dataio`/`stage1`; plotting is optional
  and isolated at the end of each `make_fig*` (guarded by a `plot=False` default) so the
  numeric core is validated headless.
- **Params**: `config.get_params()` returns a `Params` dataclass; figures/stages accept
  an optional `params` argument (defaults to `PARAMS`).
- **Determinism**: no RNG except the Fig8 random control, which takes an explicit
  `seed`/`rng` (default seed 0) and is documented as statistical, not exact.
- **No MATLAB at runtime**: `.mat` I/O via h5py/mat73 only.

## Tolerance policy (per output type; set before comparison, never loosened)
| Output type | Rule (from manifest) |
|---|---|
| constants, integer/bool masks, IDs, indices | exact equality |
| doe_kernel | rtol 1e-10, atol 1e-12 |
| loader channels | exact (bytes in → arrays out) |
| deconvolution traces + eth_filt | rtol 1e-4, atol 1e-6 (+ intermediate checked) |
| butter/filtfilt tracks | rtol 1e-6, atol 1e-6 |
| DATA_MAT copy / sensor-char arrays | rtol 1e-9, atol 1e-9 |
| KS statistic + p | 1e-6 (via H9 exact formula) |
| Fig8 random control | statistics only (not exact) |
| trajectories / speed / ethanol | error metrics + correlation |

## Acceptance gates (per component)
1. **Specified** — I/O, shapes, hazards documented; ≥1 fixture identified.
2. **Numerically equivalent** — all expected outputs (incl. key intermediates) pass the
   harness within documented tolerance, certified by the Validator (not the Translator).
3. **Integrated** — quality-reviewed; downstream fixtures still pass end-to-end.

## Orchestrator rules (never violated)
Translator ≠ Validator (always distinct invocations). No translating before spec, no
integrating before independent validation, no silent tolerance increases, no editing
fixtures to force a pass, no large refactors during equivalence testing.
