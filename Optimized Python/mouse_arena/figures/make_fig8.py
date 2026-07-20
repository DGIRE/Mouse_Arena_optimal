"""make_fig8 — port of Stage2_Figures/make_Fig8_plume_contacts.m.

FIGURE 8: plume contacts are intermittent and on average correlate with a
reduction in body speed. Population analysis over all DATA_MAT trials:
  - per trial: clean_track + lowpass_jitter + compute_speed
  - remap head speed and interpolate the ethanol signals onto the body-time base
  - detect plume contacts via findpeaks on rescale([0,1]) of the RAW sensor,
    restricted entry -> first reward, kept if > min_dist_px from the source
  - stack peri-contact windows (interpolated onto a common Nw-point grid),
    sorted by distance -> Emat (log deconv ETH) / Hmat / Bmat
  - 1-s pre/post means -> KS tests (MATLAB kstest2 asymptotic p, via H9).

A single seeded RNG drives the random no-contact control; that control is
statistical (its exact p-value is not reproducible against MATLAB's randi, only
its distribution/verdict — documented, see H9).

Reference: Tariq et al. (2020), Fig. 8. Source: logFile.m, logFile_means.m.
"""
from __future__ import annotations
import numpy as np

from mouse_arena import config
from mouse_arena.dataio import load_data_mat_struct
from mouse_arena.tracking import lowpass_jitter, clean_track, compute_speed
from mouse_arena.detection import find_contacts, ks_2samp_matlab


