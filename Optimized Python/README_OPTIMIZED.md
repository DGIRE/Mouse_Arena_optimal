# Mouse Arena — Optimized Python

A performance-optimized copy of `../Python`. Same API, same numbers: every
default optimization is **byte-identical** to the original port (proven, not
asserted), plus one opt-in numeric FFT backend. See `OPTIMIZATION_REPORT.md` for
the full write-up and `CHANGES.md` for the file-by-file diff.

## Install & validate
```bash
pip install -r requirements.txt
MA_FIXTURES="<Gold Fixtures>/fixtures"  python -m pytest tests/ -q   # 22 passed, 1 skipped
python -m benchmarks.bench_deconv                                    # median speedups
```

## What changed (all switchable via `mouse_arena/optconfig.py`)
| Switch | Default | Effect |
|--------|---------|--------|
| `cache_fir` | True | Memoize the Kaiser FIR design by `Fs` (byte-identical). |
| `vectorized_schmitt` | True | O(N) hysteresis instead of a per-sample loop (byte-identical). |
| `batched_deconv` | True | Deconvolve a whole trial matrix at once (byte-identical). |
| `batch_rows` | 64 | Rows per FFT chunk — memory/throughput dial (result-invariant). |
| `fft_backend` | `"complex"` | `"rfft"` = faster real-FFT, Level-2 numeric (≤1e-11). Opt-in. |

```python
from mouse_arena import optconfig
optconfig.set_baseline()     # force ORIGINAL byte-identical paths (A/B or rollback)
optconfig.set_optimized()    # restore defaults
optconfig.OPT.fft_backend = "rfft"   # opt into the numeric FFT speedup
optconfig.OPT.batch_rows = 16        # smaller chunks for very long recordings
```

## New / batched API
`deconvolution.deconvolve_eth_batch(ETH, kn, Fs)` — deconvolve `ETH` = [nTrials×N]
in one call; returns `(DEC, DEC_norm)`, each [nTrials×N], row-for-row identical to
looping `deconvolve_eth` over the rows. The figure modules and `optimize_kernel`
now use it internally.

## Speedups (medians, this machine — ratios are the portable result)
- Kaiser FIR design per call: ~10 000× (eliminated redundant recompute).
- `schmitt_trigger`: ~9× on a full trace.
- Per-trial deconvolution figures / `optimize_kernel`: **~2.2–2.4× end-to-end**.

Nothing here changes scientific method. Rollback is one function call.
