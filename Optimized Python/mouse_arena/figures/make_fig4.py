"""make_fig4 — port of Stage2_Figures/make_Fig4_crosscorr.m. [Low risk, plotting]

FIGURE 4 -- Cross-correlation of deconvolved ethanol with PID at 5/10/15 Hz.
  For each frequency: cross-corr deconv-ETH x PID during stimulation (blue)
  vs baseline (gray), plus PID autocorrelation (red), for every trial at that
  frequency. Vertical dashed lines mark the period of each frequency.

INPUT: the s1b "frequency" dict (ETH_all_sorted, PID_all_sorted, freqs, t,
Fs).

Cross-correlation note: MATLAB's `xcorr(a, b, maxlag, 'coeff')` on two
same-length signals normalizes by sqrt(sum(a.^2) * sum(b.^2)) (their
zero-lag autocorrelations). Since `a`/`b` here are already z-scored with
MATLAB's *population* std (zscore default: ddof=0), sum(zscore(x).^2) == N
exactly, so the 'coeff' normalizer collapses to N (the segment length). We
therefore reproduce it as
`scipy.signal.correlate(zscore(a), zscore(b), mode='full') / N`, sliced to
the central `2*maxlag+1` lags around zero -- numerically identical to
MATLAB's xcorr(...,'coeff') for zscored inputs of equal length. The
single-argument autocorrelation form `xcorr(x, maxlag, 'coeff')` is just the
two-argument form with a=b=x (peaks at 1.0 at lag 0), so we reuse the same
helper.
"""
import numpy as np
from scipy.signal import correlate

from ..config import PARAMS
from ..deconvolution import deconvolve_eth, deconvolve_eth_batch
from ..kernels import doe_kernel


def _scalar(x):
    return float(np.asarray(x).reshape(-1)[0])


def _matlab_round(x):
    """MATLAB `round`: round-half-away-from-zero."""
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def _zscore_pop(x):
    """MATLAB `zscore` default: population std (ddof=0)."""
    x = np.asarray(x, dtype=np.float64)
    sd = x.std(ddof=0)
    if sd == 0:
        return np.zeros_like(x)
    return (x - x.mean()) / sd


def _xcorr_coeff(a, b, maxlag):
    """`xcorr(zscore(a), zscore(b), maxlag, 'coeff')` -- see module docstring."""
    a = _zscore_pop(a)
    b = _zscore_pop(b)
    n = a.size
    full = correlate(a, b, mode="full") / n
    center = n - 1
    return full[center - maxlag: center + maxlag + 1]


def compute(data, params=None):
    """Numeric core behind Fig4's cross-correlation panels.

    Returns {'lags': (2*maxlag+1,) in seconds, 'want': [5,10,15],
      'panels': {freq: {'trial_idx': array of trials at this freq,
                         'XC': (nTrialsAtFreq, nLags) stim-window deconvETH-x-PID,
                         'AC': (nTrialsAtFreq, nLags) stim-window PID autocorr,
                         'BL': (nTrialsAtFreq, nLags) baseline-window deconvETH-x-PID,
                         'mean_XC', 'mean_AC': mean over trials,
                         'period_s': 1/freq}}}.
    """
    params = dict(params or {})
    ETH = np.asarray(data["ETH_all_sorted"], dtype=np.float64)
    PID = np.asarray(data["PID_all_sorted"], dtype=np.float64)
    freqs = np.asarray(data["freqs"], dtype=np.float64).reshape(-1)
    Fs = _scalar(data["Fs"])

    K = params.get("kernel_sensorChar", PARAMS.kernel_sensorChar)
    nT, N = ETH.shape
    kn = doe_kernel(K["tau_rise"], K["tau_decay"], N, Fs)

    want = params.get("want_freqs", [5, 10, 15])
    maxlag = int(_matlab_round(Fs))  # +/- 1 s
    lags = np.arange(-maxlag, maxlag + 1) / Fs

    panels = {}
    for w in want:
        idx = np.flatnonzero(freqs == w)
        if idx.size == 0:
            continue
        XC, AC, BL = [], [], []
        # OPTIMIZED: batch this frequency's trials (byte-identical to the loop).
        DECsub, _ = deconvolve_eth_batch(ETH[idx, :], kn, Fs)
        for j, k in enumerate(idx):
            dec = DECsub[j]
            pid = PID[k, :]
            n = pid.size
            half = int(_matlab_round(n / 2.0))
            stim = slice(0, half)          # MATLAB 1:round(n/2)
            base = slice(half, n)          # MATLAB round(n/2)+1:n

            XC.append(_xcorr_coeff(dec[stim], pid[stim], maxlag))
            AC.append(_xcorr_coeff(pid[stim], pid[stim], maxlag))
            BL.append(_xcorr_coeff(dec[base], pid[base], maxlag))

        XC = np.array(XC)
        AC = np.array(AC)
        BL = np.array(BL)
        panels[w] = {
            "trial_idx": idx,
            "XC": XC,
            "AC": AC,
            "BL": BL,
            "mean_XC": XC.mean(axis=0),
            "mean_AC": AC.mean(axis=0),
            "period_s": 1.0 / w,
        }

    return {"lags": lags, "want": list(want), "panels": panels}


def plot(data, params=None):
    """Optional matplotlib reproduction of Fig4's cross-correlation panels (Agg)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(data, dict) and "panels" in data and "lags" in data:
        res = data
    else:
        res = compute(data, params)

    want = res["want"]
    lags = res["lags"]
    n = max(len(want), 1)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4), squeeze=False)
    axes = axes[0]
    for c, w in enumerate(want):
        panel = res["panels"].get(w)
        ax = axes[c]
        if panel is None:
            continue
        ax.plot(lags, panel["BL"].T, color=(.7, .7, .7))
        ax.plot(lags, panel["mean_XC"], "b", linewidth=2)
        ax.plot(lags, panel["mean_AC"], "r", linewidth=1)
        ax.axvline(panel["period_s"], color="k", linestyle="--")
        ax.axvline(-panel["period_s"], color="k", linestyle="--")
        ax.set_title(f"{w} Hz")
        ax.set_xlabel("Lag (s)")
        ax.set_ylabel("corr")

    fig.suptitle("Fig4 cross-correlation")
    return fig
