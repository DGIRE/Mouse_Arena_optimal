"""optconfig — optimization switches for the Mouse Arena package.

These flags gate the performance optimizations added in the "Optimized Python"
package. They are kept OUT of ``config.Params`` on purpose: ``Params`` is pinned
byte-for-byte by fixture ``00_params`` and must not grow new fields.

Every optimization defaults to its fast path, and every fast path is proven
byte-identical to the original per-trial implementation EXCEPT ``fft_backend``:

    Optimization              flag                     baseline (byte-identical) value
    ------------------------  -----------------------  --------------------------------
    Kaiser-FIR design cache   cache_fir                False  (recompute every call)
    Vectorized Schmitt        vectorized_schmitt       False  (sequential Python loop)
    Batched deconvolution     batched_deconv           False  (per-row Python loop)
    FFT backend               fft_backend = "complex"  "complex"  (exact original)

So ``set_baseline()`` reproduces the original package output bit-for-bit and is
the one-switch revert (blueprint R7). ``fft_backend="rfft"`` is the only flag
that changes numbers — a Level-2 numeric change (≤ ~1e-11, well inside the
deconvolution's 1e-4 tolerance); it is OFF by default and opt-in only.

Usage:
    from mouse_arena import optconfig
    optconfig.OPT.batched_deconv = False      # force a baseline path
    optconfig.set_baseline()                  # force ALL baseline paths
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class OptConfig:
    # --- byte-identical fast paths (default ON) ---
    cache_fir: bool = True            # memoize design_lowpass_fir by Fs
    vectorized_schmitt: bool = True   # O(N) numpy hysteresis (exact mask)
    batched_deconv: bool = True       # deconvolve a trial matrix in one call

    # --- memory bound for batched deconvolution (rows per FFT chunk) ---
    # Byte-identical for any value >= 1 (each trial is independent); smaller =
    # lower peak RAM. See the cost-vs-size note in OPTIMIZATION_REPORT.md (R8).
    batch_rows: int = 64

    # --- numeric option (default OFF, opt-in) ---
    # "complex" = exact original np.fft.fft/ifft path (byte-identical).
    # "rfft"    = real-FFT path, ~1.5x faster FFT, Level-2 numeric (≤~1e-11).
    fft_backend: str = "complex"


OPT = OptConfig()


def set_baseline():
    """Force every optimization to the original byte-identical code path."""
    OPT.cache_fir = False
    OPT.vectorized_schmitt = False
    OPT.batched_deconv = False
    OPT.fft_backend = "complex"


def set_optimized():
    """Restore the default optimized (byte-identical) fast paths."""
    OPT.cache_fir = True
    OPT.vectorized_schmitt = True
    OPT.batched_deconv = True
    OPT.fft_backend = "complex"
