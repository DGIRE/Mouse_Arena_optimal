# Translation Inventory & Dependency Graph — Mouse Arena (MATLAB → Python)

Source: `C:\Projects\Mouse Arena\MATLAB` · Target: `C:\Projects\Mouse Arena\Python`
Ground truth: Gold Fixtures (10 stages, all exported OK by David's MATLAB run).
Reference: Tariq et al. (2021), eNeuro 8(1) ENEURO.0285-20.2020.

Risk = likelihood of a MATLAB↔SciPy numerical divergence (drives model tier + audit depth).

## Leaves-first component map

| # | MATLAB source | Python module | Fixture | Risk | Determinism |
|---|---------------|---------------|---------|------|-------------|
| 00 | config/ma_paths.m | mouse_arena/config.py | 00_params | Low | exact |
| 01 | common/read_labview_dat.m | io_labview.py | 01_loader | **High** | exact (byte-in→array-out) |
| 02 | common/doe_kernel.m | kernels.py | 02_kernel (behavior/sensor_char/unit) | Med | machine-precision |
| 03 | common/deconvolve_eth.m, convolve_pid.m | deconvolution.py | 03_deconvolve | **High** | rtol 1e-4 (FFT+FIR) |
| 04 | common/schmitt_trigger.m | detection.py | 04_schmitt (unit/real) | High-but-exact | exact mask |
| 05 | common/lowpass_jitter.m, clean_track.m, compute_speed.m, normalize_dxdx.m | tracking.py | 05_tracking (fig7/fig8 paths) | High | rtol 1e-6 |
| — | common/classify_lighting.m, lighting_for_trial.m, filter_lighting.m | lighting.py | (via 06 field / logic) | Low | exact |
| — | common/parse_trial_meta.m, extract_pulse_metrics.m, ma_first.m | metadata.py | (logic) | Low | exact |
| — | common/optimize_kernel.m | optimize.py | (derived) | Med | rtol 1e-6 |
| — | common/track_body_head_dmd.m | tracking_dmd.py | (no video in archive) | n/a | skeleton parity |
| — | common/colored_line.m | (plotting; figures) | n/a | n/a | plot-only |
| 06 | Stage1_Import/s1a–s1e.m | stage1/s1*.py | 06_data_mat (s1e), 09 (s1a-c) | Med | rtol 1e-9 |
| 07 | Stage2_Figures/make_Fig8_plume_contacts.m | figures/make_fig8.py | 07_fig8 (population_ks, pilot) | **High** | contacts exact; KS 1e-6; random=statistical |
| 08 | Stage2_Figures/make_Fig7_example_trials.m | figures/make_fig7.py | 08_fig7 (2 trials) | Med | end-to-end rtol 1e-4 |
| 09 | Stage2_Figures/make_Fig1/2/3/4/5.m | figures/make_fig1..5.py | 09_sensor_char (fig1/3/5) | Low | copy rtol 1e-9 |
| — | Stage2_Figures/make_Fig6_calcium_OB.m | figures/make_fig6.py | (no calcium data) | n/a | scaffold/skip |
| — | RUN_ALL.m | mouse_arena/pipeline.py | (integration) | — | end-to-end |

## Dependency order (translate & lock in this order)
1. config (00) → io_labview (01) → kernels (02) → deconvolution (03) → detection.schmitt (04)   ← PILOT slice
2. tracking (05); lighting, metadata, optimize (leaf helpers)
3. dataio (DATA_MAT struct reader); stage1 s1a–s1e (06 + sensor-char inputs)
4. figures: make_fig7 (08, end-to-end) → make_fig8 (07) → make_fig1/2/3/4/5 (09) → make_fig6 (scaffold)
5. pipeline (RUN_ALL) integration

## Environment reality
Cloud VM has NO MATLAB; agents consume static fixtures only. The 242 MB DATA_MAT
did not transfer over the device bridge, so 06/07 **population** validation is done on
the frozen KS distributions + peri-contact matrices + pilot per-trial fixture, not by
re-running detection over all 114 trials in-cloud (that runs locally on David's machine).
