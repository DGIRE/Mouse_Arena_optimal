#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
data.py -- the data layer behind the Mouse Arena Ethanol Console (no Qt).

Wraps the read-only ``mouse_arena_aggregate_io.Aggregate`` accessor and adds:

  * a flat **trial index** (IR status, date, animal, Loc) parsed from file names,
    mirroring the Data Console;
  * per-trial ethanol signal prep -- pick raw / deconvolved, rolling-percentile
    **baseline subtraction**, on the sensor's own 500 Hz clock;
  * **contact detection** -- above-threshold episodes of at least a minimum
    duration -- and each contact's head position + Euclidean distance to the
    target odor port (endpoint), using **shared-origin** clock alignment between
    the head track and the ethanol trace.

Everything here is plain NumPy so it can be unit-tested headlessly and reused by
downstream analyses (import the module functions directly).
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

import numpy as np

from . import console_config as C

if C.AGG_IO_DIR not in sys.path and os.path.isdir(C.AGG_IO_DIR):
    sys.path.insert(0, C.AGG_IO_DIR)

try:
    from mouse_arena_aggregate_io import Aggregate
except Exception as exc:  # pragma: no cover
    Aggregate = None
    _IMPORT_ERR = exc
else:
    _IMPORT_ERR = None


_DATE_RE = re.compile(r"(\d{1,2}-\d{1,2}-\d{4})")
_TRIAL_RE = re.compile(r"Trial[_ ]?(\d+)", re.IGNORECASE)
_LOC_RE = re.compile(r"Loc[_ ]?(\d+)", re.IGNORECASE)
_ANIMAL_RE = re.compile(r"(\d+)\s*_?\s*Trial", re.IGNORECASE)


def _parse_date(name):
    m = _DATE_RE.search(str(name))
    return m.group(1) if m else ""


def _date_key(s):
    try:
        mm, dd, yy = (int(x) for x in str(s).split("-"))
        return (yy, mm, dd)
    except Exception:
        return (9999, 99, 99)


# ===========================================================================
# Pure signal / contact helpers (reusable by downstream analyses)
# ===========================================================================
def rolling_percentile_baseline(y, fs, win_s=C.BASELINE_WIN_S, pct=C.BASELINE_PCT,
                                step_s=C.BASELINE_STEP_S):
    """Rolling low-percentile baseline of a 1-D signal (assumes ~uniform fs).

    Percentile is evaluated in a centred window at anchor samples spaced
    ``step_s`` apart, then linearly interpolated back to full resolution. This
    reproduces the reactions-v1 baseline (rolling 10th percentile, ~20 s window)
    efficiently without SciPy.
    """
    y = np.asarray(y, dtype=float).reshape(-1)
    n = y.size
    if n == 0:
        return np.zeros(0, float)
    win = max(1, int(round(win_s * fs)))
    step = max(1, int(round(step_s * fs)))
    half = win // 2
    anchors = np.arange(0, n, step)
    if anchors[-1] != n - 1:
        anchors = np.append(anchors, n - 1)
    vals = np.empty(anchors.shape, float)
    for i, a in enumerate(anchors):
        lo = max(0, a - half)
        hi = min(n, a + half + 1)
        seg = y[lo:hi]
        vals[i] = np.nanpercentile(seg, pct) if seg.size else 0.0
    if anchors.size == 1:
        return np.full(n, vals[0])
    return np.interp(np.arange(n), anchors, vals)


