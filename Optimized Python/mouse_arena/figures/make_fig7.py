"""make_fig7 — port of Stage2_Figures/make_Fig7_example_trials.m.

FIGURE 7: two example freely-behaving IR trials. For each trial:
  - tracking + background from the per-trial .mat (cr_body/cr_head/fr_ts_body/meanImage)
  - ethanol sensor from the .avi.dat, deconvolved with the behaviour kernel
  - trajectory / speed / deconvolved-ethanol over a paper-defined time window
  - plume-contact samples via a Schmitt trigger on the rescaled raw sensor.

Faithful translation of the paper's per-trial plotter (ExampleTrajectories
logFile.m). Numeric core is compute(); plot() mirrors the MATLAB figure.

Reference: Tariq et al. (2020), Fig. 7.
"""
from __future__ import annotations
import numpy as np

from mouse_arena import config
from mouse_arena.dataio import load_mat
from mouse_arena.io_labview import read_labview_dat
from mouse_arena.kernels import doe_kernel
from mouse_arena.deconvolution import deconvolve_eth
from mouse_arena.tracking import lowpass_jitter, compute_speed
from mouse_arena.detection import schmitt_trigger


def _rescale(x):
    """MATLAB rescale(x) -> (x - min) / (max - min), mapping to [0, 1]."""
    x = np.asarray(x, dtype=np.float64).ravel()
    lo = x.min()
    hi = x.max()
    return (x - lo) / (hi - lo)


def _orient_coords(a):
    """MATLAB: cb = double(cr_body); if size(cb,1)==2 && size(cb,2)~=2; cb=cb.'; end."""
    a = np.asarray(a, dtype=np.float64)
    if a.shape[0] == 2 and a.shape[1] != 2:
        a = a.T
    return a


def compute(mat_path, dat_path, tmin, tmax, th, src, FR_cam=90, params=None):
    """Compute the numeric contents of one Fig. 7 example-trial panel set.

    Follows make_Fig7_example_trials.m exactly.

    Returns a dict with the panel arrays (traj_x/traj_y/speed/ethdec_window/
    ethresc/hit/contact_xy/contact_color/btw/t0/Fs/meanImage) plus 'full', the
    pre-window full traces {body, head, bt, ethdec_full, eth_raw}.
    """
    if params is None:
        params = config.PARAMS
    K = params.kernel_behavior

    # --- tracking + background ---
    T = load_mat(mat_path)
    cb = _orient_coords(T["cr_body"])
    ch = _orient_coords(T["cr_head"])
    body = lowpass_jitter(cb)                       # [N x 2] pixel coords
    head = lowpass_jitter(ch)

    bt = np.asarray(T["fr_ts_body"], dtype=np.float64).ravel() / float(FR_cam)
    t0 = float(bt.min())                            # shared trial-start clock
    bt = bt - t0                                    # body time relative to start

    mi = np.asarray(T["meanImage"], dtype=np.float64)
    if mi.shape[0] > mi.shape[1]:                   # orient: arena wider than tall
        mi = mi.T

    # --- ethanol sensor from the .avi.dat ---
    S = read_labview_dat(dat_path, params.chan_beh, params)
    eth = np.asarray(S["ETH"], dtype=np.float64).ravel()
    Fs = float(S["Fs"])
    ts = np.asarray(S["time"], dtype=np.float64).ravel() / 1000.0 - t0

    kn = doe_kernel(K["tau_rise"], K["tau_decay"], eth.size, Fs)
    ethdec, _ = deconvolve_eth(eth, kn, Fs)         # upward-oriented deconvolution
    ethdec = ethdec.ravel()

    # --- window (paper values) ---
    bw = (bt >= tmin) & (bt <= tmax)
    x = body[bw, 0]
    y = body[bw, 1]
    btw = bt[bw]
    spd = compute_speed(body)[bw]

    # ethanol on the body-time base, within the window
    # MATLAB interp1(...,'linear',0): linear interp, 0 outside [min(ts),max(ts)].
    ethraw_bt = np.interp(btw, ts, eth, left=0.0, right=0.0)
    ethdec_bt = np.interp(btw, ts, ethdec, left=0.0, right=0.0)
    ethresc = _rescale(ethraw_bt)                   # [0,1] as in logFile.m
    hit = schmitt_trigger(ethresc, th, th - 0.02)   # plume-contact samples

    contact_xy = np.column_stack([x[hit], y[hit]])
    contact_color = ethresc[hit]

    return {
        "traj_x": x.reshape(-1, 1),
        "traj_y": y.reshape(-1, 1),
        "speed": spd.reshape(-1, 1),
        "ethdec_window": ethdec_bt.reshape(-1, 1),
        "ethresc": ethresc.reshape(-1, 1),
        "hit": hit,
        "contact_xy": contact_xy,
        "contact_color": contact_color.reshape(-1, 1),
        "btw": btw.reshape(-1, 1),
        "t0": t0,
        "Fs": Fs,
        "meanImage": mi,
        "src": np.asarray(src, dtype=np.float64).ravel(),
        "full": {
            "body": body,
            "head": head,
            "bt": bt.reshape(-1, 1),
            "ethdec_full": ethdec.reshape(-1, 1),
            "eth_raw": eth.reshape(-1, 1),
        },
    }


