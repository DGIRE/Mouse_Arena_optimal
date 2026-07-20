"""detection — port of common/schmitt_trigger.m + make_Fig8 contact detection (fixtures 04, 07). [High]

schmitt_trigger(x, hi, lo=None): two-threshold hysteresis -> boolean mask.
  y[i]=True once x>=hi, stays True until x<lo (lo defaults hi-0.02). Exact (H7).

ks_2samp_matlab(a, b): MATLAB kstest2 two-sample asymptotic p-value. D is the
  SciPy KS statistic; p uses the Stephens-corrected Kolmogorov series (H9).

find_contacts(...): make_Fig8 findpeaks contact detection (H8).
"""
import numpy as np
from scipy.stats import ks_2samp
from scipy.signal import find_peaks, peak_prominences

from .optconfig import OPT


def _schmitt_trigger_loop(x, hi, lo):
    """Original sequential hysteresis (baseline; H7 exact)."""
    y = np.zeros(x.size, dtype=bool)
    state = False
    for i in range(x.size):
        if (not state) and x[i] >= hi:
            state = True
        elif state and x[i] < lo:
            state = False
        y[i] = state
    return y


def _schmitt_trigger_vec(x, hi, lo):
    """Vectorized hysteresis, byte-identical to the sequential loop.

    Rising (``x>=hi``) and falling (``x<lo``) samples are mutually exclusive
    (hi>lo), and every other sample holds the current state. So label each
    sample +1 (rise) / -1 (fall) / 0 (hold), forward-fill the last non-zero
    label (initial state False), and the sign of that label is the state. O(N),
    no Python per-sample loop. Verified bit-identical on fuzz + edge cases.
    """
    ev = np.zeros(x.size, dtype=np.int8)
    ev[x >= hi] = 1
    ev[x < lo] = -1
    src = np.where(ev != 0, np.arange(x.size), -1)
    np.maximum.accumulate(src, out=src)              # index of last event, -1 before any
    y = np.zeros(x.size, dtype=bool)
    seen = src >= 0
    y[seen] = ev[src[seen]] > 0
    return y


def schmitt_trigger(x, hi, lo=None):
    """Two-threshold hysteresis detector (logical output).

    MATLAB common/schmitt_trigger.m: state starts False; rising edge when
    ``x[i] >= hi`` (while off), falling edge when ``x[i] < lo`` (while on).
    ``lo`` defaults to ``hi - 0.02``. Sequential — order matters (H7 exact).

    OPTIMIZED: uses an O(N) vectorized implementation when
    ``optconfig.OPT.vectorized_schmitt`` is True (default), proven byte-identical
    to the sequential loop. Set the flag False to force the original loop.
    """
    x = np.asarray(x, dtype=float).ravel()
    if lo is None:
        lo = hi - 0.02
    if OPT.vectorized_schmitt:
        return _schmitt_trigger_vec(x, hi, lo)
    return _schmitt_trigger_loop(x, hi, lo)


