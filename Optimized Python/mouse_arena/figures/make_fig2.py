"""make_fig2 — port of Stage2_Figures/make_Fig2_peak_times.m. [Low risk, plotting]

FIGURE 2 -- Peak times of deconvolved ethanol coincide with PID peak times.
  A: PID / deconv-ETH heatmaps (rows=trials, aligned to valve) + overlay diff.
  B: linear relation of PID vs deconv-ETH peak times (per trial).

INPUT: the s1a "pulses" dict (ETH_all_sorted, PID_all_sorted,
durations_sorted, t, Fs).

The MATLAB source prefers paper-precomputed peak times (AUCs.mat:
tPeak_PID/tPeak_ETHdeconv) when present; no such fixture ships with this
batch, so `compute()` always derives peak times directly (the MATLAB "else"
branch): argmax of each trial's PID/deconvolved-ETH trace.
"""
import numpy as np

from ..config import PARAMS
from ..deconvolution import deconvolve_eth, deconvolve_eth_batch
from ..kernels import doe_kernel


def _scalar(x):
    return float(np.asarray(x).reshape(-1)[0])


def _safe_polyfit(x, y, deg=1):
    """np.polyfit, but degrade to NaN coefficients instead of raising on a
    degenerate (e.g. zero-variance / rank-deficient) fit -- see make_fig1."""
    try:
        return np.polyfit(x, y, deg)
    except Exception:
        return np.full(deg + 1, np.nan)


def _rescale(x):
    """MATLAB `rescale(A)` (no InputMin/Max): global min/max over the whole array."""
    x = np.asarray(x, dtype=np.float64)
    return (x - x.min()) / (x.max() - x.min())


def compute(data, params=None):
    """Numeric core behind Fig2's two panels.

    Returns {'DEC': deconvolved ETH (nTrials x N), 'overlay': rescale(DEC) -
    rescale(PID) (global min/max), 'PID': raw PID (nTrials x N), 't': time
    vector, 'B': {'xp': PID peak times, 'yp': ETH-deconv peak times,
    'polyfit': [slope, intercept], 'slope': float}}.
    """
    params = dict(params or {})
    ETH = np.asarray(data["ETH_all_sorted"], dtype=np.float64)
    PID = np.asarray(data["PID_all_sorted"], dtype=np.float64)
    t = np.asarray(data["t"], dtype=np.float64).reshape(-1)
    Fs = _scalar(data["Fs"])

    K = params.get("kernel_sensorChar", PARAMS.kernel_sensorChar)
    nT, N = ETH.shape
    kn = doe_kernel(K["tau_rise"], K["tau_decay"], N, Fs)

    # OPTIMIZED: batch the per-trial deconvolution (byte-identical to the loop).
    DEC, _ = deconvolve_eth_batch(ETH, kn, Fs)

    overlay = _rescale(DEC) - _rescale(PID)

    # ---- Panel B: peak times -------------------------------------------
    xp = t[np.argmax(PID, axis=1)]
    yp = t[np.argmax(DEC, axis=1)]
    g = ~np.isnan(xp) & ~np.isnan(yp)
    p = _safe_polyfit(xp[g], yp[g], 1) if g.sum() >= 2 else np.array([np.nan, np.nan])
    panelB = {"xp": xp, "yp": yp, "polyfit": p, "slope": float(p[0])}

    return {"t": t, "PID": PID, "DEC": DEC, "overlay": overlay, "B": panelB}


def plot(data, params=None):
    """Optional matplotlib reproduction of Fig2's panels (Agg backend)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(data, dict) and {"DEC", "overlay", "B"}.issubset(data.keys()):
        res = data
    else:
        res = compute(data, params)

    figs = {}

    figA, axes = plt.subplots(1, 3, figsize=(12, 4))
    nT = res["PID"].shape[0]
    extent = [res["t"][0], res["t"][-1], 1, nT]
    axes[0].imshow(res["PID"], aspect="auto", extent=extent, origin="lower")
    axes[0].set_title("PID")
    axes[0].set_xlabel("s")
    axes[0].set_ylabel("trial")
    axes[1].imshow(res["DEC"], aspect="auto", extent=extent, origin="lower")
    axes[1].set_title("ETH deconv")
    axes[1].set_xlabel("s")
    axes[2].imshow(res["overlay"], aspect="auto", extent=extent, origin="lower")
    axes[2].set_title("overlay (diff)")
    axes[2].set_xlabel("s")
    figA.suptitle("Fig2A heatmaps")
    figs["A"] = figA

    B = res["B"]
    figB, axB = plt.subplots(figsize=(4, 4))
    axB.plot(B["xp"], B["yp"], "ko", markerfacecolor="k")
    xl = np.array(axB.get_xlim())
    p = B["polyfit"]
    if np.all(np.isfinite(p)):
        axB.plot(xl, np.polyval(p, xl), "r-")
    axB.set_xlabel("PID peak time (s)")
    axB.set_ylabel("ETH-deconv peak time (s)")
    axB.set_title(f"slope = {B['slope']:.2f}")
    figs["B"] = figB

    return figs
