"""Optimization-equivalence tests (Optimized Python package).

These guard the performance work: each optimization's default (fast) path must
be byte-identical to the original (baseline) path — the whole point of the
`optconfig` switches (blueprint gate 4 + R7). The one numeric option, the rfft
FFT backend, is checked to stay inside the deconvolution's documented tolerance.

Runs with NO fixtures required (self-contained synthetic + fixture-shaped data),
so it validates in any environment.
"""
import numpy as np
import pytest

from mouse_arena import optconfig, deconvolution as dc, kernels
from mouse_arena.detection import _schmitt_trigger_loop, _schmitt_trigger_vec, schmitt_trigger
from mouse_arena.optimize import optimize_kernel


@pytest.fixture(autouse=True)
def _reset_opt():
    optconfig.set_optimized()
    yield
    optconfig.set_optimized()


def _eth(n=6000, seed=0):
    rs = np.random.RandomState(seed)
    base = np.abs(rs.randn(n).cumsum() * 0.01) + 0.2
    return base


def test_fir_cache_byte_identical():
    optconfig.set_optimized()
    a = dc.design_lowpass_fir(500.0)
    optconfig.set_baseline()
    b = dc.design_lowpass_fir(500.0)
    assert a.shape == b.shape
    assert np.array_equal(a, b)          # bit-identical taps, cached or not


def test_schmitt_vectorized_equals_loop():
    rs = np.random.RandomState(1)
    for _ in range(100):
        n = rs.randint(1, 2000)
        x = rs.randn(n).cumsum() * 0.02 + 0.3
        hi = rs.uniform(0.1, 0.6)
        assert np.array_equal(
            _schmitt_trigger_vec(x, hi, hi - 0.02),
            _schmitt_trigger_loop(x, hi, hi - 0.02),
        )
    # edge cases
    for x in (np.array([]), np.array([0.4]), np.full(8, 0.3),
              np.array([0.5, 0.5, 0.29, 0.31, 0.1])):
        assert np.array_equal(
            _schmitt_trigger_vec(x, 0.3, 0.28),
            _schmitt_trigger_loop(x, 0.3, 0.28),
        )
    # public entry honors the switch and matches the loop by default
    x = _eth(4000)
    optconfig.set_optimized(); yopt = schmitt_trigger(x, 0.3)
    optconfig.set_baseline();  ybase = schmitt_trigger(x, 0.3)
    assert np.array_equal(yopt, ybase)


def test_batched_deconv_equals_per_row_loop():
    eth = _eth(5000)
    Fs = 500.0
    kn = kernels.doe_kernel(0.02, 2.0, eth.size, Fs).ravel()
    M = np.vstack([eth + 0.03 * i + 0.001 * i * np.cos(np.arange(eth.size)) for i in range(11)])

    optconfig.set_baseline()
    loopD = np.array([dc.deconvolve_eth(M[i], kn, Fs)[0].ravel() for i in range(M.shape[0])])
    loopN = np.array([dc.deconvolve_eth(M[i], kn, Fs)[1].ravel() for i in range(M.shape[0])])

    optconfig.set_optimized()
    for br in (1, 3, 11, 64):             # result is invariant to chunk size
        optconfig.OPT.batch_rows = br
        bD, bN = dc.deconvolve_eth_batch(M, kn, Fs)
        assert np.max(np.abs(bD - loopD)) == 0.0
        assert np.max(np.abs(bN - loopN)) == 0.0


def test_optimize_kernel_batched_equals_original():
    eth = _eth(4000)
    M = np.vstack([eth + 0.02 * i for i in range(5)])
    pid = np.abs(M) + 1.0
    tr, td = [0.01, 0.02], [1.0, 2.0]

    # original triple-loop reference (baseline path)
    optconfig.set_baseline()
    nT, N = M.shape
    Rref = np.zeros((nT, len(tr) * len(td)))
    for it in range(nT):
        ci = -1
        for a in tr:
            for b in td:
                ci += 1
                kn = kernels.doe_kernel(a, b, N, 500.0)
                d, _ = dc.deconvolve_eth(M[it], kn, 500.0)
                d = d.ravel(); ad = np.abs(d)
                dn = (d - ad.min()) / (ad.max() - ad.min())
                pn = pid[it]; pn = (pn - pn.min()) / (pn.max() - pn.min())
                seg = slice(499, d.size - 500)
                Rref[it, ci] = np.sqrt(np.mean((dn[seg] - pn[seg]) ** 2))

    optconfig.set_optimized()
    Ropt, _, _ = optimize_kernel(M, pid, tr, td, 500.0)
    assert np.max(np.abs(Ropt - Rref)) == 0.0


def test_rfft_backend_within_tolerance():
    eth = _eth(6000)
    Fs = 500.0
    kn = kernels.doe_kernel(0.02, 2.0, eth.size, Fs).ravel()
    optconfig.OPT.fft_backend = "complex"
    d0, n0 = dc.deconvolve_eth(eth, kn, Fs)
    optconfig.OPT.fft_backend = "rfft"
    d1, n1 = dc.deconvolve_eth(eth, kn, Fs)
    # deconvolution tolerance is 1e-4; rfft stays far inside it
    assert np.max(np.abs(d1 - d0)) < 1e-6
    assert np.max(np.abs(n1 - n0)) < 1e-6
