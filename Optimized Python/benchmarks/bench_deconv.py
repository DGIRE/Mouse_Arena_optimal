"""Benchmarks for the Mouse Arena optimizations (medians, not best runs).

Compares each optimization's baseline path against its optimized path using the
`optconfig` switches, on fixture-shaped synthetic data (no fixtures required).

    python -m benchmarks.bench_deconv        # from the package root

Reports median wall time over N repeats. Numbers vary with CPU/BLAS threads;
the RATIOS are the portable result.
"""
import time, statistics
import numpy as np

from mouse_arena import optconfig, deconvolution as dc, kernels
from mouse_arena.detection import _schmitt_trigger_loop, _schmitt_trigger_vec


def _med(fn, r=7):
    ts = []
    for _ in range(r):
        t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    return statistics.median(ts)


def main():
    Fs = 500.0
    N = 35679                                   # a real per-trial trace length
    rs = np.random.RandomState(0)
    eth = np.abs(rs.randn(N).cumsum() * 0.01) + 0.2
    kn = kernels.doe_kernel(0.02, 2.0, N, Fs).ravel()

    print("== B1: Kaiser FIR design per deconvolve_eth call ==")
    optconfig.set_baseline(); tb = _med(lambda: dc.design_lowpass_fir(500.0))
    optconfig.set_optimized(); dc.design_lowpass_fir(500.0)
    to = _med(lambda: dc.design_lowpass_fir(500.0))
    print(f"   uncached {tb*1e3:.2f} ms -> cached {to*1e6:.1f} us  ({tb/to:.0f}x)")

    print("== B2: schmitt_trigger on a full trace ==")
    x = np.abs(rs.randn(N))
    tl = _med(lambda: _schmitt_trigger_loop(x, 0.3, 0.28))
    tv = _med(lambda: _schmitt_trigger_vec(x, 0.3, 0.28))
    print(f"   loop {tl*1e3:.2f} ms -> vec {tv*1e3:.3f} ms  ({tl/tv:.0f}x)")

    print("== B3: figure deconvolution loop (nT trials) ==")
    for nT in (24, 60, 114):
        M = np.vstack([eth + 0.03 * i for i in range(nT)])
        optconfig.set_baseline()
        tb = _med(lambda: np.array([dc.deconvolve_eth(M[i], kn, Fs)[0].ravel()
                                    for i in range(nT)]), 3)
        optconfig.set_optimized()
        to = _med(lambda: dc.deconvolve_eth_batch(M, kn, Fs)[0], 3)
        print(f"   nT={nT:3d}: per-row loop {tb*1e3:6.0f} ms -> batched {to*1e3:6.0f} ms  ({tb/to:.2f}x)")

    print("== B5: rfft backend (opt-in, Level-2) on a long recording ==")
    long = np.tile(eth, 10); kn2 = kernels.doe_kernel(0.02, 2.0, long.size, Fs).ravel()
    optconfig.OPT.fft_backend = "complex"; tc = _med(lambda: dc.deconvolve_eth(long, kn2, Fs), 3)
    optconfig.OPT.fft_backend = "rfft";    tr = _med(lambda: dc.deconvolve_eth(long, kn2, Fs), 3)
    optconfig.OPT.fft_backend = "complex"
    print(f"   N={long.size}: complex {tc*1e3:.0f} ms -> rfft {tr*1e3:.0f} ms  ({tc/tr:.2f}x)")


if __name__ == "__main__":
    main()