def _rescale(x):
    """MATLAB rescale(x) -> (x - min) / (max - min)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    return (x - x.min()) / (x.max() - x.min())


def _interp_extrap(xq, xp, fp):
    """MATLAB interp1(xp, fp, xq, 'linear', 'extrap'): linear w/ linear extrapolation."""
    xp = np.asarray(xp, dtype=np.float64).ravel()
    fp = np.asarray(fp, dtype=np.float64).ravel()
    xq = np.asarray(xq, dtype=np.float64).ravel()
    y = np.interp(xq, xp, fp)                       # interior + endpoint clamp
    # linear extrapolation for query points outside [xp[0], xp[-1]]
    if xp.size >= 2:
        left = xq < xp[0]
        if np.any(left):
            s = (fp[1] - fp[0]) / (xp[1] - xp[0])
            y[left] = fp[0] + s * (xq[left] - xp[0])
        right = xq > xp[-1]
        if np.any(right):
            s = (fp[-1] - fp[-2]) / (xp[-1] - xp[-2])
            y[right] = fp[-1] + s * (xq[right] - xp[-1])
    return y


def _as_scalar(v):
    a = np.asarray(v).ravel()
    return a[0] if a.size == 1 else None


def compute(datamat_path, params=None, seed=0):
    """Population peri-contact analysis (make_Fig8_plume_contacts.m numeric core).

    Returns a dict with n_contacts, n_trials, Emat/Hmat/Bmat (contacts x Nw,
    sorted by distance from source), head_p/body_p (contact KS), the random
    control p-values, the common time grid tw, per-contact trajC/distC, and the
    1-s pre/post mean arrays.
    """
    if params is None:
        params = config.get_params()

    C = params.contact
    win_s = float(C["win_s"])
    min_sep_s = float(C["min_sep_s"])
    min_dist_px = float(C["min_dist_px"])
    reward_px = float(C["reward_px"])
    prom_mult = float(C["prominence_mult"])
    arena_px = np.asarray(params.arena_px, dtype=np.float64)
    Nw = int(params.fig8_win_samples)
    half = win_s / 2.0
    tw = np.linspace(-half, half, Nw)               # common peri-contact grid (s)

    rng = np.random.default_rng(seed)

    trials = load_data_mat_struct(datamat_path)

    # accumulators
    ETHc, HSc, BSc = [], [], []
    distC, trajC, epC, trialC = [], [], [], []
    trajR = []
    preH, postH, preB, postB = [], [], [], []
    preHr, postHr, preBr, postBr = [], [], [], []

    for k, D in enumerate(trials):
        try:
            bt = np.asarray(D["body_time"], dtype=np.float64).ravel()
            body = lowpass_jitter(clean_track(np.asarray(D["body"], dtype=np.float64), arena_px))
            head = lowpass_jitter(clean_track(np.asarray(D["head"], dtype=np.float64), arena_px))
            bspd = compute_speed(body)
            # head has its own (shorter) time base -> remap onto body time
            hspd = _interp_extrap(bt, np.asarray(D["head_time"]).ravel(), compute_speed(head))

            eth_t = np.asarray(D["ethanol_time"], dtype=np.float64).ravel()
            ethraw = np.interp(bt, eth_t, np.asarray(D["ethanol"]).ravel(), left=0.0, right=0.0)
            ethdec = np.interp(bt, eth_t, np.asarray(D["ethdeconv_raw"]).ravel(), left=0.0, right=0.0)
            ethresc = _rescale(ethraw)              # [0,1] as in logFile.m
            logdec = np.log(np.maximum(ethdec, np.finfo(float).eps))  # trajectory colour

            src = np.asarray(D["endpoint"], dtype=np.float64).ravel()
            Fs_b = 1.0 / np.median(np.diff(bt))
            dist = np.hypot(body[:, 0] - src[0], body[:, 1] - src[1])

            # analyse only entry -> first reward
            reach_idx = np.flatnonzero(dist < reward_px)
            tend = bt.size
            if reach_idx.size:
                tend = int(reach_idx[0]) + 1        # 1-based count (MATLAB reach index)

            thr = _as_scalar(D.get("threshold"))
            if thr is None or not np.isfinite(thr) or thr <= 0:
                thr = 0.3
            thr = float(thr)

            seg = ethresc[:tend]
            if tend < 3 or seg.max() <= thr:
                locs = np.array([], dtype=int)
            else:
                locs = find_contacts(seg, thr, min_sep_s * Fs_b, prom_mult)

            for o in locs:
                o = int(o)
                d2 = dist[o]
                if d2 < min_dist_px:
                    continue
                tt = bt[o] + tw
                if tt[0] < bt[0] or tt[-1] > bt[-1]:
                    continue
                ETHc.append(np.interp(tt, bt, logdec))
                HSc.append(np.interp(tt, bt, hspd))
                BSc.append(np.interp(tt, bt, bspd))
                trajC.append(np.column_stack([np.interp(tt, bt, body[:, 0]),
                                              np.interp(tt, bt, body[:, 1])]))
                distC.append(d2)
                epC.append(src.copy())
                trialC.append(k)
                pre = (bt >= bt[o] - 1) & (bt < bt[o])
                post = (bt > bt[o]) & (bt <= bt[o] + 1)
                preH.append(np.mean(hspd[pre])); postH.append(np.mean(hspd[post]))
                preB.append(np.mean(bspd[pre])); postB.append(np.mean(bspd[post]))

            # one random no-contact control window per contact
            for _ in range(locs.size):
                c = int(rng.integers(1, max(2, tend) + 1)) - 1   # MATLAB randi(max(2,tend)), 1-based
                tt = bt[c] + tw
                if tt[0] < bt[0] or tt[-1] > bt[-1]:
                    continue
                seg_r = np.interp(tt, bt, ethresc)
                if np.any(seg_r >= thr):
                    continue
                trajR.append(np.column_stack([np.interp(tt, bt, body[:, 0]),
                                              np.interp(tt, bt, body[:, 1])]))
                pre = (bt >= bt[c] - 1) & (bt < bt[c])
                post = (bt > bt[c]) & (bt <= bt[c] + 1)
                preHr.append(np.mean(hspd[pre])); postHr.append(np.mean(hspd[post]))
                preBr.append(np.mean(bspd[pre])); postBr.append(np.mean(bspd[post]))
        except Exception as ME:  # noqa: BLE001 — mirror MATLAB per-trial try/catch
            print(f"  Fig8: trial {k} skipped ({ME})")

    n_contacts = len(ETHc)
    n_trials = len(np.unique(trialC)) if trialC else 0

    # heatmaps over ALL contacts, sorted by distance
    if n_contacts:
        distC = np.asarray(distC, dtype=np.float64)
        order = np.argsort(distC, kind="stable")
        Emat = np.vstack([ETHc[i] for i in order])
        Hmat = np.vstack([HSc[i] for i in order])
        Bmat = np.vstack([BSc[i] for i in order])
    else:
        distC = np.asarray(distC, dtype=np.float64)
        order = np.array([], dtype=int)
        Emat = np.empty((0, Nw)); Hmat = np.empty((0, Nw)); Bmat = np.empty((0, Nw))

    # KS tests (MATLAB kstest2 asymptotic p, H9). ksafe: needs >=2 finite each.
    def _ks(a, b):
        a = np.asarray(a, dtype=np.float64); b = np.asarray(b, dtype=np.float64)
        a = a[np.isfinite(a)]; b = b[np.isfinite(b)]
        if a.size < 2 or b.size < 2:
            return np.nan
        return ks_2samp_matlab(a, b)[1]

    head_p = _ks(preH, postH)
    body_p = _ks(preB, postB)
    head_pr = _ks(preHr, postHr)
    body_pr = _ks(preBr, postBr)

    return {
        "n_contacts": n_contacts,
        "n_trials": n_trials,
        "Emat": Emat,
        "Hmat": Hmat,
        "Bmat": Bmat,
        "head_p": head_p,
        "body_p": body_p,
        "head_pr": head_pr,
        "body_pr": body_pr,
        "tw": tw,
        "traj": [trajC[i] for i in order] if n_contacts else [],
        "trajC": trajC,
        "trajR": trajR,
        "distC": distC,
        "epC": np.asarray(epC, dtype=np.float64) if epC else np.empty((0, 2)),
        "trialC": np.asarray(trialC, dtype=int),
        "preH": np.asarray(preH), "postH": np.asarray(postH),
        "preB": np.asarray(preB), "postB": np.asarray(postB),
        "preHr": np.asarray(preHr), "postHr": np.asarray(postHr),
        "preBr": np.asarray(preBr), "postBr": np.asarray(postBr),
    }


def plot(res):
    """Render Fig. 8C heatmaps + Fig. 8D mean +/- SEM (mirrors the MATLAB figure).

    Optional; numeric compute() is what is tested. Uses the Agg backend.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tw = np.asarray(res["tw"]).ravel()
    Emat = np.asarray(res["Emat"]); Hmat = np.asarray(res["Hmat"]); Bmat = np.asarray(res["Bmat"])

    figC, axc = plt.subplots(1, 3, figsize=(11, 4), facecolor="w")
    for ax, M, ttl in zip(axc, (Emat, Hmat, Bmat),
                          ("Ci log ETH", "Cii head speed", "Ciii body speed")):
        ax.imshow(M, aspect="auto", extent=[tw[0], tw[-1], M.shape[0], 1], cmap="viridis")
        ax.axvline(0, color="w", ls="--")
        ax.set_title(ttl); ax.set_xlabel("s")
    axc[0].set_ylabel("contact (sorted by dist)")

    def _shaded(ax, M, c, ylabel):
        m = np.nanmean(M, axis=0)
        s = np.nanstd(M, axis=0, ddof=0) / np.sqrt(M.shape[0])
        ax.fill_between(tw, m - s, m + s, color=c, alpha=0.2, lw=0)
        ax.plot(tw, m, color=c, lw=2)
        ax.axvline(0, color="r", ls="--")
        ax.set_ylabel(ylabel)

    figD, axd = plt.subplots(3, 1, figsize=(6, 8), facecolor="w")
    _shaded(axd[0], Emat, "b", "log ETH"); axd[0].set_title("ethanol")
    _shaded(axd[1], Hmat, "k", "head speed")
    _shaded(axd[2], Bmat, "k", "body speed"); axd[2].set_xlabel("Time from contact (s)")
    return figC, figD
