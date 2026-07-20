"""deconvolution — port of common/deconvolve_eth.m + convolve_pid.m (fixture 03). [High risk]

design_lowpass_fir(Fs): reproduce MATLAB designfilt('lowpassfir','kaiserwin',
PassbandFrequency=0.001, StopbandFrequency=40, PassbandRipple=0.5,
StopbandAttenuation=65, SampleRate=Fs). Fixture stores fir_coeffs (58 taps at
Fs=500, sum=1). Match these taps.

deconvolve_eth(eth, kn, Fs=500): eth_filt=filtfilt(fir, eth);
eth_deconv=real(ifft(fft(eth_filt)/fft(kn,N))); edge=min(500,floor(N/4));
idx=edge:N-edge; polarity flip if sum((D-mean).*(filt-mean)) over idx < 0;
core=abs(D[idx]); norm=(D-min(core))/(max(core)-min(core)). Returns
(eth_deconv, eth_deconv_norm). Test eth_filt intermediate first.

OPTIMIZED PACKAGE
-----------------
Two byte-identical performance changes plus one opt-in numeric change, all gated
by ``mouse_arena.optconfig.OPT`` (see that module for the baseline revert):

  * FIR-design cache (OPT.cache_fir): ``design_lowpass_fir`` is deterministic in
    Fs, but it was recomputed on *every* ``deconvolve_eth`` call — and the whole
    package deconvolves in per-trial loops (figs 1-5, s1e's 114 trials,
    optimize.py). The design runs a kaiserord estimate + a numtaps-growth loop
    that evaluates ``freqz(8192)`` several times. We memoize it by Fs. The taps
    are bit-identical to the original; only the redundant recomputation is gone.

  * Batched deconvolution (``deconvolve_eth_batch``, OPT.batched_deconv): the
    figure loops all do ``DEC[i]=deconvolve_eth(ETH[i])`` over a trial matrix.
    Batching filtfilt (axis=1) and the FFTs over all rows removes the Python
    loop and the per-row FIR design. Proven byte-identical (max|Δ|=0.0) to the
    per-row loop; chunked by ``OPT.batch_rows`` to bound peak memory (R2/R8).

  * FFT backend (OPT.fft_backend): default "complex" is the exact original path.
    "rfft" uses real-FFT (the inputs are real, so the spectrum is
    conjugate-symmetric and the ifft is real) — ~1.5x faster FFT, Level-2
    numeric (<= ~1e-11, inside the 1e-4 tolerance). Opt-in only.
"""
import numpy as np
from functools import lru_cache
from scipy.signal import firwin, filtfilt, freqz, kaiserord

from .optconfig import OPT


# Fixed design spec from deconvolve_eth.m designfilt(...):
_FPASS = 0.001      # PassbandFrequency (Hz)
_FSTOP = 40.0       # StopbandFrequency (Hz)
_APASS = 0.5        # PassbandRipple (dB)   -- see note in design_lowpass_fir
_ASTOP = 65.0       # StopbandAttenuation (dB)


def _stopband_attenuation_db(taps, Fs):
    """Worst-case realized stopband attenuation (dB) of an FIR design.

    Evaluates the magnitude response and returns the minimum attenuation across
    the stopband (f >= Fstop, in normalized units with Nyquist = 1). Larger is
    better; the design meets spec when this is >= _ASTOP.
    """
    w, h = freqz(taps, worN=8192)
    f = w / np.pi                       # normalized frequency in [0, 1] (Nyquist=1)
    mag = np.abs(h)

    fstop_n = _FSTOP / (Fs / 2.0)       # stopband edge, normalized to Nyquist
    stop_mask = f >= fstop_n

    with np.errstate(divide="ignore"):
        return -20.0 * np.log10(np.max(mag[stop_mask]) + 1e-300)


