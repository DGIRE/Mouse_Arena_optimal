#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
main_window.py -- the Mouse Arena Ethanol Console main window.

Top control bar:

  row 1 : [IR status v] [Date v] [End loc v] | Trial: [combo] [< Prev] [Next >]
          (Left / Right arrow keys also advance the trial)
  row 2 : Signal: (o) Deconvolved (o) Raw | Baseline [x] pct[ ] win(s)[ ] |
          Min dur (s)[ ]
  row 3 : Threshold [spin] [Auto] | Contacts: <n>  dist px: min/mean/max |
          [Save (Enter)]  <saved indicator>

Below: the Ethanol view -- trajectory map (left) + binary on/off preview (top
right) over the thresholding trace (bottom right, with box-zoom toolbar).

Enter saves the current trial's threshold + computed contacts into the master
JSON (output/ + a DATA mirror), each stamped with a production date/time.
"""
from __future__ import annotations

import os

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from . import console_config as C
from . import data as D
from .data import DataStore
from .thresholds import ThresholdStore
from .view import EthanolView
from . import __version__


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, agg_path):
        super().__init__()
        self.setWindowTitle("Mouse Arena Ethanol Console")
        self.resize(1280, 860)
        self.store = DataStore(agg_path)
        self.jstore = ThresholdStore(getattr(self.store, "path", agg_path),
                                     version=__version__)
        self._loading = True
        self._order = []            # list[TrialRec] in the current filter
        self._pos = -1              # index into self._order
        self._ts = None             # current TrialSignal
        self._last_handles = None

        bar = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(bar)
        v.setContentsMargins(8, 6, 8, 4)
        v.setSpacing(4)
        v.addWidget(self._build_row1())
        v.addWidget(self._build_row2())
        v.addWidget(self._build_row3())

        self.view = EthanolView()
        self.view.set_threshold_callback(self._on_line_drag)

        central = QtWidgets.QWidget()
        cv = QtWidgets.QVBoxLayout(central)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(bar)
        cv.addWidget(self.view, 1)
        self.setCentralWidget(central)
        self.status = self.statusBar()

        self._populate_lightings()
        self._wire()
        self._install_shortcuts()
        self._loading = False
        self._on_lighting_changed()

    # ================================================================ build
    def _build_row1(self):
        w = QtWidgets.QWidget(); h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        self.cb_light = QtWidgets.QComboBox(); self.cb_light.setMinimumWidth(110)
        self.cb_date = QtWidgets.QComboBox(); self.cb_date.setMinimumWidth(120)
        self.cb_endloc = QtWidgets.QComboBox(); self.cb_endloc.setMinimumWidth(110)
        self.cb_trial = QtWidgets.QComboBox(); self.cb_trial.setMinimumWidth(240)
        self.cb_trial.setToolTip("Trial to threshold. Left / Right arrow keys "
                                 "advance through the filtered list.")
        self.btn_prev = QtWidgets.QPushButton("◀ Prev")
        self.btn_next = QtWidgets.QPushButton("Next ▶")
        for lab, wid in [("IR status:", self.cb_light), ("Date:", self.cb_date),
                         ("End loc:", self.cb_endloc)]:
            h.addWidget(QtWidgets.QLabel(lab)); h.addWidget(wid)
        h.addWidget(self._vline())
        h.addWidget(QtWidgets.QLabel("Trial:")); h.addWidget(self.cb_trial, 1)
        h.addWidget(self.btn_prev); h.addWidget(self.btn_next)
        return w

    def _build_row2(self):
        w = QtWidgets.QWidget(); h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QtWidgets.QLabel("Signal:"))
        self.rb_deconv = QtWidgets.QRadioButton("Deconvolved")
        self.rb_raw = QtWidgets.QRadioButton("Raw")
        self.rb_deconv.setChecked(True)
        grp = QtWidgets.QButtonGroup(self)
        grp.addButton(self.rb_deconv); grp.addButton(self.rb_raw)
        h.addWidget(self.rb_deconv); h.addWidget(self.rb_raw)
        h.addWidget(self._vline())
        self.cb_baseline = QtWidgets.QCheckBox("Baseline subtract")
        self.cb_baseline.setChecked(C.BASELINE_ON_DEFAULT)
        self.cb_baseline.setToolTip("Subtract a rolling low-percentile baseline "
                                    "before thresholding.")
        h.addWidget(self.cb_baseline)
        h.addWidget(QtWidgets.QLabel("pct:"))
        self.sp_bpct = self._dspin(0.0, 100.0, 1.0, C.BASELINE_PCT, 0, 56)
        h.addWidget(self.sp_bpct)
        h.addWidget(QtWidgets.QLabel("win(s):"))
        self.sp_bwin = self._dspin(0.5, 600.0, 1.0, C.BASELINE_WIN_S, 1, 64)
        h.addWidget(self.sp_bwin)
        h.addWidget(self._vline())
        h.addWidget(QtWidgets.QLabel("Min dur (s):"))
        self.sp_mindur = self._dspin(0.0, 10.0, 0.01, C.MIN_DURATION_S, 3, 72)
        h.addWidget(self.sp_mindur)
        h.addStretch(1)
        return w

    def _build_row3(self):
        w = QtWidgets.QWidget(); h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QtWidgets.QLabel("Threshold:"))
        self.sp_thr = self._dspin(-1e6, 1e6, 0.001, 0.0, 6, 110)
        self.sp_thr.setToolTip("Threshold in baseline-subtracted signal units. "
                               "Drag the red line or type a value.")
        h.addWidget(self.sp_thr)
        self.btn_auto = QtWidgets.QPushButton("Auto")
        self.btn_auto.setToolTip("Seed threshold = median + k*MAD on this trace.")
        h.addWidget(self.btn_auto)
        h.addWidget(self._vline())
        self.lbl_contacts = QtWidgets.QLabel("Contacts: -")
        self.lbl_contacts.setStyleSheet("font-weight:600;")
        h.addWidget(self.lbl_contacts)
        h.addWidget(self._vline())
        self.btn_save = QtWidgets.QPushButton("Save (Enter)")
        self.btn_save.setStyleSheet("font-weight:600;")
        h.addWidget(self.btn_save)
        self.lbl_saved = QtWidgets.QLabel("not saved")
        self.lbl_saved.setStyleSheet("color:#888;")
        h.addWidget(self.lbl_saved)
        h.addStretch(1)
        return w

    @staticmethod
    def _dspin(lo, hi, step, val, dec, width=72):
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(lo, hi); s.setSingleStep(step); s.setDecimals(dec)
        s.setValue(val); s.setMaximumWidth(width)
        s.setKeyboardTracking(False)
        return s

    @staticmethod
    def _vline():
        ln = QtWidgets.QFrame()
        ln.setFrameShape(QtWidgets.QFrame.VLine)
        ln.setFrameShadow(QtWidgets.QFrame.Sunken)
        return ln

    # ================================================================ wiring
    def _wire(self):
        self.cb_light.currentIndexChanged.connect(self._on_lighting_changed)
        self.cb_date.currentIndexChanged.connect(self._on_date_changed)
        self.cb_endloc.currentIndexChanged.connect(self._on_endloc_changed)
        self.cb_trial.currentIndexChanged.connect(self._on_trial_selected)
        self.btn_prev.clicked.connect(lambda: self._advance(-1))
        self.btn_next.clicked.connect(lambda: self._advance(+1))
        self.rb_deconv.toggled.connect(self._on_signal_changed)
        self.cb_baseline.stateChanged.connect(self._reload_trial)
        self.sp_bpct.valueChanged.connect(self._reload_trial)
        self.sp_bwin.valueChanged.connect(self._reload_trial)
        self.sp_mindur.valueChanged.connect(self._redraw)
        self.sp_thr.valueChanged.connect(self._redraw)
        self.btn_auto.clicked.connect(self._on_auto)
        self.btn_save.clicked.connect(self._on_save)

    def _install_shortcuts(self):
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), self,
                        activated=lambda: self._advance(-1))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right), self,
                        activated=lambda: self._advance(+1))
        for key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            QtGui.QShortcut(QtGui.QKeySequence(key), self, activated=self._on_save)

    def _populate_lightings(self):
        self.cb_light.blockSignals(True)
        self.cb_light.clear()
        for lt in self.store.lightings():
            self.cb_light.addItem(lt, lt)
        self.cb_light.addItem("All", C.LIGHTING_ALL)
        self.cb_light.setCurrentIndex(0)
        self.cb_light.blockSignals(False)

    # ================================================================ slots
    def _on_lighting_changed(self, *a):
        if self._loading:
            return
        self._loading = True
        lt = self.cb_light.currentData()
        self.cb_date.clear()
        self.cb_date.addItem("All dates", C.LIGHTING_ALL)
        for d in self.store.dates(lt):
            self.cb_date.addItem(d, d)
        self.cb_date.setCurrentIndex(0)
        self._loading = False
        self._on_date_changed()

    def _on_date_changed(self, *a):
        if self._loading:
            return
        self._loading = True
        lt = self.cb_light.currentData()
        date = self.cb_date.currentData()
        self.cb_endloc.blockSignals(True)
        self.cb_endloc.clear()
        self.cb_endloc.addItem("All locations", C.LIGHTING_ALL)
        for loc in self.store.end_locations(lt, date):
            self.cb_endloc.addItem(f"Loc {loc}" if loc >= 0 else "Loc ?", loc)
        self.cb_endloc.setCurrentIndex(0)
        self.cb_endloc.blockSignals(False)
        self._loading = False
        self._on_endloc_changed()

    def _on_endloc_changed(self, *a):
        if self._loading:
            return
        self._rebuild_order()

    def _rebuild_order(self):
        lt = self.cb_light.currentData()
        date = self.cb_date.currentData()
        loc = self.cb_endloc.currentData()
        self._order = self.store.trials_for(lt, date, loc)
        self._loading = True
        self.cb_trial.clear()
        for r in self._order:
            mark = " ✓" if self.jstore.has(r.file_name) else ""
            self.cb_trial.addItem(f"{r.label}  {r.file_name}{mark}", r.index)
        self._loading = False
        if self._order:
            self._pos = 0
            self.cb_trial.setCurrentIndex(0)
            self._load_pos()
        else:
            self._pos = -1
            self._ts = None
            self.view._render_blank("no trials for this filter")
            self.lbl_contacts.setText("Contacts: -")
            self.lbl_saved.setText("not saved")

    def _on_trial_selected(self, *a):
        if self._loading:
            return
        i = self.cb_trial.currentIndex()
        if 0 <= i < len(self._order):
            self._pos = i
            self._load_pos()

    def _advance(self, step):
        if not self._order:
            return
        self._pos = int(np.clip(self._pos + step, 0, len(self._order) - 1))
        self._loading = True
        self.cb_trial.setCurrentIndex(self._pos)
        self._loading = False
        self._load_pos()

    def _on_signal_changed(self, *a):
        if self._loading:
            return
        self._reload_trial()

    # ================================================================ helpers
    def _signal(self):
        return C.SIGNAL_DECONV if self.rb_deconv.isChecked() else C.SIGNAL_RAW

    def _baseline_kw(self):
        return dict(baseline_on=self.cb_baseline.isChecked(),
                    baseline_pct=self.sp_bpct.value(),
                    baseline_win_s=self.sp_bwin.value())

    def _load_pos(self):
        """Prepare the current trial's signal and seed the threshold."""
        if not (0 <= self._pos < len(self._order)):
            return
        rec = self._order[self._pos]
        try:
            ts = self.store.trial_signal(rec.index, signal=self._signal(),
                                         **self._baseline_kw())
        except Exception as ex:
            self.status.showMessage(f"error loading trial: {ex}")
            return
        self._ts = ts
        # seed the threshold: saved JSON value (same signal) else auto-estimate
        seed = None
        entry = self.jstore.get(rec.file_name)
        if entry is not None and entry.get("signal") == ts.signal:
            try:
                seed = float(entry.get("threshold"))
            except (TypeError, ValueError):
                seed = None
        if seed is None:
            seed = D.auto_threshold(ts.sig)
        self._loading = True
        self.sp_thr.setValue(float(seed))
        self._loading = False
        self._update_saved_indicator(rec)
        self._redraw()

    def _reload_trial(self, *a):
        if self._loading or self._ts is None:
            return
        self._load_pos()

    def _on_auto(self, *a):
        if self._ts is None:
            return
        self.sp_thr.setValue(float(D.auto_threshold(self._ts.sig)))

    def _on_line_drag(self, value):
        self.sp_thr.setValue(float(value))       # triggers _redraw via valueChanged

    def _update_saved_indicator(self, rec):
        entry = self.jstore.get(rec.file_name)
        if entry is None:
            self.lbl_saved.setText("not saved")
            self.lbl_saved.setStyleSheet("color:#888;")
        else:
            self.lbl_saved.setText(
                f"saved ✓ thr={entry.get('threshold'):.4g} "
                f"({entry.get('signal')}) @ {entry.get('set_local','?')}")
            self.lbl_saved.setStyleSheet("color:#0a8a0a;")

    # ================================================================ redraw
    def _redraw(self, *a):
        if self._loading or self._ts is None:
            return
        thr = self.sp_thr.value()
        mindur = self.sp_mindur.value()
        contacts = self._ts.contacts(thr, mindur)
        handles = self.view.show_trial(self._ts, thr, mindur, contacts=contacts)
        self._last_handles = handles
        ds = handles["dist_summary"]
        if ds["n"]:
            self.lbl_contacts.setText(
                f"Contacts: {len(contacts)}  |  dist px: "
                f"{ds['min']:.0f}/{ds['mean']:.0f}/{ds['max']:.0f} (min/mean/max)")
        else:
            self.lbl_contacts.setText(f"Contacts: {len(contacts)}  |  dist px: n/a")
        self.status.showMessage(
            f"trial {self._pos + 1}/{len(self._order)}  |  {self._ts.rec.file_name}"
            f"  |  signal: {self._ts.signal}  |  saved trials: {self.jstore.count()}")

    # ================================================================ save
    def _on_save(self, *a):
        if self._ts is None:
            self.status.showMessage("nothing to save")
            return
        ts = self._ts
        thr = float(self.sp_thr.value())
        mindur = float(self.sp_mindur.value())
        contacts = ts.contacts(thr, mindur)
        dists = ts.contact_distances(contacts)
        rec = ts.rec
        units = ("ethdeconv" if ts.signal == C.SIGNAL_DECONV else "ethanol") + \
                ("_baseline_subtracted" if ts.baseline_on else "_raw")
        entry = {
            "file_name": rec.file_name,
            "trial_index": int(rec.index),
            "loc": int(rec.loc_no),
            "animal": int(rec.animal),
            "date": rec.date,
            "lighting": rec.lighting,
            "signal": ts.signal,
            "baseline_subtracted": bool(ts.baseline_on),
            "baseline": ts.baseline_params,
            "threshold": thr,
            "threshold_units": units,
            "min_duration_s": mindur,
            "n_contacts": int(len(contacts)),
            "contact_onsets_s": [round(float(c["t_onset"]), 4) for c in contacts],
            "contact_distances_px": [None if not np.isfinite(d) else round(float(d), 2)
                                     for d in dists],
            "endpoint_px": ([float(ts.endpoint[0]), float(ts.endpoint[1])]
                            if ts.endpoint is not None else None),
        }
        try:
            _, local_str = self.jstore.set_trial(entry)
        except Exception as ex:
            self.status.showMessage(f"SAVE FAILED: {ex}")
            return
        # refresh the check-mark in the combo + saved indicator
        self._loading = True
        cur = self.cb_trial.currentIndex()
        self.cb_trial.setItemText(cur, f"{rec.label}  {rec.file_name} ✓")
        self._loading = False
        self._update_saved_indicator(rec)
        self.status.showMessage(
            f"saved {rec.file_name}: thr={thr:.4g}, {len(contacts)} contacts  ->  "
            f"{C.output_json_path()}  (+ DATA mirror)  @ {local_str}")

    def closeEvent(self, ev):
        self.store.close()
        super().closeEvent(ev)
