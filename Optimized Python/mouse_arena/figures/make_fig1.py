"""make_fig1 — port of Stage2_Figures/make_Fig1_deconv_kernel.m. [Low risk, plotting]

FIGURE 1 -- Ethanol-sensor response deconvolved with a difference-of-two-
exponentials kernel.
  A: representative raw ETH/PID traces spanning pulse durations.
  B: mean ETH response + illustrative tau fit (tau_rise=60ms, tau_decay=3.5s).
  C: kernel-optimization heatmap (mean deconv-vs-PID RMSE over a
     tau_rise x tau_decay grid).
  D: deconvolved ETH vs PID for one representative trial (+ normalized inset).
  E: threshold-time (5% of max) linear relation, PID vs ETH-deconv.

INPUT: the s1a "pulses" dict (ETH_all_sorted, PID_all_sorted,
durations_sorted, t, Fs) -- MATLAB-oriented arrays (trials x samples).

The MATLAB source prefers paper-precomputed results (KernelOptimization.mat /
AUCs.mat / <dur>s.mat, located via `ma_first`) when present, and otherwise
computes everything from `pulses.mat`. No such paper-precomputed fixtures
ship with this batch, so `compute()` always takes the MATLAB "else" branch
(full computation from the raw sorted traces). Panel C's grid search
(default: 10 tau_rise x 25 tau_decay values, every trial) is the expensive
step -- O(nTrials * nGrid) FFT deconvolutions; pass smaller
`taus_rise`/`taus_decay` via `params` to speed up ad-hoc exploration.
"""
import numpy as np

from ..config import PARAMS
from ..deconvolution import deconvolve_eth, deconvolve_eth_batch
from ..kernels import doe_kernel
from ..optimize import optimize_kernel


def _scalar(x):
    return float(np.asarray(x).reshape(-1)[0])


def _colon(start, step, stop):
    """Reproduce MATLAB's `start:step:stop` colon operator (inclusive, float-safe)."""
    n = int(np.floor((stop - start) / step + 1e-9)) + 1
    n = max(n, 0)
    return start + step * np.arange(n)


def _matlab_round(x):
    """MATLAB `round`: round-half-away-from-zero (vs numpy's round-half-to-even)."""
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def _rescale_rows(X):
    """rescale(X,'InputMin',min(X,[],2),'InputMax',max(X,[],2)): per-row [0,1]."""
    X = np.asarray(X, dtype=np.float64)
    row_min = X.min(axis=1)
    row_max = X.max(axis=1)
    return (X - row_min[:, None]) / (row_max - row_min)[:, None]


def _safe_polyfit(x, y, deg=1):
    """np.polyfit, but degrade to NaN coefficients instead of raising on a
    degenerate (e.g. zero-variance / rank-deficient) fit. MATLAB's `polyfit`
    warns ("badly conditioned") on such inputs but never raises; this keeps
    that same non-fatal behavior."""
    try:
        return np.polyfit(x, y, deg)
    except Exception:
        return np.full(deg + 1, np.nan)


def _tt05(x, t):
    """Local `tt05` helper: time to 5% of (baseline-subtracted) max, else NaN."""
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    x = x - x.min()
    thr = 0.05 * x.max()
    idx = np.flatnonzero(x >= thr)
    if idx.size == 0:
        return float("nan")
    return float(t[idx[0]])


def compute(data, params=None):
    """Numeric core behind Fig1's five panels.

    Returns {'A':..., 'B':..., 'C':..., 'D':..., 'E':...}; see module
    docstring for panel semantics. All panels are computed from `data`
    (mirrors the MATLAB "no paper file found" fallback branches).
    """
    params = dict(params or {})
    ETH = np.asarray(data["ETH_all_sorted"], dtype=np.float64)
    PID = np.asarray(data["PID_all_sorted"], dtype=np.float64)
    durations = np.asarray(data["durations_sorted"], dtype=np.float64).reshape(-1)
    t = np.asarray(data["t"], dtype=np.float64).reshape(-1)
    Fs = _scalar(data["Fs"])

    nT, N = ETH.shape
    K = params.get("kernel_sensorChar", PARAMS.kernel_sensorChar)

    # ---- Panel A: representative raw traces spanning pulse durations ------
    ud, pick_first = np.unique(durations, return_index=True)  # first idx per unique duration
    m = min(3, pick_first.size)
    lin_1based = np.linspace(1, pick_first.size, m) if pick_first.size else np.array([])
    sel0 = (_matlab_round(lin_1based) - 1).astype(int)
    pick = pick_first[sel0]
    panelA = {
        "pick_idx": pick,
        "picked_durations": durations[pick],
        "t": t,
        "ETH": ETH[pick, :],
        "PID": PID[pick, :],
    }

    # ---- Panel B: mean ETH response + illustrative tau fit -----------------
    mE = ETH.mean(axis=0)
    kfit = doe_kernel(0.060, 3.5, N, Fs).reshape(-1) * mE.max()
    panelB = {"t": t, "mean_ETH": mE, "kernel_fit": kfit}

    # ---- Panel C: kernel-optimization heatmap ------------------------------
    taus_rise = np.asarray(params.get("taus_rise", _colon(0.001, 0.005, 0.05)), dtype=np.float64)
    taus_decay = np.asarray(params.get("taus_decay", _colon(0.1, 0.2, 5.0)), dtype=np.float64)
    eth_rescaled = _rescale_rows(ETH)
    RMSE, tr_out, td_out = optimize_kernel(eth_rescaled, PID, taus_rise, taus_decay, Fs)
    # RMSE columns are ordered rise-major/decay-minor (see optimize_kernel.m loop
    # order), so a plain C-order reshape recovers the (n_rise, n_decay) grid.
    mean_RMSE = RMSE.mean(axis=0).reshape(taus_rise.size, taus_decay.size)
    panelC = {"taus_rise": tr_out, "taus_decay": td_out, "mean_RMSE": mean_RMSE}

    # ---- Panel D: deconvolved ETH vs PID, one representative trial --------
    kn = doe_kernel(K["tau_rise"], K["tau_decay"], N, Fs)
    dev, dev_norm = deconvolve_eth(ETH[pick[0], :], kn, Fs)
    panelD = {
        "t": t,
        "trial_idx": int(pick[0]),
        "ETH_deconv": dev.reshape(-1),
        "PID": PID[pick[0], :],
        "ETH_deconv_norm": dev_norm.reshape(-1),
    }

    # ---- Panel E: threshold-time (5% of max) linear relation --------------
    # OPTIMIZED: batch the per-trial deconvolution (byte-identical to the loop).
    DEC_E, _ = deconvolve_eth_batch(ETH, kn, Fs)
    y = np.empty(nT)
    x = np.empty(nT)
    for i in range(nT):
        y[i] = _tt05(DEC_E[i], t)
        x[i] = _tt05(PID[i, :], t)
    g = ~np.isnan(x) & ~np.isnan(y)
    p = _safe_polyfit(x[g], y[g], 1) if g.sum() >= 2 else np.array([np.nan, np.nan])
    panelE = {"x_PID_t05": x, "y_ETHdeconv_t05": y, "polyfit": p, "slope": float(p[0])}

    return {"A": panelA, "B": panelB, "C": panelC, "D": panelD, "E": panelE}