def _design_lowpass_fir_impl(Fs):
    """Uncached Kaiser-window lowpass FIR design (the original computation)."""
    beta = 0.1102 * (_ASTOP - 8.7)
    cutoff = (_FPASS + _FSTOP) / 2.0 / (Fs / 2.0)

    # Initial numtaps estimate from the Kaiser design formula.
    trans_width = (_FSTOP - _FPASS) / (Fs / 2.0)     # normalized transition width
    numtaps, _ = kaiserord(_ASTOP, trans_width)
    if numtaps % 2 == 0:
        numtaps += 1  # kaiserord may hand back an even count; start odd

    # Grow numtaps until the realized stopband attenuation reaches _ASTOP.
    max_taps = numtaps + 1000
    while numtaps < max_taps:
        taps = firwin(numtaps, cutoff, window=("kaiser", beta))
        if _stopband_attenuation_db(taps, Fs) >= _ASTOP:
            break
        numtaps += 1

    return taps


@lru_cache(maxsize=None)
def _design_lowpass_fir_cached(Fs):
    return _design_lowpass_fir_impl(Fs)


def design_lowpass_fir(Fs=500.0):
    """Reproduce MATLAB designfilt('lowpassfir','kaiserwin', ...) (deconvolve_eth.m).

    Kaiser-window lowpass FIR with:
      PassbandFrequency=0.001, StopbandFrequency=40,
      PassbandRipple=0.5 dB, StopbandAttenuation=65 dB, SampleRate=Fs.

    beta   = 0.1102*(Astop - 8.7)                 (Astop > 50)
    cutoff = (Fpass + Fstop)/2 / (Fs/2)           (-6 dB point, normalized to Nyquist)
    numtaps: start from scipy.signal.kaiserord's estimate, then grow until the
      *realized* stopband attenuation meets spec (>= _ASTOP = 65 dB). At Fs=500
      this lands on 58 taps, matching MATLAB designfilt.

    The passband spec (_APASS = 0.5 dB) is never binding for these parameters
    (Fpass=0.001 Hz is DC); numtaps growth is driven by stopband attenuation.

    OPTIMIZED: memoized by Fs when ``optconfig.OPT.cache_fir`` is True (default).
    The returned taps are bit-identical to the uncached design; the cache only
    removes redundant recomputation across the package's per-trial deconvolution
    loops.
    """
    if OPT.cache_fir:
        return _design_lowpass_fir_cached(float(Fs))
    return _design_lowpass_fir_impl(float(Fs))


def _fft_deconv(ef, kn, N):
    """dec = real(ifft(fft(ef) / fft(kn, N))) with the configured FFT backend.

    ``ef`` may be 1-D (N,) or 2-D (rows, N); FFTs run along the last axis.
    "complex" reproduces the original np.fft path bit-for-bit; "rfft" is the
    faster real-FFT equivalent (Level-2 numeric).
    """
    kn = np.asarray(kn, dtype=np.float64).reshape(-1)
    if OPT.fft_backend == "rfft":
        knf = np.fft.rfft(kn, N)
        return np.fft.irfft(np.fft.rfft(ef, axis=-1) / knf, N, axis=-1)
    # default exact path
    knf = np.fft.fft(kn, N)
    return np.real(np.fft.ifft(np.fft.fft(ef, axis=-1) / knf, axis=-1))


