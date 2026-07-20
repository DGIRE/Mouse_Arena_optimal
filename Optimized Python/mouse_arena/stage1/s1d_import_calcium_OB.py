"""s1d_import_calcium_OB — port of Stage1_Import/s1d_import_calcium_OB.m.

STAGE 1d -- Data behind Figure 6: widefield calcium imaging of dorsal OB
(Thy1-GCaMP6f) paired with the ethanol sensor.

This pipeline has NO calcium/CNMF data or code in the Mouse Arena archive
(it is entirely behavior/sensor). The script therefore auto-checks the
expected location and, if nothing is found, returns a clearly-marked
placeholder ({'available': False}) so the rest of the pipeline runs without
stopping. To populate Figure 6, drop a CNMF result named 'calcium_raw.mat'
(fields C [nGlom x nFrames x nTrial] and eth [nFrames x nTrial]) into out_root.

Reference: Tariq et al. (2020), Fig. 6; Methods (CNMF, align to first ETH peak).
"""
from __future__ import annotations

import os
import warnings

import numpy as np

from mouse_arena import config, dataio, metadata

_DEFAULT_ARENA_ROOT = os.environ.get(
    "MA_ARENA_ROOT", os.path.join(os.sep, "GireLab_Data", "Mouse_Arena")
)


def _paper_root(paths):
    """Resolve the paper backup root directory (s1d configuration)."""
    paths = paths or {}
    return paths.get(
        "paper_root",
        os.path.join(paths.get("arena_root", _DEFAULT_ARENA_ROOT),
                     "Ethanol Sensor Data", "Paper_BackUp", "Paper"),
    )


def _out_root(paths):
    """Resolve the output root directory for reconstruction results."""
    paths = paths or {}
    return paths.get(
        "out_root",
        os.path.join(paths.get("arena_root", _DEFAULT_ARENA_ROOT), "_reconstruction_outputs"),
    )


def _default_files_calcium(paths):
    """Return candidate paths to calcium imaging data (s1d)."""
    return [
        os.path.join(_out_root(paths), "calcium_raw.mat"),
        os.path.join(_paper_root(paths), "Fig6", "calcium_raw.mat"),
    ]


def import_from(path, params=None):
    """Pure transform: load a CNMF calcium_raw.mat and align every trial to
    the first ethanol peak after stimulus (plume arrival).

    MATLAB:
        R = load(src);         % C [nGlom x nFrames x nTrial], eth [nFrames x nTrial]
        C = R.C; eth = R.eth; Fs = P.Fs;
        nTr = size(C,3); win = round(4*Fs);
        for tr=1:nTr
            e = eth(:,tr);
            [~,pk] = max(e);                       % first dominant peak = plume arrival
            idx = pk-win : pk+win; idx = idx(idx>=1 & idx<=size(C,2));
            dFF(:,1:numel(idx),tr) = C(:,idx,tr);
            ethA(1:numel(idx),tr)  = e(idx);
        end
        t = ((1:size(dFF,2))-win-1)/Fs;
        restIdx = t<0; postIdx = t>=0; available = true;
    """
    if params is None:
        params = config.get_params()
    Fs = params.Fs

    R = dataio.load_mat(path)
    C = np.asarray(R["C"], dtype=np.float64)
    eth = np.asarray(R["eth"], dtype=np.float64)

    nGlom, nFrames, nTr = C.shape
    win = int(round(4 * Fs))
    win_len = 2 * win + 1

    dFF = np.zeros((nGlom, win_len, nTr), dtype=np.float64)
    ethA = np.zeros((win_len, nTr), dtype=np.float64)

    for tr in range(nTr):
        e = eth[:, tr]
        pk = int(np.argmax(e))                     # 0-based index of first dominant peak
        # MATLAB: idx = pk-win : pk+win (1-based); idx = idx(idx>=1 & idx<=size(C,2))
        idx1 = np.arange((pk + 1) - win, (pk + 1) + win + 1)   # 1-based candidate window
        idx1 = idx1[(idx1 >= 1) & (idx1 <= nFrames)]
        idx0 = idx1 - 1                                        # -> 0-based
        n = idx0.size
        dFF[:, :n, tr] = C[:, idx0, tr]
        ethA[:n, tr] = e[idx0]

    t = (np.arange(1, win_len + 1, dtype=np.float64) - win - 1) / Fs
    restIdx = t < 0
    postIdx = t >= 0

    return {
        "dFF": dFF,
        "ethA": ethA,
        "t": t,
        "restIdx": restIdx,
        "postIdx": postIdx,
        "available": True,
    }


def run(params=None, paths=None):
    """Higher-level entry: look for a CNMF calcium_raw.mat; if absent, return
    the {'available': False} placeholder (see module docstring / s1d.m).
    """
    if params is None:
        params = config.get_params()
    paths = paths or {}

    candidates = paths.get("files_calcium") or _default_files_calcium(paths)
    src = metadata.ma_first(candidates)
    if not src:
        warnings.warn(
            "s1d: no calcium data found (Fig 6 has no data/code in this archive). "
            "Returning a placeholder; supply calcium_raw.mat to populate."
        )
        return {"available": False}

    return import_from(src, params)
