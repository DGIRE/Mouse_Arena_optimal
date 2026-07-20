"""make_fig5 — port of Stage2_Figures/make_Fig5_spatial_corr.m. [Low risk, plotting]

FIGURE 5 -- Deconvolved ethanol correlates with PID in turbulent airflow,
across three arena locations (near port / middle / downwind).
  B: representative PID (red) vs deconv-ETH (blue) traces per location.
  C: cumulative distributions of PID-PID cross-trial corr (red) vs PID-ETH
     within-trial corr (blue), per location.
  D: mean +/- SD correlation bars per location, with individual-trial dots.

(Panel A is the overhead arena photo -- not numeric, skipped here.)

INPUT: the s1c "spatial" dict (ETH_all_sorted, PID_all_sorted,
locations_sorted, t, Fs).

Correlation window = ethanol-stimulation window (60-120 s), as in Fig5.m:
`w = round(60*Fs):round(120*Fs)` (1-based, inclusive, capped at N samples).
`corr(a,b)` (MATLAB) is a plain Pearson correlation coefficient, reproduced
here with `np.corrcoef`. `std` uses MATLAB's default ddof=1 (sample std).
"""
import numpy as np

from ..config import PARAMS
from ..deconvolution import deconvolve_eth, deconvolve_eth_batch
from ..kernels import doe_kernel


def _scalar(x):
    return float(np.asarray(x).reshape(-1)[0])


def _matlab_round(x):
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def _pearson(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def _cdf(x):
    """`cdfplot_local`: sort(x) vs (1:n)/n (a stairs-style empirical CDF)."""
    x = np.sort(np.asarray(x, dtype=np.float64).reshape(-1))
    n = x.size
    y = np.arange(1, n + 1) / n if n else np.array([])
    return x, y


def _window_idx(Fs, N):
    """MATLAB `w = round(60*Fs):round(120*Fs); w = w(w<=size(DEC,2));` as 0-based idx."""
    start_1based = int(_matlab_round(60.0 * Fs))
    end_1based = min(int(_matlab_round(120.0 * Fs)), N)
    return np.arange(start_1based - 1, end_1based)  # 0-based, inclusive of end


def compute(data, params=None):
    """Numeric core behind Fig5's panels.

    Deconvolves every trial, then computes within-trial (PID vs ETH-deconv)
    and across-trial (PID vs PID) correlations inside the ethanol
    stimulation window, per arena location.

    Returns {'locs': sorted unique locations, 't': (N,), 'DEC': (nTrials,N),
      'PID': (nTrials,N), 'window_idx': 0-based sample indices of the
      60-120s window, 'mu': mean within-corr per location, 'sd': std
      (ddof=1) within-corr per location,
      'B': {loc: {'trial_idx', 'ETH_deconv', 'PID'}} representative traces,
      'per_location': {loc: {'trial_idx', 'within', 'across',
                              'cdf_within': (x,y), 'cdf_across': (x,y)}}}.
    """
    params = dict(params or {})
    ETH = np.asarray(data["ETH_all_sorted"], dtype=np.float64)
    PID = np.asarray(data["PID_all_sorted"], dtype=np.float64)
    locations = np.asarray(data["locations_sorted"], dtype=np.float64).reshape(-1)
    t = np.asarray(data["t"], dtype=np.float64).reshape(-1)
    Fs = _scalar(data["Fs"])

    K = params.get("kernel_sensorChar", PARAMS.kernel_sensorChar)
    nT, N = ETH.shape
    kn = doe_kernel(K["tau_rise"], K["tau_decay"], N, Fs)

    # OPTIMIZED: batch the per-trial deconvolution (byte-identical to the loop).
    DEC, _ = deconvolve_eth_batch(ETH, kn, Fs)

    w = _window_idx(Fs, N)
    locs = np.unique(locations)

    panelB = {}
    for loc in locs:
        idx = np.flatnonzero(locations == loc)
        if idx.size == 0:
            continue
        tr = int(idx[0])
        panelB[loc] = {"trial_idx": tr, "ETH_deconv": DEC[tr, :], "PID": PID[tr, :]}

    mu = np.zeros(locs.size)
    sd = np.zeros(locs.size)
    per_location = {}
    for li, loc in enumerate(locs):
        idx = np.flatnonzero(locations == loc)
        within = np.array([_pearson(PID[i, w], DEC[i, w]) for i in idx])
        mu[li] = within.mean() if within.size else np.nan
        sd[li] = within.std(ddof=1) if within.size > 1 else np.nan

        across = []
        for a_i in range(idx.size):
            for b_i in range(a_i + 1, idx.size):
                across.append(_pearson(PID[idx[a_i], w], PID[idx[b_i], w]))
        across = np.array(across)

        per_location[loc] = {
            "trial_idx": idx,
            "within": within,
            "across": across,
            "cdf_within": _cdf(within),
            "cdf_across": _cdf(across),
        }

    return {
        "locs": locs,
        "t": t,
        "DEC": DEC,
        "PID": PID,
        "window_idx": w,
        "mu": mu,
        "sd": sd,
        "B": panelB,
        "per_location": per_location,
    }


def plot(data, params=None):
    """Optional matplotlib reproduction of Fig5's panels B/C/D (Agg backend)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(data, dict) and "per_location" in data:
        res = data
    else:
        res = compute(data, params)

    locs = res["locs"]
    figs = {}

    figB, axesB = plt.subplots(len(locs), 1, figsize=(6, 3 * len(locs)), squeeze=False)
    for li, loc in enumerate(locs):
        ax = axesB[li, 0]
        ax2 = ax.twinx()
        panel = res["B"][loc]
        ax.plot(res["t"], panel["ETH_deconv"], "b")
        ax2.plot(res["t"], panel["PID"], "r")
        ax.set_title(f"Location {loc:g}")
        ax.set_xlim(45, 135)
        ax.set_ylabel("ETH deconv")
        ax2.set_ylabel("PID")
    axesB[-1, 0].set_xlabel("Time (s)")
    figB.suptitle("Fig5B representative traces")
    figs["B"] = figB

    figC, axesC = plt.subplots(1, len(locs), figsize=(4 * len(locs), 4), squeeze=False)
    axesC = axesC[0]
    for li, loc in enumerate(locs):
        ax = axesC[li]
        pl = res["per_location"][loc]
        xa, ya = pl["cdf_across"]
        xw, yw = pl["cdf_within"]
        ax.step(xa, ya, where="post", color="r", linewidth=2, label="PID-PID (across)")
        ax.step(xw, yw, where="post", color="b", linewidth=2, label="PID-ETH (within)")
        ax.set_title(f"Loc {loc:g}")
        ax.set_xlabel("correlation")
        ax.set_ylabel("CDF")
        ax.legend(loc="lower right")
    figC.suptitle("Fig5C CDFs")
    figs["C"] = figC

    figD, axD = plt.subplots(figsize=(2 + len(locs), 4))
    x = np.arange(1, len(locs) + 1)
    axD.bar(x, res["mu"], color=(.8, .8, .8))
    axD.errorbar(x, res["mu"], yerr=res["sd"], fmt="none", ecolor="k", linewidth=1.5)
    for li, loc in enumerate(locs):
        within = res["per_location"][loc]["within"]
        axD.plot(np.full_like(within, x[li]), within, "ko")
    axD.set_xticks(x)
    axD.set_xticklabels([f"Loc {loc:g}" for loc in locs])
    axD.set_ylabel("PID-ETH correlation")
    axD.set_title("mean +/- SD")
    figs["D"] = figD

    return figs
