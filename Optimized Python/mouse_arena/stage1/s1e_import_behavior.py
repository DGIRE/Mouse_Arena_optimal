"""s1e_import_behavior — port of Stage1_Import/s1e_import_behavior.m.

STAGE 1e -- Data behind Figures 7-8: freely-behaving navigation trials.

Strategy (closest-to-paper first):
  1. Load the paper's aggregate DATA_MAT (MATLAB FILES/Data_Mat.mat), the
     114-trial struct the publication analyzed -- already contains body/head
     positions, times, ethanol, deconvolved ethanol, endpoints AND the
     per-trial thresholds. This IS the publication behavior dataset.
  2. If absent, auto-scan every date folder under P.head_root, pair each
     <name>.avi.dat with its tracking (<name>_DMD.mat if present), read the
     sensor, deconvolve with the BEHAVIOR kernel, read the location from the
     filename (_LocN), and set a data-driven threshold (baseline mean+3*std
     of dx/x) -- no user input.

OUTPUT (dict): {'DATA_MAT': [per-trial dict, ...]} (struct array, canonical
fields; illumination-tagged and filtered to params.lighting).
Reference: Tariq et al. (2020), Figs. 7-8. Source: Batch_*_MFT.m, logFile_means.m.
"""
from __future__ import annotations

import glob
import os

import numpy as np

from mouse_arena import config, dataio, deconvolution, kernels, lighting, metadata, tracking
from mouse_arena.io_labview import read_labview_dat

_DEFAULT_ARENA_ROOT = os.environ.get(
    "MA_ARENA_ROOT", os.path.join(os.sep, "GireLab_Data", "Mouse_Arena")
)


def _head_root(paths):
    """Resolve the head-mounted sensor root directory (s1e configuration)."""
    paths = paths or {}
    return paths.get(
        "head_root",
        os.path.join(paths.get("arena_root", _DEFAULT_ARENA_ROOT),
                     "Ethanol Sensor Data", "Ethanol Sensor on Head"),
    )


def _default_files_behavior(paths):
    """Return candidate paths to the paper's behavior/DATA_MAT file (s1e)."""
    head = _head_root(paths)
    return [
        os.path.join(head, "MATLAB FILES", "DATA_Mat_4_23_20.mat"),
        os.path.join(head, "MATLAB FILES", "Data_Mat.mat"),
        os.path.join(head, "MATLAB FILES", "Data_Mat_MFT_3_4_20.mat"),
    ]


def _threshold_from_ethdeconv(bt, et, ethdeconv, baseline_s):
    """MATLAB (ensure_behavior_fields.m / s1e inline):
        ethb = interp1(et, ethdeconv, bt, 'linear', 0);
        b0 = ethb(bt <= bt(1)+baseline_s);
        dxx = (ethb - mean(b0)) / mean(b0);
        threshold = mean(dxx) + 3*std(dxx);
    """
    bt = np.asarray(bt, dtype=np.float64).reshape(-1)
    et = np.asarray(et, dtype=np.float64).reshape(-1)
    ethdeconv = np.asarray(ethdeconv, dtype=np.float64).reshape(-1)
    ethb = np.interp(bt, et, ethdeconv, left=0.0, right=0.0)
    b0 = ethb[bt <= bt[0] + baseline_s]
    b0mean = b0.mean()
    dxx = (ethb - b0mean) / b0mean
    return float(dxx.mean() + 3.0 * dxx.std(ddof=1))   # MATLAB std() is N-1 (ddof=1)


def _ensure_behavior_fields(rows, params):
    """Port of the ensure_behavior_fields() local function in s1e_import_behavior.m.

    Make every trial usable by Figs 7-8 regardless of which aggregate was
    loaded. Some aggregates (e.g. Data_Mat.mat) lack 'ethdeconv_raw' and
    'threshold'; derive them here so downstream figures never hit a missing
    field.
    """
    K = params.kernel_behavior
    out = []
    for r in rows:
        r = dict(r)
        et = r.get("ethanol_time")
        if et is None or np.asarray(et).size == 0:
            out.append(r)
            continue
        et = np.asarray(et, dtype=np.float64).reshape(-1)

        dt = np.median(np.diff(et))
        Fs = 1.0 / dt if (np.isfinite(dt) and dt > 0) else params.Fs

        raw_e = r.get("eth_raw")
        if raw_e is None or np.asarray(raw_e).size == 0:
            raw_e = r.get("ethanol")
        raw_e = np.asarray(raw_e, dtype=np.float64).reshape(-1)

        if "ethdeconv_raw" not in r or np.asarray(r["ethdeconv_raw"]).size == 0:
            kn = kernels.doe_kernel(K["tau_rise"], K["tau_decay"], raw_e.size, Fs)
            ethdeconv_raw, _ = deconvolution.deconvolve_eth(raw_e, kn, Fs)
            r["ethdeconv_raw"] = ethdeconv_raw

        if "threshold" not in r or np.asarray(r["threshold"]).size == 0:
            bt = np.asarray(r["body_time"], dtype=np.float64).reshape(-1)
            r["threshold"] = _threshold_from_ethdeconv(
                bt, et, r["ethdeconv_raw"], params.contact["baseline_s"]
            )

        out.append(r)
    return out