def ks_2samp_matlab(a, b):
    """Two-sample KS test matching MATLAB ``kstest2`` (asymptotic p-value).

    Returns ``(D, p)`` where D is ``scipy.stats.ks_2samp(a,b).statistic`` and p
    is the Stephens continuity-corrected Kolmogorov asymptotic tail probability
    (H9), which SciPy omits:

        ne  = n1*n2/(n1+n2)
        lam = max((sqrt(ne) + 0.12 + 0.11/sqrt(ne)) * D, 0)
        p   = 2 * sum_{j=1..inf} (-1)^(j-1) exp(-2 lam^2 j^2)   # clamped to [0,1]

    Verified to reproduce head_p=0.0126127339 and body_p=0.0643908757 (<1e-15).
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    D = ks_2samp(a, b).statistic

    n1 = a.size
    n2 = b.size
    ne = n1 * n2 / (n1 + n2)
    sne = np.sqrt(ne)
    lam = max((sne + 0.12 + 0.11 / sne) * D, 0.0)

    # 2 * sum_{j=1}^inf (-1)^(j-1) exp(-2 lam^2 j^2); ~100 terms is ample.
    j = np.arange(1, 101)
    terms = ((-1.0) ** (j - 1)) * np.exp(-2.0 * lam * lam * j * j)
    p = 2.0 * np.sum(terms)
    p = min(max(p, 0.0), 1.0)
    return D, p


def find_contacts(seg_rescaled, threshold, min_peak_distance, prominence_mult):
    """Plume-contact peak detection, faithfully replicating MATLAB ``findpeaks``.

    MATLAB (make_Fig8_plume_contacts.m):
        findpeaks(seg, 'MinPeakHeight', thr,
                  'MinPeakDistance', max(1,round(min_sep_s*Fs_b)),
                  'MinPeakProminence', thr*prominence_mult)
    on ``seg = rescale([0,1])`` of the RAW ethanol on the body-time base.

    Here ``seg_rescaled`` is that segment, ``threshold`` = thr,
    ``min_peak_distance`` = ``min_sep_s*Fs_b`` (rounded internally), and
    ``prominence_mult`` scales the prominence floor.

    H8: SciPy's single ``find_peaks`` call applies MinPeakDistance BEFORE
    MinPeakProminence, whereas MATLAB ``findpeaks`` applies the filters in a
    fixed order that differs — on closely-spaced or tied peaks this can select a
    different contact set. We therefore replicate MATLAB's exact order:

      1. Locate all local maxima (``find_peaks`` with no filters).
      2. Keep peaks with value >= MinPeakHeight (threshold).
      3. Compute prominence on the FULL signal (``peak_prominences``) and keep
         peaks with prominence STRICTLY GREATER THAN MinPeakProminence — BEFORE
         distance. MATLAB ``findpeaks`` rejects a peak whose prominence merely
         ties the floor (``prom == Pmin``); SciPy's ``>=`` would keep it. Using
         strict ``>`` reproduces the gold fixture exactly (fixture 07: the
         rescaled global-max peak in trial 110 has prom == Pmin == 1.0 and must
         be dropped -> 60 contacts, not 61). Verified: ``>`` gives 60, ``>=``
         gives 61.
      4. Enforce MinPeakDistance greedily: stable-sort survivors by DESCENDING
         peak height, walk the list, and drop any peak within D samples of an
         already-accepted (taller) peak.

    ``D`` uses round-half-away-from-zero (``floor(x + 0.5)``), not Python's
    banker's rounding, to match MATLAB ``round``, and is floored at 1.

    Returns 0-based sample indices (Python/SciPy convention), sorted ascending.
    Note: MATLAB ``findpeaks`` returns 1-based ``locs``; the caller (make_fig8)
    indexes accordingly. This keeps the module's 0-based convention consistent
    with ``schmitt_trigger``'s output.
    """
    seg = np.asarray(seg_rescaled, dtype=float).ravel()
    Pmin = threshold * prominence_mult
    D = int(np.floor(min_peak_distance + 0.5))  # round-half-away-from-zero
    D = max(1, D)

    # Step 1: all local maxima, no filtering.
    cand, _ = find_peaks(seg)
    if cand.size == 0:
        return cand

    # Step 2: MinPeakHeight.
    cand = cand[seg[cand] >= threshold]
    if cand.size == 0:
        return cand

    # Step 3: MinPeakProminence, computed on the full signal, before distance.
    # Strict '>' matches MATLAB findpeaks (a prom == Pmin tie is rejected); H8.
    prom = peak_prominences(seg, cand)[0]
    cand = cand[prom > Pmin]
    if cand.size == 0:
        return cand

    # Step 4: greedy MinPeakDistance on peaks sorted by descending height.
    # np.argsort is stable ('stable' kind) so equal heights keep index order;
    # we negate the height to sort descending while preserving that stability.
    order = cand[np.argsort(-seg[cand], kind='stable')]
    accepted = []
    for idx in order:
        if all(abs(idx - a) >= D for a in accepted):
            accepted.append(idx)
    return np.array(sorted(accepted), dtype=int)