def plot(res, name="", loc="", th=None, ax=None):
    """Render the Fig. 7 panels for one trial (mirrors the MATLAB figure).

    Optional; the numeric compute() output is what is tested. Uses the Agg
    backend so it runs headless.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.asarray(res["traj_x"]).ravel()
    y = np.asarray(res["traj_y"]).ravel()
    btw = np.asarray(res["btw"]).ravel()
    spd = np.asarray(res["speed"]).ravel()
    ethdec_bt = np.asarray(res["ethdec_window"]).ravel()
    ethresc = np.asarray(res["ethresc"]).ravel()
    hit = np.asarray(res["hit"]).astype(bool)
    mi = np.asarray(res["meanImage"])
    src = np.asarray(res["src"]).ravel()

    fig = plt.figure(figsize=(8, 9), facecolor="w")
    fig.suptitle(f"Fig7 {name} ({loc}, infrared)")

    ax1 = fig.add_subplot(4, 1, (1, 2))
    bg = (mi - mi.min()) / (mi.max() - mi.min() + np.finfo(float).eps)
    ax1.imshow(np.dstack([bg, bg, bg]))
    ax1.plot(x, y, "k-", lw=2)
    if np.any(hit):
        nC = 64
        ethmap = np.column_stack([
            np.linspace(0, 0.85, nC), np.zeros(nC), np.linspace(0.85, 0, nC)])
        cmap = matplotlib.colors.ListedColormap(ethmap)
        sctr = ax1.scatter(x[hit], y[hit], s=45, c=ethresc[hit],
                           cmap=cmap, edgecolors="none")
        fig.colorbar(sctr, ax=ax1, label="ethanol (norm.)")
    ax1.plot(src[0], src[1], "ro", lw=3, ms=11, fillstyle="none")
    ax1.plot(x[0], y[0], "g+", lw=2, ms=10)
    ax1.set_xticks([])
    ax1.set_yticks([])
    ax1.set_title(f"{name} ({loc}, infrared): trajectory (red = source, dots = contact)")

    ax2 = fig.add_subplot(4, 1, 3)
    ax2.plot(btw, spd, "k-", lw=1.5)
    ax2.set_ylabel("Speed")
    ax2.set_xticks([])

    ax3 = fig.add_subplot(4, 1, 4)
    ax3.plot(btw, ethdec_bt, "b-", lw=1.5)
    ax3.set_ylabel("ETH\ndeconv")
    ax3.set_xlabel("Time (s)")
    return fig