def detect_contacts(t, sig, thr, min_duration_s=C.MIN_DURATION_S):
    """Above-threshold episodes lasting >= min_duration_s.

    Parameters
    ----------
    t   : (N,) time in seconds (shared-origin), monotonically increasing
    sig : (N,) signal (already baseline-subtracted if desired)
    thr : float threshold in sig units
    min_duration_s : minimum episode duration to count as a contact

    Returns a list of dicts, one per qualifying episode::

        {i0, i1, t_onset, t_offset, duration_s, peak}

    ``i0`` is the onset sample index (first sample of the episode).
    """
    t = np.asarray(t, dtype=float).reshape(-1)
    sig = np.asarray(sig, dtype=float).reshape(-1)
    n = min(t.size, sig.size)
    t, sig = t[:n], sig[:n]
    if n == 0:
        return []
    above = np.isfinite(sig) & (sig >= float(thr))
    if not above.any():
        return []
    # contiguous runs of True
    idx = np.flatnonzero(above)
    splits = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate([[idx[0]], idx[splits + 1]])
    ends = np.concatenate([idx[splits], [idx[-1]]])       # inclusive
    out = []
    for i0, i1 in zip(starts, ends):
        t0 = float(t[i0])
        t1 = float(t[i1])
        # duration spans the samples; for a single-sample episode use one sample dt
        if i1 > i0:
            dur = t1 - t0
        else:
            dt = float(np.median(np.diff(t))) if n > 1 else 0.0
            dur = dt
        if dur + 1e-12 >= float(min_duration_s):
            out.append({"i0": int(i0), "i1": int(i1), "t_onset": t0,
                        "t_offset": t1, "duration_s": float(dur),
                        "peak": float(np.nanmax(sig[i0:i1 + 1]))})
    return out


def auto_threshold(sig, k=C.AUTO_THRESH_K):
    """Robust auto-seed: median + k * MAD (MAD scaled to std units)."""
    sig = np.asarray(sig, dtype=float).reshape(-1)
    sig = sig[np.isfinite(sig)]
    if sig.size == 0:
        return 0.0
    med = float(np.median(sig))
    mad = float(np.median(np.abs(sig - med)))
    return med + k * 1.4826 * mad


# ===========================================================================
# Trial records / prepared trial
# ===========================================================================
@dataclass
class TrialRec:
    index: int
    file_name: str
    lighting: str
    date: str
    date_key: tuple
    trial_no: int
    loc_no: int
    animal: int

    @property
    def label(self):
        bits = [f"#{self.index}"]
        if self.animal >= 0:
            bits.append(f"a{self.animal}")
        if self.trial_no >= 0:
            bits.append(f"T{self.trial_no}")
        if self.loc_no >= 0:
            bits.append(f"L{self.loc_no}")
        return " ".join(bits)


@dataclass
class TrialSignal:
    """Everything the view + contact logic need for one trial."""
    rec: TrialRec
    signal: str                 # "deconv" | "raw"
    baseline_on: bool
    baseline_params: dict
    fs: float
    t: np.ndarray               # ethanol time, shared-origin seconds
    raw: np.ndarray             # chosen signal on t (pre baseline-sub)
    baseline: np.ndarray        # rolling baseline on t (zeros if off)
    sig: np.ndarray             # baseline-subtracted signal on t (what we threshold)
    head_t: np.ndarray          # head time, shared-origin seconds
    head_x: np.ndarray          # head x on head_t
    head_y: np.ndarray          # head y on head_t
    endpoint: np.ndarray        # (2,) or None
    stored_threshold: float     # aggregate per-trial threshold attr (raw scale)
    extent: tuple = C.ARENA_EXTENT_PX

    # -- derived at a given threshold --------------------------------------
    def contacts(self, thr, min_duration_s=C.MIN_DURATION_S):
        return detect_contacts(self.t, self.sig, thr, min_duration_s)

    def on_mask(self, thr, min_duration_s=C.MIN_DURATION_S):
        """Binary odor-on mask on ``t`` (True inside qualifying episodes)."""
        m = np.zeros(self.t.shape, bool)
        for ep in self.contacts(thr, min_duration_s):
            m[ep["i0"]:ep["i1"] + 1] = True
        return m

    def contact_positions(self, contacts):
        """Head (x, y) at each contact onset time, via shared-origin interp.

        Returns (P, valid) where P is (K,2) with NaN where the onset falls
        outside head-track coverage, and ``valid`` is the finite-row mask.
        """
        if not contacts:
            return np.zeros((0, 2)), np.zeros(0, bool)
        ons = np.array([c["t_onset"] for c in contacts], float)
        if self.head_t.size >= 2:
            px = np.interp(ons, self.head_t, self.head_x, left=np.nan, right=np.nan)
            py = np.interp(ons, self.head_t, self.head_y, left=np.nan, right=np.nan)
        else:
            px = np.full(ons.shape, np.nan)
            py = np.full(ons.shape, np.nan)
        P = np.column_stack([px, py])
        valid = np.isfinite(P).all(axis=1)
        return P, valid

    def contact_distances(self, contacts):
        """Euclidean distance (px) from each contact onset position to the
        endpoint (odor port). NaN where position or endpoint is unavailable."""
        P, _ = self.contact_positions(contacts)
        if P.shape[0] == 0 or self.endpoint is None:
            return np.full(P.shape[0], np.nan)
        ep = np.asarray(self.endpoint, float).reshape(-1)[:2]
        return np.sqrt(((P - ep[None, :]) ** 2).sum(axis=1))


