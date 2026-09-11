#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data.py -- the data layer behind the Mouse Arena Data Console.

Wraps the read-only ``mouse_arena_aggregate_io.Aggregate`` accessor and adds
everything the UI needs, with NO Qt dependency:

  * a flat **trial index** built from ``/behavior`` -- each trial's IR status
    (lighting), recording **date** (parsed from the file name), and a short
    Loc/Trial label;
  * IR-status and date menus, and a per-(status,date) trial list;
  * per-trial **head trajectory** + **ethanol concentration at each head sample**
    (the head-mounted sensor trace, raw or deconvolved, interpolated onto the
    head time base), plus the ethanol **time series** for the panel below the
    arena, and the single target **odor-port** location (the reward endpoint);
  * a seconds window and per-trial length statistics.

Concentration is normalised to [0, 1] across the current selection so the dot
alpha, the alpha threshold, and the vmin/vmax colour range all live in [0, 1]
and the time-series threshold line is in the same units.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

import numpy as np

from . import arena_config as C

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
# animal id: the number just before "_Trial" (e.g. "...-Mohammad-204_Trial6" -> 204)
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


@dataclass
class TrialRec:
    index: int                 # 0-based trial index in /behavior
    file_name: str
    lighting: str
    date: str
    date_key: tuple
    trial_no: int              # from "Trial N" (or -1)
    loc_no: int                # from "Loc N" (or -1) -- the end (odor-port) location
    animal: int                # animal id from the file name (or -1)

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
class TrialData:
    label: str
    lighting: str
    date: str
    x: np.ndarray            # head x, windowed, finite mask applied at draw
    y: np.ndarray            # head y
    conc: np.ndarray         # normalised concentration at each head sample [0,1]
    t_series: np.ndarray     # ethanol time (s, zero-based, windowed)
    sig_series: np.ndarray   # normalised ethanol signal on t_series [0,1]
    endpoint: np.ndarray     # (2,) target odor-port location, or None
    length_s: float
    color: str = "#1f77b4"
    file_name: str = ""      # source recording name for this trial


@dataclass
class Selection:
    lighting: str
    date: str
    signal: str
    trials: list = field(default_factory=list)     # list[TrialData]
    lengths_s: list = field(default_factory=list)
    n_trials: int = 0
    pooled_max: float = 1.0
    note: str = ""