def _report_lighting(rows):
    """Port of report_lighting() -- informational only (fprintf in MATLAB)."""
    if not rows:
        return
    labels = [str(r.get("lighting", "unknown")) for r in rows]
    uniq = sorted(set(labels))
    parts = [f"{u}={labels.count(u)}" for u in uniq]
    print("s1e: lighting -> " + ", ".join(parts))


def import_from(path, params=None):
    """Pure transform: load the paper aggregate DATA_MAT, ensure derived
    fields, tag lighting, and filter to params.lighting.

    MATLAB:
        S = load(src,'DATA_MAT');
        DATA_MAT = ensure_behavior_fields(S.DATA_MAT, P);
        for k = 1:numel(DATA_MAT)
            DATA_MAT(k).lighting = lighting_for_trial(DATA_MAT(k).file_name);
        end
        report_lighting(DATA_MAT);
        DATA_MAT = filter_lighting(DATA_MAT, P.lighting);
    """
    if params is None:
        params = config.get_params()

    rows = dataio.load_data_mat_struct(path)
    rows = _ensure_behavior_fields(rows, params)
    for r in rows:
        r["lighting"] = lighting.lighting_for_trial(r.get("file_name", ""))
    _report_lighting(rows)
    rows = lighting.filter_lighting(rows, params.lighting)

    return {"DATA_MAT": rows}


def _local_endpoints(head_root):
    """Port of local_endpoints() local function."""
    fp = os.path.join(head_root, "MATLAB FILES", "Endpoints_anotherLoc.csv")
    if os.path.isfile(fp):
        return np.loadtxt(fp, delimiter=",")
    fp2 = os.path.join(head_root, "endpoints.mat")
    if os.path.isfile(fp2):
        S = dataio.load_mat(fp2)
        return np.asarray(S["endpoints"], dtype=np.float64)
    return np.full((6, 3), np.nan)


def _local_unpack(T):
    """Port of local_unpack() local function."""
    if "cr" in T:
        body = np.asarray(T["cr"], dtype=np.float64)
    elif "body" in T:
        body = np.asarray(T["body"], dtype=np.float64)
    else:
        body = np.asarray(T["cr_head"], dtype=np.float64)
    head = np.asarray(T["cr_head"], dtype=np.float64) if "cr_head" in T else body
    if "fr_ts_head" in T:
        ht = np.asarray(T["fr_ts_head"], dtype=np.float64).reshape(-1)
    else:
        ht = np.arange(head.shape[0], dtype=np.float64)
    bt = np.arange(body.shape[0], dtype=np.float64)
    return body, head, bt, ht


def _from_raw(head_root, params):
    """Fallback: auto-derive DATA_MAT from every dated *.avi.dat + *_DMD.mat
    pair under head_root (see s1e_import_behavior.m, lines ~39-81).
    """
    K = params.kernel_behavior
    endpoints = _local_endpoints(head_root)
    dats = sorted(glob.glob(os.path.join(head_root, "**", "*.avi.dat"), recursive=True))

    rows = []
    for fpath in dats:
        d = os.path.dirname(fpath)
        name = os.path.basename(fpath)
        base = name[: -len(".avi.dat")]
        avi_file = os.path.join(d, base + ".avi")
        if not os.path.isfile(avi_file):
            continue
        mat_file = os.path.join(d, base + "_DMD.mat")
        if not os.path.isfile(mat_file):
            continue
        T = dataio.load_mat(mat_file)
        if not T:
            continue

        body, head, bt, ht = _local_unpack(T)
        body = tracking.lowpass_jitter(body)
        head = tracking.lowpass_jitter(head)

        D = read_labview_dat(fpath, params.chan_beh, params)
        Fs = float(D["Fs"])
        kn = kernels.doe_kernel(K["tau_rise"], K["tau_decay"], np.asarray(D["ETH"]).size, Fs)
        ethdeconv, _ = deconvolution.deconvolve_eth(D["ETH"], kn, Fs)
        etime = np.asarray(D["time"], dtype=np.float64).reshape(-1) / 1000.0

        meta = metadata.parse_trial_meta(base)
        loc = meta["loc"]
        if np.isnan(loc) or loc < 1 or loc > endpoints.shape[0]:
            ep = np.array([np.nan, np.nan])
        else:
            ep = np.asarray(endpoints[int(loc) - 1, -2:], dtype=np.float64)

        thr = _threshold_from_ethdeconv(bt, etime, ethdeconv, params.contact["baseline_s"])

        rows.append({
            "body": body, "head": head,
            "body_time": bt, "head_time": ht,
            "ethanol": np.asarray(D["ETH"], dtype=np.float64), "ethanol_time": etime,
            "ethdeconv_raw": np.asarray(ethdeconv, dtype=np.float64), "endpoint": ep,
            "threshold": thr, "file_name": name,
            "lighting": lighting.lighting_for_trial(name),
        })

    if rows:
        _report_lighting(rows)
    rows = lighting.filter_lighting(rows, params.lighting)

    return {"DATA_MAT": rows}


def run(params=None, paths=None):
    """Higher-level entry: resolve the paper aggregate (or raw fallback) and import it."""
    if params is None:
        params = config.get_params()
    paths = paths or {}

    candidates = paths.get("files_behavior") or _default_files_behavior(paths)
    src = metadata.ma_first(candidates)
    if src:
        return import_from(src, params)

    return _from_raw(_head_root(paths), params)
