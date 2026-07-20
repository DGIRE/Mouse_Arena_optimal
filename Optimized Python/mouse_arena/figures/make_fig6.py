"""make_fig6 — port of Stage2_Figures/make_Fig6_calcium_OB.m. [Low risk, scaffold]

FIGURE 6 -- Ethanol plume detected by the sensor coincides with olfactory
bulb (OB) glomerular activation (widefield calcium imaging).
  C: dF/F from 10 glomeruli for a single trial.
  D: mean activity of 6 glomeruli over presentations, aligned to first ETH
     peak.
  E: PCA trajectory in the first 2 PCs after plume detection.
  F: Euclidean distance between PCs, rest vs post-plume, over sessions
     (only if a per-session breakdown is supplied).

(Panel A -- resting-fluorescence/SD imaging frames -- is not numeric and is
skipped here.)

INPUT: the s1d "calcium" dict (SCAFFOLD -- s1d_import_calcium_OB.m header:
"the disorganized repo contains NO calcium code, so this figure is a
scaffold that plots whatever s1d produces"). MATLAB behavior: if
`calcium.mat` has no `available` field, or `available` is false, the script
warns "Figure 6 skipped: no calcium data..." and returns without producing
any panels. We mirror that exactly: `compute()` returns
`{'available': False}` (a no-op) whenever `data` is empty/None or lacks a
truthy 'available' key -- no error is raised, matching the MATLAB `return`
(as opposed to the preceding `error(...)` which only fires if `calcium.mat`
itself is entirely missing, a case s1d's caller is responsible for).

When calcium data *is* available, expected fields (mirroring S = load(cf)):
  dFF      : (nGlom, nTime, nTrial) dF/F traces
  ethA     : sensor trace(s) aligned to the same time base (unused
             numerically here besides being passed through)
  t        : (nTime,) time vector, aligned to plume/peak (0 = ETH peak)
  restIdx  : boolean mask (or index array) into `t`/PCA rows selecting the
             pre-plume "rest" period
  postIdx  : boolean mask (or index array) selecting the post-plume period
  sessions : optional list of {'rest': (n,d) points, 'post': (m,d) points}
             per-session point clouds for Panel F (MATLAB: `sessions`
             variable, only used `if exist('sessions','var')`)
"""
import numpy as np


def _has_calcium(data):
    return bool(data) and bool(data.get("available", False))


def _as_index(mask_or_idx, n):
    """Accept either a boolean mask or an integer index array; return int indices.

    MATLAB restIdx/postIdx could be either logical masks or numeric indices;
    normalize to a 0-based integer index array against a dimension of length n.
    """
    a = np.asarray(mask_or_idx)
    if a.dtype == bool or (a.size == n and set(np.unique(a)).issubset({0, 1})):
        return np.flatnonzero(a.astype(bool))
    # Treat as MATLAB 1-based indices.
    return (a.reshape(-1).astype(np.int64) - 1)