class DataStore:
    def __init__(self, agg_path):
        if Aggregate is None:
            raise RuntimeError(
                "Could not import mouse_arena_aggregate_io.Aggregate "
                f"(looked in {C.AGG_IO_DIR!r}).\nOriginal error: {_IMPORT_ERR}")
        self.path = agg_path
        self.agg = Aggregate(agg_path)
        self._trials_raw = None          # cached agg.behavior() (arrays)
        self._recs = None                # list[TrialRec]
        self._build_index()

    def close(self):
        try:
            self.agg.close()
        except Exception:
            pass

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
        """All behavior trials with arrays (cached; loaded once)."""
        if self._trials_raw is None:
            try:
                self._trials_raw = self.agg.behavior()
            except Exception:
                self._trials_raw = []
        return self._trials_raw

    @property
    def extent(self):
        return C.ARENA_EXTENT_PX

    # -- menus -----------------------------------------------------------
    def lightings(self):
        present = {r.lighting for r in self._recs}
        ordered = [l for l in C.LIGHTING_ORDER if l in present]
        ordered += sorted(present - set(ordered))
        return ordered

    def dates(self, lighting):
        recs = self._match(lighting, None)
        uniq = sorted({r.date for r in recs if r.date}, key=_date_key)
        return uniq

    def end_locations(self, lighting, date):
        """Ordered list of distinct end (odor-port) locations present for the IR
        status + date, as Loc indices (-1 = unknown/no Loc token)."""
        recs = self._match(lighting, date)
        return sorted({r.loc_no for r in recs})

    def animals_at(self, lighting, date, end_loc):
        """Animal ids that have a trial at the given end location (for the IR
        status + date). Feeds the 'only animals with that end location become
        selectable' filter."""
        recs = self._match(lighting, date, end_loc)
        return sorted({r.animal for r in recs if r.animal >= 0})

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
        """Ordered list of TrialRec matching the IR status, date, and (optionally)
        end location. With an end location set, only trials/animals that used that
        odor-port location are returned -- so only they become selectable."""
        recs = self._match(lighting, date, end_loc)
        recs.sort(key=lambda r: (r.date_key, r.loc_no,
                                 r.animal if r.animal >= 0 else 0,
                                 r.trial_no if r.trial_no >= 0 else r.index))
        return recs

    # -- collect ---------------------------------------------------------
    def collect(self, lighting, date, trial_indices, seconds=(0.0, 0.0),
                signal=C.DEFAULT_SIGNAL, end_loc=None):
        t0, t1 = seconds if seconds else (0.0, 0.0)
        raw = self._raw()
        recs = self.trials_for(lighting, date, end_loc)
        if trial_indices:
            want = set(int(i) for i in trial_indices)
            recs = [r for r in recs if r.index in want]

        # first pass: windowed head coords + concentration on head-time, plus the
        # windowed sensor time series -- collect raw (un-normalised) signal to set
        # one shared normalisation scalar for the whole selection.
        prepared = []
        pooled_peak = 0.0
        for k, r in enumerate(recs):
            if r.index >= len(raw):
                continue
            tr = raw[r.index]
            head = _xy(tr.get(C.TRAJ_POINT))
            ht = _vec(tr.get("head_time"))
            if head is None or ht is None or head.shape[0] == 0:
                continue
            n = min(head.shape[0], ht.shape[0])
            head, ht = head[:n], ht[:n]
            sig = _vec(tr.get("ethdeconv") if signal == C.SIGNAL_DECONV else None)
            if sig is None:
                sig = _vec(tr.get("ethanol"))
            et = _vec(tr.get("ethanol_time"))
            # zero-base the two clocks to the trial start
            t_rel = ht - ht[0] if ht.size else ht
            # concentration at each head sample (interp sensor onto head clock)
            if sig is not None and et is not None and et.size >= 2:
                et_rel = et - et[0]
                conc = np.interp(t_rel, et_rel, sig, left=sig[0], right=sig[-1])
                ts_t, ts_sig = et_rel, sig
            else:
                conc = np.zeros(t_rel.shape, float)
                ts_t = t_rel
                ts_sig = conc
            # seconds window (relative to trial start)
            hm = _window_mask(t_rel, t0, t1)
            sm = _window_mask(ts_t, t0, t1)
            hx, hy = head[hm, 0], head[hm, 1]
            hc = conc[hm]
            ts_t_w, ts_sig_w = ts_t[sm], ts_sig[sm]
            length_s = float(t_rel[hm][-1] - t_rel[hm][0]) if np.count_nonzero(hm) > 1 else 0.0
            peak = np.nanmax(np.abs(hc)) if hc.size else 0.0
            peak = max(peak, np.nanmax(np.abs(ts_sig_w)) if ts_sig_w.size else 0.0)
            pooled_peak = max(pooled_peak, float(peak) if np.isfinite(peak) else 0.0)
            prepared.append(dict(
                rec=r, x=hx, y=hy, conc=hc, ts_t=ts_t_w, ts_sig=ts_sig_w,
                endpoint=_vec(tr.get("endpoint")), length_s=length_s,
                color=C.TRIAL_COLORS[k % len(C.TRIAL_COLORS)]))

        norm = pooled_peak if pooled_peak > C.NORM_EPS else 1.0
        sel = Selection(lighting=lighting, date=date, signal=signal,
                        pooled_max=norm, n_trials=len(prepared))
        for p in prepared:
            ep = p["endpoint"]
            ep = ep[:2] if (ep is not None and ep.size >= 2) else None
            sel.trials.append(TrialData(
                label=p["rec"].label, lighting=p["rec"].lighting, date=p["rec"].date,
                x=p["x"], y=p["y"], conc=np.clip(p["conc"] / norm, 0.0, 1.0),
                t_series=p["ts_t"], sig_series=np.clip(p["ts_sig"] / norm, None, None),
                endpoint=ep, length_s=p["length_s"], color=p["color"],
                file_name=p["rec"].file_name))
            sel.lengths_s.append(p["length_s"])
        return sel


# ---- small array helpers ---------------------------------------------------
def _vec(a):
    if a is None:
        return None
    a = np.asarray(a, dtype=float).reshape(-1)
    return a


def _xy(a):
    if a is None:
        return None
    a = np.asarray(a, dtype=float)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if a.shape[1] != 2 and a.shape[0] == 2:
        a = a.T
    return a[:, :2]


def _window_mask(t, t0, t1):
    t = np.asarray(t, float)
    if t.size == 0:
        return np.zeros(0, bool)
    m = np.ones(t.shape, bool)
    if t0 and t0 > 0:
        m &= t >= t0
    if t1 and t1 > 0:
        m &= t <= t1
    return m
