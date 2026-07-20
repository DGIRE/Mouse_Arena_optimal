"""make_fig3 — port of Stage2_Figures/make_Fig3_frequency.m. [Low risk, plotting]

FIGURE 3 -- Frequency response: sensor resolves ethanol fluctuations to 15 Hz.
  A: single-trial PID (red) + raw ETH (blue) at 5/10/15 Hz.
  B: deconvolved ETH for the same (one representative trial per frequency).
  C: 1-s zoom (t0+60..t0+61 s) of rescaled PID vs rescaled deconv-ETH.

INPUT: the s1b "frequency" dict (ETH_all_sorted, PID_all_sorted, freqs, t,
Fs) -- MATLAB-oriented arrays (trials x samples). `freqs` must be aligned to
the *_sorted trial order (one label per row of ETH/PID_all_sorted).
"""
import numpy as np

from ..config import PARAMS
from ..deconvolution import deconvolve_eth, deconvolve_eth_batch
from ..kernels import doe_kernel


def _scalar(x):
    return float(np.asarray(x).reshape(-1)[0])


def _rescale(x):
    """MATLAB `rescale(A)` (no InputMin/Max): global min/max over the whole array."""
    x = np.asarray(x, dtype=np.float64)
    return (x - x.min()) / (x.max() - x.min())


def compute(data, params=None):
    """Numeric core behind Fig3's panels.

    Deconvolves *every* trial (the numeric core), then builds the
    MATLAB-faithful per-frequency panel selections (one representative trial
    per frequency in `want`, matching `find(freqs==want(c),1,'first')`).

    Returns:
      {'t': (N,), 'freqs': (nTrials,), 'DEC_all': (nTrials, N) deconvolved
       ETH for every trial, 'kernel': (N,) the doe_kernel used, 'want':
       list of requested frequencies,
       'panels': {freq: {'trial_idx', 'ETH_raw', 'PID_raw', 'ETH_deconv',
                          'zoom_mask', 'PID_zoom_rescaled',
                          'ETH_deconv_zoom_rescaled'}}}
    """
    params = dict(params or {})
    ETH = np.asarray(data["ETH_all_sorted"], dtype=np.float64)
    PID = np.asarray(data["PID_all_sorted"], dtype=np.float64)
    freqs = np.asarray(data["freqs"], dtype=np.float64).reshape(-1)
    t = np.asarray(data["t"], dtype=np.float64).reshape(-1)
    Fs = _scalar(data["Fs"])

    K = params.get("kernel_sensorChar", PARAMS.kernel_sensorChar)
    nT, N = ETH.shape
    kn = doe_kernel(K["tau_rise"], K["tau_decay"], N, Fs)

    # ---- numeric core: deconvolve every trial ------------------------------
    # OPTIMIZED: batch the per-trial deconvolution (byte-identical to the loop).
    DEC_all, _ = deconvolve_eth_batch(ETH, kn, Fs)

    want = params.get("want_freqs", [5, 10, 15])
    panels = {}
    for w in want:
        idx = np.flatnonzero(freqs == w)
        if idx.size == 0:
            continue
        tr = int(idx[0])
        dec = DEC_all[tr, :]
        zoom_mask = (t >= t[0] + 60) & (t <= t[0] + 61)
        pid_zoom = PID[tr, zoom_mask]
        dec_zoom = dec[zoom_mask]
        panels[w] = {
            "trial_idx": tr,
            "ETH_raw": ETH[tr, :],
            "PID_raw": PID[tr, :],
            "ETH_deconv": dec,
            "zoom_mask": zoom_mask,
            "PID_zoom_rescaled": _rescale(pid_zoom) if pid_zoom.size else pid_zoom,
            "ETH_deconv_zoom_rescaled": _rescale(dec_zoom) if dec_zoom.size else dec_zoom,
        }

    return {
        "t": t,
        "freqs": freqs,
        "DEC_all": DEC_all,
        "kernel": kn.reshape(-1),
        "want": list(want),
        "panels": panels,
    }


def plot(data, params=None):
    """Optional matplotlib reproduction of Fig3's 3xN panel grid (Agg backend)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(data, dict) and "panels" in data and "DEC_all" in data:
        res = data
    else:
        res = compute(data, params)

    want = res["want"]
    t = res["t"]
    n = len(want)
    fig, axes = plt.subplots(3, max(n, 1), figsize=(4 * max(n, 1), 9), squeeze=False)
    for c, w in enumerate(want):
        panel = res["panels"].get(w)
        if panel is None:
            continue
        ax = axes[0, c]
        ax2 = ax.twinx()
        ax.plot(t, panel["ETH_raw"], "b")
        ax2.plot(t, panel["PID_raw"], "r")
        ax.set_title(f"{w} Hz raw")

        axb = axes[1, c]
        axb.plot(t, panel["ETH_deconv"], "b")
        axb.set_title("deconv ETH")

        axc = axes[2, c]
        z = panel["zoom_mask"]
        axc.plot(t[z], panel["PID_zoom_rescaled"], "r", t[z], panel["ETH_deconv_zoom_rescaled"], "b")
        axc.set_title("1-s zoom")
        axc.set_xlabel("Time (s)")

    fig.suptitle("Fig3 frequency response")
    return fig