def compute(data, params=None):
    """Numeric core behind Fig6's panels -- gracefully no-ops without calcium data.

    Returns {'available': False} if `data` is missing/empty or
    `data['available']` is falsy (mirrors the MATLAB early-return/warning).
    Otherwise returns {'available': True, 'C': {...}, 'D': {...},
    'E': {...}, 'F': {...} (present only if `sessions` supplied)}.
    """
    if not _has_calcium(data):
        return {"available": False}

    params = dict(params or {})
    dFF = np.asarray(data["dFF"], dtype=np.float64)
    t = np.asarray(data["t"], dtype=np.float64).reshape(-1)
    nGlom, nTime, nTrial = dFF.shape

    # ---- Panel C: single-trial traces from up to 10 glomeruli -------------
    tr = int(params.get("trial_idx", 0))  # MATLAB tr=1 (1-based) -> 0-based here
    g10 = np.arange(min(10, nGlom))
    stack = dFF[g10, :, tr].T + np.arange(g10.size) * 1.0  # (nTime, len(g10)), offset stack
    panelC = {"t": t, "glom_idx": g10, "stack": stack}

    # ---- Panel D: mean activity of 6 glomeruli over presentations ---------
    g6_1based = np.round(np.linspace(1, nGlom, 6)).astype(int)
    g6 = g6_1based - 1
    means = np.stack([dFF[gi, :, :].mean(axis=1) for gi in g6], axis=0)  # (6, nTime)
    panelD = {"t": t, "glom_idx": g6, "mean_dFF": means}

    # ---- Panel E: PCA trajectory in first 2 PCs ----------------------------
    # X = reshape(permute(dFF,[2 1 3]), nTime, []) -- MATLAB column-major reshape
    # combining (glom, trial) into columns with glom varying fastest.
    permuted = np.transpose(dFF, (1, 0, 2))  # (nTime, nGlom, nTrial)
    X = permuted.reshape(nTime, nGlom * nTrial, order="F")
    finite_cols = np.all(np.isfinite(X), axis=0)
    X = X[:, finite_cols]

    panelE = None
    if X.shape[1] >= 2 and X.shape[0] >= 2:
        # zscore(X,0,1): per-column zscore across rows (time), sample std (ddof=1).
        mu = X.mean(axis=0, keepdims=True)
        sd = X.std(axis=0, ddof=1, keepdims=True)
        sd = np.where(sd == 0, 1.0, sd)
        Xz = (X - mu) / sd

        Xc = Xz - Xz.mean(axis=0, keepdims=True)
        U, S, _Vt = np.linalg.svd(Xc, full_matrices=False)
        score = U * S  # (nTime, nComponents); PCA scores (sign is arbitrary, per SVD)
        var = S ** 2
        explained = var / var.sum() * 100.0 if var.sum() > 0 else np.zeros_like(var)

        restIdx = _as_index(data["restIdx"], nTime) if "restIdx" in data else np.array([], dtype=int)
        postIdx = _as_index(data["postIdx"], nTime) if "postIdx" in data else np.array([], dtype=int)
        panelE = {
            "score": score,
            "explained_pct": explained,
            "rest_pc12": score[restIdx, :2] if restIdx.size and score.shape[1] >= 2 else np.empty((0, 2)),
            "post_pc12": score[postIdx, :2] if postIdx.size and score.shape[1] >= 2 else np.empty((0, 2)),
        }

    out = {"available": True, "C": panelC, "D": panelD, "E": panelE}

    # ---- Panel F: rest vs post-plume PC distance across sessions ----------
    if "sessions" in data and data["sessions"]:
        from scipy.spatial.distance import pdist

        sessions = data["sessions"]
        d_rest = np.empty(len(sessions))
        d_post = np.empty(len(sessions))
        for si, sess in enumerate(sessions):
            rest_pts = np.asarray(sess["rest"], dtype=np.float64)
            post_pts = np.asarray(sess["post"], dtype=np.float64)
            d_rest[si] = pdist(rest_pts).mean() if rest_pts.shape[0] > 1 else np.nan
            d_post[si] = pdist(post_pts).mean() if post_pts.shape[0] > 1 else np.nan
        out["F"] = {"d_rest": d_rest, "d_post": d_post}

    return out


def plot(data, params=None):
    """Optional matplotlib reproduction of Fig6's panels (Agg backend).

    Returns {} (no figures) when calcium data is unavailable, mirroring the
    MATLAB script's early `return` (a warning, not an error).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(data, dict) and "available" in data and ("C" in data or data.get("available") is False):
        res = data
    else:
        res = compute(data, params)

    if not res.get("available", False):
        return {}

    figs = {}

    C = res["C"]
    figC, axC = plt.subplots(figsize=(6, 4))
    axC.plot(C["t"], C["stack"])
    axC.set_xlabel("Time from plume (s)")
    axC.set_ylabel("dF/F (offset)")
    axC.set_title("10 glomeruli")
    figs["C"] = figC

    D = res["D"]
    figD, axD = plt.subplots(figsize=(6, 4))
    for row in D["mean_dFF"]:
        axD.plot(D["t"], row, linewidth=1.5)
    axD.axvline(0, color="k", linestyle="--")
    axD.set_xlabel("Time from ETH peak (s)")
    axD.set_ylabel("mean dF/F")
    axD.set_title("6 glomeruli, mean over presentations")
    figs["D"] = figD

    E = res.get("E")
    if E is not None:
        figE, axE = plt.subplots(figsize=(5, 5))
        if E["rest_pc12"].size:
            axE.plot(E["rest_pc12"][:, 0], E["rest_pc12"][:, 1], "b")
        if E["post_pc12"].size:
            axE.plot(E["post_pc12"][:, 0], E["post_pc12"][:, 1], "b-", linewidth=1.5)
            axE.plot(E["post_pc12"][:, 0], E["post_pc12"][:, 1], "r.")
        expl = E["explained_pct"]
        axE.set_xlabel(f"PC1 ({expl[0]:.0f}%)" if expl.size else "PC1")
        axE.set_ylabel(f"PC2 ({expl[1]:.0f}%)" if expl.size > 1 else "PC2")
        axE.set_title("OB population trajectory after plume")
        figs["E"] = figE

    if "F" in res:
        F = res["F"]
        figF, axF = plt.subplots(figsize=(4, 4))
        for d_rest, d_post in zip(F["d_rest"], F["d_post"]):
            axF.plot([1, 2], [d_rest, d_post], "-o")
        axF.set_xticks([1, 2])
        axF.set_xticklabels(["rest", "post-plume"])
        axF.set_ylabel("PC Euclidean dist")
        figs["F"] = figF

    return figs