# ===========================================================================
# Data store
# ===========================================================================
class DataStore:
    def __init__(self, agg_path=None, agg=None):
        """Open an aggregate by path, or wrap an already-constructed accessor
        (``agg=`` -- used by the headless tests)."""
        if agg is not None:
            self.agg = agg
            self.path = getattr(agg, "path", "<in-memory>")
        else:
            if Aggregate is None:
                raise RuntimeError(
                    "Could not import mouse_arena_aggregate_io.Aggregate "
                    f"(looked in {C.AGG_IO_DIR!r}).\nOriginal error: {_IMPORT_ERR}")
            self.path = agg_path
            self.agg = Aggregate(agg_path)
        self._trials_raw = None
        self._recs = None
        self._build_index()

    def close(self):
        try:
            self.agg.close()
        except Exception:
            pass

    @property
    def extent(self):
        return C.ARENA_EXTENT_PX

    # -- index -----------------------------------------------------------
    def _build_index(self):
        try:
            idx = self.agg.behavior_index() or {}
        except Exception:
            idx = {}
        fns = idx.get("file_name") or []
        lts = idx.get("lighting") or []
        recs = []
        for i, (fn, lt) in enumerate(zip(fns, lts)):
            d = _parse_date(fn)
            tn = _TRIAL_RE.search(str(fn))
            ln = _LOC_RE.search(str(fn))
            an = _ANIMAL_RE.search(str(fn))
            recs.append(TrialRec(
                index=i, file_name=str(fn), lighting=str(lt) or "unknown",
                date=d, date_key=_date_key(d),
                trial_no=int(tn.group(1)) if tn else -1,
                loc_no=int(ln.group(1)) if ln else -1,
                animal=int(an.group(1)) if an else -1))
        self._recs = recs

    def _raw(self):
        if self._trials_raw is None:
            try:
                self._trials_raw = self.agg.behavior()
            except Exception:
                self._trials_raw = []
        return self._trials_raw

    # -- menus -----------------------------------------------------------
    def lightings(self):
        present = {r.lighting for r in self._recs}
        ordered = [l for l in C.LIGHTING_ORDER if l in present]
        ordered += sorted(present - set(ordered))
        return ordered

    def dates(self, lighting):
        recs = self._match(lighting, None)
        return sorted({r.date for r in recs if r.date}, key=_date_key)

    def end_locations(self, lighting, date):
        recs = self._match(lighting, date)
        return sorted({r.loc_no for r in recs})

    def _match(self, lighting, date, end_loc=None):
        out = []
        for r in self._recs:
            if lighting not in (None, C.LIGHTING_ALL) and r.lighting != lighting:
                continue
            if date not in (None, C.LIGHTING_ALL, "") and r.date != date:
                continue
            if end_loc not in (None, C.LIGHTING_ALL) and r.loc_no != int(end_loc):
                continue
            out.append(r)
        return out

    def trials_for(self, lighting, date, end_loc=None):
        recs = self._match(lighting, date, end_loc)
        recs.sort(key=lambda r: (r.date_key, r.loc_no,
                                 r.animal if r.animal >= 0 else 0,
                                 r.trial_no if r.trial_no >= 0 else r.index))
        return recs

    def rec_by_index(self, index):
        for r in self._recs:
            if r.index == int(index):
                return r
        return None

    # -- per-trial prep --------------------------------------------------
    def trial_signal(self, index, signal=C.DEFAULT_SIGNAL,
                     baseline_on=C.BASELINE_ON_DEFAULT,
                     baseline_pct=C.BASELINE_PCT, baseline_win_s=C.BASELINE_WIN_S,
                     baseline_step_s=C.BASELINE_STEP_S, fs=None):
        """Prepare one trial's thresholding signal (shared-origin clocks)."""
        rec = self.rec_by_index(index)
        raw = self._raw()
        if rec is None or rec.index >= len(raw):
            return None
        tr = raw[rec.index]
        fs = float(fs) if fs else C.FS_DEFAULT

        et = _vec(tr.get("ethanol_time"))
        sig_name = "ethdeconv" if signal == C.SIGNAL_DECONV else "ethanol"
        sig = _vec(tr.get(sig_name))
        if sig is None:                                  # fall back to raw
            sig = _vec(tr.get("ethanol"))
            signal = C.SIGNAL_RAW
        head = _xy(tr.get(C.TRAJ_POINT))
        ht = _vec(tr.get("head_time"))

        # shared-origin zero: earliest sample across the two clocks becomes t=0
        origins = [x[0] for x in (et, ht) if x is not None and x.size]
        t0 = min(origins) if origins else 0.0

        if et is not None and et.size:
            t = et - t0
        else:
            t = np.zeros(0, float)
        if sig is None:
            sig = np.zeros(t.shape, float)
        n = min(t.size, sig.size)
        t, sig = t[:n], sig[:n]

        if head is not None and ht is not None and head.shape[0] and ht.size:
            m = min(head.shape[0], ht.size)
            head_t = ht[:m] - t0
            head_x = head[:m, 0]
            head_y = head[:m, 1]
        else:
            head_t = np.zeros(0, float)
            head_x = np.zeros(0, float)
            head_y = np.zeros(0, float)

        bparams = {"method": "rolling_pct", "pct": float(baseline_pct),
                   "window_s": float(baseline_win_s), "step_s": float(baseline_step_s)}
        if baseline_on and t.size:
            base = rolling_percentile_baseline(sig, fs, win_s=baseline_win_s,
                                               pct=baseline_pct, step_s=baseline_step_s)
        else:
            base = np.zeros(t.shape, float)
            bparams = None
        sig_bs = sig - base

        ep = _vec(tr.get("endpoint"))
        ep = ep[:2] if (ep is not None and ep.size >= 2) else None

        return TrialSignal(
            rec=rec, signal=signal, baseline_on=bool(baseline_on),
            baseline_params=bparams, fs=fs, t=t, raw=sig, baseline=base, sig=sig_bs,
            head_t=head_t, head_x=head_x, head_y=head_y, endpoint=ep,
            stored_threshold=float(tr.get("threshold", np.nan)),
            extent=C.ARENA_EXTENT_PX)


# ---- small array helpers ---------------------------------------------------
def _vec(a):
    if a is None:
        return None
    return np.asarray(a, dtype=float).reshape(-1)


def _xy(a):
    if a is None:
        return None
    a = np.asarray(a, dtype=float)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if a.shape[1] != 2 and a.shape[0] == 2:
        a = a.T
    return a[:, :2]


# ---- distance summary (used by the UI + tests) -----------------------------
def distance_summary(dists):
    d = np.asarray(dists, float)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return {"n": 0, "min": None, "mean": None, "median": None, "max": None}
    return {"n": int(d.size), "min": float(d.min()), "mean": float(d.mean()),
            "median": float(np.median(d)), "max": float(d.max())}
