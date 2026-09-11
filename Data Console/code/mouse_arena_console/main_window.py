#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_window.py -- the Mouse Arena Data Console main window.

Top control bar (all controls along the top, mirroring the Rat Arena console):

  row 1 : [IR status v] [Date v] | Trials: (All)(#0 T..)(...)
  row 2 : Signal: (o) Deconvolved (o) Raw   |  Seconds: [start]-[end]
  row 3 : Contacts [x]  Alpha[ ] Min[ ] Max[ ] | α<thr→0 [x] [thr]
          [Refresh] [Save image…]                 Trial length: <indicator>

Below the bar: the arena view (background + head trajectory + ethanol-contact
dots) and, beneath it, the ethanol time series with the threshold line.
"""
from __future__ import annotations

import os

import numpy as np
from PySide6 import QtCore, QtWidgets

from . import arena_config as C
from .data import DataStore
from .arena_view import ArenaView


def _sanitize(name):
    """Make a string safe for a Windows filename (illegal chars / spaces -> _)."""
    out = []
    for ch in str(name):
        if ch in '<>:"/\\|?*' or ch.isspace():
            out.append("_")
        else:
            out.append(ch)
    s = "".join(out).strip("_")
    return s or "mouse_arena"


def _load_background(path):
    if not path:
        return None
    try:
        from PIL import Image
        im = Image.open(path)
        if im.mode not in ("L", "I", "F"):
            im = im.convert("L")
        return np.asarray(im)
    except Exception:
        try:
            import matplotlib.image as mpimg
            return mpimg.imread(path)
        except Exception:
            return None


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, agg_path):
        super().__init__()
        self.setWindowTitle("Mouse Arena Data Console")
        self.resize(1160, 900)
        self.store = DataStore(agg_path)
        self._loading = True
        self._trial_boxes = {}          # trial index -> QCheckBox

        bar = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(bar)
        v.setContentsMargins(8, 6, 8, 4)
        v.setSpacing(4)
        v.addWidget(self._build_row1())
        v.addWidget(self._build_row2())
        v.addWidget(self._build_row3())

        self.view = ArenaView()
        bg = _load_background(C.resolve_background())
        self.view.set_background(bg, self.store.extent)
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
        self._loading = False
        self._on_lighting_changed()

    # ================================================================ build
    def _build_row1(self):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)

        self.cb_light = QtWidgets.QComboBox()
        self.cb_light.setMinimumWidth(120)
        self.cb_date = QtWidgets.QComboBox()
        self.cb_date.setMinimumWidth(130)
        self.cb_endloc = QtWidgets.QComboBox()
        self.cb_endloc.setMinimumWidth(120)
        self.cb_endloc.setToolTip(
            "Target odor-port (end) location. Pick one and only the trials/animals "
            "that ran to that location become selectable.")

        # dynamic trial checkbox strip
        self.trial_container = QtWidgets.QWidget()
        self.trial_layout = QtWidgets.QHBoxLayout(self.trial_container)
        self.trial_layout.setContentsMargins(0, 0, 0, 0)
        self.trial_layout.setSpacing(6)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.trial_container)
        scroll.setFixedHeight(34)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.trial_scroll = scroll

        for lab, wid in [("IR status:", self.cb_light), ("Date:", self.cb_date),
                         ("End loc:", self.cb_endloc)]:
            h.addWidget(QtWidgets.QLabel(lab)); h.addWidget(wid)
        h.addWidget(self._vline())
        h.addWidget(QtWidgets.QLabel("Trials:"))
        h.addWidget(scroll, 1)
        return w

    def _build_row2(self):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QtWidgets.QLabel("Signal:"))
        self.rb_deconv = QtWidgets.QRadioButton("Deconvolved")
        self.rb_raw = QtWidgets.QRadioButton("Raw")
        self.rb_deconv.setChecked(True)
        grp = QtWidgets.QButtonGroup(self)
        grp.addButton(self.rb_deconv); grp.addButton(self.rb_raw)
        h.addWidget(self.rb_deconv); h.addWidget(self.rb_raw)

        h.addWidget(self._vline())
        h.addWidget(QtWidgets.QLabel("Seconds:"))
        self.sp_t0 = self._dspin(0.0, 3600.0, 0.5, 0.0, 2)
        self.sp_t1 = self._dspin(0.0, 3600.0, 0.5, 0.0, 2)
        self.sp_t1.setToolTip("End second (0 = to end of trial)")
        h.addWidget(self.sp_t0); h.addWidget(QtWidgets.QLabel("to")); h.addWidget(self.sp_t1)
        h.addStretch(1)
        return w

    def _build_row3(self):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)

        self.cb_contacts = QtWidgets.QCheckBox("Ethanol contacts")
        self.cb_contacts.setChecked(C.DEFAULT_CONTACTS_ON)
        self.cb_contacts.setToolTip("Overlay ethanol-contact dots on the head "
                                    "trajectory, coloured by plume concentration (jet).")
        h.addWidget(self.cb_contacts)

        h.addWidget(QtWidgets.QLabel("Alpha:"))
        self.sp_alpha = self._dspin(0.0, 1.0, 0.05, C.DEFAULT_ALPHA, 3)
        h.addWidget(self.sp_alpha)
        h.addWidget(QtWidgets.QLabel("Min:"))
        self.sp_vmin = self._dspin(0.0, 1.0, 0.05, C.DEFAULT_VMIN, 3)
        h.addWidget(self.sp_vmin)
        h.addWidget(QtWidgets.QLabel("Max:"))
        self.sp_vmax = self._dspin(0.0, 1.0, 0.05, C.DEFAULT_VMAX, 3)
        h.addWidget(self.sp_vmax)

        h.addWidget(self._vline())
        self.cb_thr = QtWidgets.QCheckBox("α<thr→0")
        self.cb_thr.setChecked(C.DEFAULT_ALPHA_THRESH_ON)
        self.cb_thr.setToolTip("Concentration below the threshold is drawn fully "
                               "transparent; the threshold is the dashed red line "
                               "on the time series.")
        h.addWidget(self.cb_thr)
        self.sp_thr = self._dspin(0.0, 1.0, 0.05, C.DEFAULT_ALPHA_THRESH, 3)
        h.addWidget(self.sp_thr)

        h.addWidget(self._vline())
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        h.addWidget(self.btn_refresh)
        self.btn_save = QtWidgets.QPushButton("Save image…")
        h.addWidget(self.btn_save)
        h.addStretch(1)
        self.lbl_len = QtWidgets.QLabel("Trial length: -")
        self.lbl_len.setStyleSheet("font-weight:600;")
        h.addWidget(self.lbl_len)
        return w

    @staticmethod
    def _dspin(lo, hi, step, val, dec):
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(lo, hi); s.setSingleStep(step); s.setDecimals(dec)
        s.setValue(val); s.setMaximumWidth(72)
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
        self.rb_deconv.toggled.connect(self._refresh)
        for wdg in (self.sp_t0, self.sp_t1, self.sp_alpha, self.sp_vmin,
                    self.sp_vmax, self.sp_thr):
            wdg.valueChanged.connect(self._refresh)
        self.cb_thr.stateChanged.connect(self._refresh)
        self.cb_contacts.stateChanged.connect(self._refresh)
        self.btn_refresh.clicked.connect(self._refresh)
        self.btn_save.clicked.connect(self._on_save)

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
        self._populate_endloc()
        self._loading = False
        self._on_endloc_changed()

    def _populate_endloc(self):
        lt = self.cb_light.currentData()
        date = self.cb_date.currentData()
        self.cb_endloc.blockSignals(True)
        self.cb_endloc.clear()
        self.cb_endloc.addItem("All locations", C.LIGHTING_ALL)
        for loc in self.store.end_locations(lt, date):
            self.cb_endloc.addItem(f"Loc {loc}" if loc >= 0 else "Loc ?", loc)
        self.cb_endloc.setCurrentIndex(0)
        self.cb_endloc.blockSignals(False)

    def _on_endloc_changed(self, *a):
        if self._loading:
            return
        self._loading = True
        self._rebuild_trials()
        self._loading = False
        self._refresh()

    def _rebuild_trials(self):
        while self.trial_layout.count():
            it = self.trial_layout.takeAt(0)
            wdg = it.widget()
            if wdg is not None:
                wdg.deleteLater()
        self._trial_boxes = {}
        self.cb_trial_all = QtWidgets.QCheckBox("All")
        self.cb_trial_all.setChecked(True)
        self.cb_trial_all.stateChanged.connect(self._on_trial_all)
        self.trial_layout.addWidget(self.cb_trial_all)

        lt = self.cb_light.currentData()
        date = self.cb_date.currentData()
        loc = self.cb_endloc.currentData()
        recs = self.store.trials_for(lt, date, loc)
        if len(recs) <= C.MAX_TRIAL_CHECKBOXES:
            for r in recs:
                cbx = QtWidgets.QCheckBox(r.label)
                cbx.setToolTip(r.file_name)
                cbx.stateChanged.connect(self._on_trial_toggle)
                self._trial_boxes[r.index] = cbx
                self.trial_layout.addWidget(cbx)
        else:
            note = QtWidgets.QLabel(f"({len(recs)} trials — 'All' only)")
            note.setStyleSheet("color:#888;")
            self.trial_layout.addWidget(note)
        self.trial_layout.addStretch(1)

    def _on_trial_all(self, *a):
        if self._loading:
            return
        if self.cb_trial_all.isChecked():
            self._loading = True
            for cbx in self._trial_boxes.values():
                cbx.setChecked(False)
            self._loading = False
        self._refresh()

    def _on_trial_toggle(self, *a):
        if self._loading:
            return
        if any(c.isChecked() for c in self._trial_boxes.values()):
            self._loading = True
            self.cb_trial_all.setChecked(False)
            self._loading = False
        self._refresh()

    # ================================================================ helpers
    def _selected_trials(self):
        if getattr(self, "cb_trial_all", None) is None or self.cb_trial_all.isChecked():
            return []                          # empty -> all in the current filter
        return [i for i, c in self._trial_boxes.items() if c.isChecked()]

    def _signal(self):
        return C.SIGNAL_DECONV if self.rb_deconv.isChecked() else C.SIGNAL_RAW

    def _on_line_drag(self, kind, value):
        """A reference line on the time series was dragged -> set that control.
        Setting the spin box triggers a single _refresh via valueChanged."""
        v = float(value)
        if kind == "thr":
            # applying the cutoff makes the drag visible on the dots
            self.cb_thr.blockSignals(True)
            self.cb_thr.setChecked(True)
            self.cb_thr.blockSignals(False)
            self.sp_thr.setValue(v)
        elif kind == "vmax":
            self.sp_vmax.setValue(max(v, self.sp_vmin.value()))
        elif kind == "vmin":
            self.sp_vmin.setValue(min(v, self.sp_vmax.value()))

    # ================================================================ refresh
    def _refresh(self, *a):
        if self._loading:
            return
        lt = self.cb_light.currentData()
        date = self.cb_date.currentData()
        loc = self.cb_endloc.currentData()
        seconds = (self.sp_t0.value(), self.sp_t1.value())
        signal = self._signal()
        try:
            sel = self.store.collect(lt, date, self._selected_trials(),
                                     seconds=seconds, signal=signal, end_loc=loc)
        except Exception as ex:
            self.status.showMessage(f"error: {ex}")
            return

        self._last_sel = sel
        ltxt = "all IR" if lt == C.LIGHTING_ALL else str(lt)
        dtxt = "all dates" if date in (C.LIGHTING_ALL, None) else str(date)
        loctxt = "all locations" if loc in (C.LIGHTING_ALL, None) else f"Loc {loc}"
        # caption shows exactly which data is on screen: trial name (if one),
        # IR status, and end (odor-port) location.
        if sel.n_trials == 1:
            tname = sel.trials[0].file_name or sel.trials[0].label
            title = f"{tname}   |   IR: {ltxt}   |   end: {loctxt}   |   {dtxt}"
        else:
            title = (f"{sel.n_trials} trials   |   IR: {ltxt}   |   "
                     f"end: {loctxt}   |   {dtxt}")
        self.view.show_selection(
            sel, alpha=self.sp_alpha.value(), vmin=self.sp_vmin.value(),
            vmax=self.sp_vmax.value(), contacts_on=self.cb_contacts.isChecked(),
            thr_on=self.cb_thr.isChecked(), thr=self.sp_thr.value(),
            title=title, signal_label=("deconvolved" if signal == C.SIGNAL_DECONV else "raw"))
        self._update_length(sel)
        self.status.showMessage(
            f"{sel.n_trials} trial(s)  |  signal: {signal}  |  "
            f"norm peak: {sel.pooled_max:.3g}")

    def _update_length(self, sel):
        L = np.asarray(sel.lengths_s, dtype=float)
        L = L[np.isfinite(L) & (L > 0)]
        if L.size == 0:
            self.lbl_len.setText("Trial length: n/a")
        elif L.size == 1:
            self.lbl_len.setText(f"Trial length: {L[0]:.2f} s")
        else:
            self.lbl_len.setText(
                f"Trial length (n={L.size}): min {L.min():.2f} / "
                f"mean {L.mean():.2f} / max {L.max():.2f} s")

    # ================================================================ export
    def _on_save(self):
        base = os.path.dirname(self.store.path) or os.getcwd()
        lt = self.cb_light.currentData()
        date = self.cb_date.currentData()
        loc = self.cb_endloc.currentData()
        ltxt = "allIR" if lt == C.LIGHTING_ALL else str(lt)
        dtxt = "allDates" if date in (C.LIGHTING_ALL, None) else str(date)
        loctxt = "allLocs" if loc in (C.LIGHTING_ALL, None) else f"Loc{loc}"
        # name the file after the actual data shown: the trial's own recording
        # name when a single trial is selected, else an N-trials summary.
        sel = getattr(self, "_last_sel", None)
        trials = sel.trials if sel else []
        if len(trials) == 1:
            data_name = os.path.splitext(trials[0].file_name)[0] or trials[0].label
        elif len(trials) > 1:
            data_name = f"{len(trials)}trials"
        else:
            data_name = "nodata"
        name = _sanitize(
            f"mouse_arena_{ltxt}_{dtxt}_{loctxt}_{data_name}_{self._signal()}.png")
        default = os.path.join(base, name)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save current view", default,
            "PNG image (*.png);;PDF document (*.pdf);;SVG image (*.svg);;"
            "TIFF image (*.tif *.tiff)")
        if not path:
            return
        try:
            self.view.save(path)
        except Exception as ex:
            self.status.showMessage(f"save failed: {ex}")
            return
        self.status.showMessage(f"saved: {path}")

    def closeEvent(self, ev):
        self.store.close()
        super().closeEvent(ev)