def plot(data, params=None):
    """Optional matplotlib reproduction of Fig1's panels (Agg backend).

    `data` may be the raw s1a dict (compute() is run internally) or an
    already-computed dict from `compute()` (detected via the 'A'..'E' keys).
    Returns {'A': fig, 'B': fig, 'C': fig, 'D': fig, 'E': fig}.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(data, dict) and set("ABCDE").issubset(data.keys()):
        res = data
    else:
        res = compute(data, params)

    figs = {}

    # Panel A
    A = res["A"]
    figA, axes = plt.subplots(1, len(A["pick_idx"]), figsize=(4 * len(A["pick_idx"]), 3))
    axes = np.atleast_1d(axes)
    for j, ax in enumerate(axes):
        ax2 = ax.twinx()
        ax.plot(A["t"], A["ETH"][j, :], "b")
        ax2.plot(A["t"], A["PID"][j, :], "r")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("ETH")
        ax2.set_ylabel("PID")
        ax.set_title(f"{A['picked_durations'][j]:.2f} s pulse")
    figA.suptitle("Fig1A raw PID vs ETH")
    figs["A"] = figA

    # Panel B
    B = res["B"]
    figB, axB = plt.subplots(figsize=(5, 3))
    axB.plot(B["t"], B["mean_ETH"], color=(.6, .6, .6), label="mean ETH")
    axB.plot(B["t"], B["kernel_fit"], "m", linewidth=1.5,
             label=r"$\tau_{rise}$=60ms,$\tau_{decay}$=3.5s")
    axB.set_xlabel("Time (s)")
    axB.set_ylabel("ETH (a.u.)")
    axB.legend()
    figB.suptitle("Fig1B mean ETH response")
    figs["B"] = figB

    # Panel C
    C = res["C"]
    figC, axC = plt.subplots(figsize=(5, 4))
    pc = axC.pcolormesh(C["taus_decay"], C["taus_rise"], C["mean_RMSE"], shading="gouraud")
    axC.set_xlabel(r"$\tau_{Decay}$ (s)")
    axC.set_ylabel(r"$\tau_{Rise}$ (s)")
    axC.set_title("mean deconv-vs-PID RMSE")
    figC.colorbar(pc, ax=axC)
    figs["C"] = figC

    # Panel D
    D = res["D"]
    figD, axD = plt.subplots(figsize=(5, 3))
    axD2 = axD.twinx()
    axD.plot(D["t"], D["ETH_deconv"], "b")
    axD2.plot(D["t"], D["PID"], "r")
    axD.set_xlabel("Time (s)")
    axD.set_ylabel("ETH deconv")
    axD2.set_ylabel("PID")
    figD.suptitle("Fig1D deconvolved ETH vs PID")
    figs["D"] = figD

    # Panel E
    E = res["E"]
    figE, axE = plt.subplots(figsize=(4, 4))
    axE.plot(E["x_PID_t05"], E["y_ETHdeconv_t05"], "ko", markerfacecolor="k")
    xl = np.array(axE.get_xlim())
    p = E["polyfit"]
    if np.all(np.isfinite(p)):
        axE.plot(xl, np.polyval(p, xl), "r-")
    axE.set_xlabel("PID threshold time (s)")
    axE.set_ylabel("ETH-deconv threshold time (s)")
    axE.set_title(f"slope={E['slope']:.2f}")
    figs["E"] = figE

    return figs
