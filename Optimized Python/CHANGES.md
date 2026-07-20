# CHANGES — Optimized Python vs the certified port

Baseline = `C:\Projects\Mouse Arena\Python` (unchanged, source of truth).
This package is a copy with performance changes only. Numeric behavior on the
default paths is byte-identical to the baseline (except the opt-in `rfft`).

## Files added
- `mouse_arena/optconfig.py` — optimization switches (`OPT`) + `set_baseline()` /
  `set_optimized()`. Kept out of `config.Params` (fixture-locked).
- `tests/test_10_opt_equivalence.py` — proves every fast path == its baseline
  path (byte-identical) and `rfft` within tolerance. No fixtures required.
- `benchmarks/bench_deconv.py` — median-time benchmarks (baseline vs optimized).
- `OPTIMIZATION_REPORT.md`, `CHANGES.md`, `README_OPTIMIZED.md`.

## Files changed (logic)
- `mouse_arena/deconvolution.py`
  - E1: `design_lowpass_fir` memoized by `Fs` (`lru_cache`); byte-identical taps.
  - E3: new `deconvolve_eth_batch(ETH, kn, Fs)` — vectorized over a trial matrix,
    chunked by `OPT.batch_rows`; byte-identical to the per-row loop.
  - E5: `_fft_deconv` selects `complex` (default, exact) or `rfft` (opt-in).
- `mouse_arena/detection.py`
  - E2: `schmitt_trigger` gains an O(N) vectorized path (`_schmitt_trigger_vec`),
    byte-identical to the sequential loop; original kept as `_schmitt_trigger_loop`.

## Files changed (call sites → batched helper, byte-identical)
- `mouse_arena/figures/make_fig1.py` (Panel E loop)
- `mouse_arena/figures/make_fig2.py`
- `mouse_arena/figures/make_fig3.py`
- `mouse_arena/figures/make_fig4.py` (per-frequency subset)
- `mouse_arena/figures/make_fig5.py`
- `mouse_arena/optimize.py` (kernel-outer / batched-trial restructure)

## Unchanged
Everything else, including `config.py` (and thus fixture `00_params`), the loader,
kernels, tracking, dataio, stage1 s1a–s1d, make_fig6–8 numeric cores, and the
whole `harness/`. The FFT length `N`, FIR taps, filtfilt padlen, findpeaks order,
and KS formula (hazard catalog H1–H11) are untouched.

## Reverting
`from mouse_arena import optconfig; optconfig.set_baseline()` restores the
original code paths (byte-identical output) at runtime — no edits needed.