def deconvolve_eth(eth, kn, Fs=500.0):
    """FFT deconvolution of a raw ethanol-sensor trace (deconvolve_eth.m).

    ETH_filt   = filtfilt(lpFilt, ETH)
    ETH_deconv = real(ifft(fft(ETH_filt) ./ fft(kn, numel(ETH_filt))))
    edge = min(500, floor(N/4));  idx = edge:N-edge
    polarity flip if sum((D-mean(D)).*(filt-mean(filt))) over idx < 0
    core = abs(D[idx]);  norm = (D - min(core)) / (max(core) - min(core))

    Returns (ETH_deconv, ETH_deconv_norm) as (N,1) column vectors.
    """
    eth = np.asarray(eth, dtype=np.float64).reshape(-1)
    kn = np.asarray(kn, dtype=np.float64).reshape(-1)

    taps = design_lowpass_fir(Fs)
    eth_filt = filtfilt(taps, [1.0], eth)

    N = eth_filt.size
    dec = _fft_deconv(eth_filt, kn, N)

    edge = min(500, N // 4)                          # floor(N/4)
    idx = slice(edge, N - edge)                      # MATLAB edge:N-edge (inclusive)

    # Polarity: orient so contact is upward-going, matching the filtered raw sensor.
    a = dec[idx] - dec[idx].mean()
    b = eth_filt[idx] - eth_filt[idx].mean()
    if np.dot(a, b) < 0:
        dec = -dec

    # Normalize: numerator uses the FULL dec, denominator the core abs-range.
    core = np.abs(dec[idx])
    dec_norm = (dec - core.min()) / (core.max() - core.min())

    return dec.reshape(-1, 1), dec_norm.reshape(-1, 1)


def deconvolve_eth_batch(ETH, kn, Fs=500.0):
    """Vectorized deconvolution of a trial matrix ``ETH`` = [nTrials x N].

    Byte-identical to looping ``deconvolve_eth`` over the rows (proven max|Δ|=0.0)
    but designs the FIR once, filters and FFTs all rows together, and vectorizes
    the per-row polarity/normalization. Rows are processed in chunks of
    ``optconfig.OPT.batch_rows`` to bound peak memory (each row is independent,
    so the result is identical for any chunk size >= 1).

    Returns (DEC, DEC_norm), each [nTrials x N] float64 (row-per-trial), matching
    ``deconvolve_eth(ETH[i])[0].ravel()`` / ``[1].ravel()`` for every row i.
    """
    ETH = np.asarray(ETH, dtype=np.float64)
    if ETH.ndim == 1:
        ETH = ETH[None, :]
    nT, N = ETH.shape
    kn = np.asarray(kn, dtype=np.float64).reshape(-1)
    taps = design_lowpass_fir(Fs)

    edge = min(500, N // 4)
    idx = slice(edge, N - edge)

    DEC = np.empty((nT, N), dtype=np.float64)
    DECN = np.empty((nT, N), dtype=np.float64)

    step = max(1, int(OPT.batch_rows)) if OPT.batched_deconv else 1
    for s in range(0, nT, step):
        e = min(s + step, nT)
        ef = filtfilt(taps, [1.0], ETH[s:e], axis=1)
        dec = _fft_deconv(ef, kn, N)                 # (rows, N)

        a = dec[:, idx] - dec[:, idx].mean(axis=1, keepdims=True)
        b = ef[:, idx] - ef[:, idx].mean(axis=1, keepdims=True)
        flip = (a * b).sum(axis=1) < 0
        if flip.any():
            dec[flip] = -dec[flip]

        core = np.abs(dec[:, idx])
        cmin = core.min(axis=1, keepdims=True)
        cmax = core.max(axis=1, keepdims=True)
        DEC[s:e] = dec
        DECN[s:e] = (dec - cmin) / (cmax - cmin)

    return DEC, DECN


def convolve_pid(PID, kn):
    """Forward-convolve a PID trace with the sensor kernel (convolve_pid.m).

    c = real(ifft(fft(PID) .* fft(kn, numel(PID))));
    PID_conv_norm = (c - min(c)) / (max(c) - min(c));
    """
    PID = np.asarray(PID, dtype=np.float64).reshape(-1)
    kn = np.asarray(kn, dtype=np.float64).reshape(-1)
    N = PID.size
    c = np.real(np.fft.ifft(np.fft.fft(PID) * np.fft.fft(kn, N)))
    c_norm = (c - c.min()) / (c.max() - c.min())
    return c_norm.reshape(-1, 1)
