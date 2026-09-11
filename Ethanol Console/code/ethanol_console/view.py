#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
view.py -- the Ethanol Console canvas.

Three linked panels:

  * LEFT  -- the trial's x,y **trajectory map** (arena pixel frame, y downward):
    faint head track + red dots at odor-contact onsets + red circle at the target
    odor port (endpoint). Title shows the contact count.
  * TOP-RIGHT -- a **binary preview**: odor ON/OFF along time at the current
    threshold (a green band where a qualifying contact episode is active).
  * BOTTOM-RIGHT -- the **thresholding trace**: the baseline-subtracted ethanol
    signal with the draggable red threshold line; qualifying episodes shaded.

The preview shares the trace's time axis, so box-zoom / pan on the trace zooms the
preview too. The drawing lives in the module-level ``render(...)`` so it works
with a plain matplotlib Figure (tests / export) as well as the Qt canvas.
"""
from __future__ import annotations

import numpy as np
import matplotlib.patches as mp
from matplotlib.gridspec import GridSpec

from . import console_config as C
from . import data as D


def _img_ylim(ax, extent):
    x0, x1, y0, y1 = extent
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)                # y downward (image convention)


def render(fig, ts, thr, min_duration_s=C.MIN_DURATION_S, contacts=None):
    """Draw a data.TrialSignal ``ts`` at threshold ``thr`` onto ``fig``.

    Returns handles incl the threshold Line2D and the trace Axes for dragging,
    and the computed contact summary.
    """
    fig.clear()
    gs = GridSpec(2, 2, width_ratios=[1.0, 1.32], height_ratios=[1.0, 3.0],
                  hspace=0.16, wspace=0.14, figure=fig)
    ax_map = fig.add_subplot(gs[:, 0])
    ax_prev = fig.add_subplot(gs[0, 1])
    ax_trace = fig.add_subplot(gs[1, 1], sharex=ax_prev)

    if contacts is None:
        contacts = ts.contacts(thr, min_duration_s) if ts is not None else []
    P, valid = (ts.contact_positions(contacts) if ts is not None
                else (np.zeros((0, 2)), np.zeros(0, bool)))
    dists = ts.contact_distances(contacts) if ts is not None else np.zeros(0)
    dsum = D.distance_summary(dists)

    # ---------------- trajectory map ----------------
    extent = ts.extent if ts is not None else C.ARENA_EXTENT_PX
    x0, x1, y0, y1 = extent
    ax_map.add_patch(mp.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                  facecolor="#101317", edgecolor="#444", lw=1.0, zorder=0))
    _img_ylim(ax_map, extent)
    ax_map.set_xticks([]); ax_map.set_yticks([])
    if ts is not None and ts.head_x.size:
        fin = np.isfinite(ts.head_x) & np.isfinite(ts.head_y)
        ax_map.plot(ts.head_x[fin], ts.head_y[fin], color=C.TRAJ_LINE_COLOR,
                    lw=C.TRAJ_LINE_LW, alpha=C.TRAJ_LINE_ALPHA, zorder=2,
                    solid_capstyle="round")
    if P.shape[0] and valid.any():
        ax_map.scatter(P[valid, 0], P[valid, 1], s=C.CONTACT_SIZE,
                       facecolors=C.CONTACT_COLOR, edgecolors="white",
                       linewidths=0.4, zorder=4, label="contacts")
    if ts is not None and ts.endpoint is not None and np.all(np.isfinite(ts.endpoint)):
        ax_map.scatter([ts.endpoint[0]], [ts.endpoint[1]], s=C.PORT_SIZE,
                       facecolors="none", edgecolors=C.PORT_COLOR,
                       linewidths=C.PORT_LW, zorder=5)
        ax_map.scatter([ts.endpoint[0]], [ts.endpoint[1]], s=14,
                       c=C.PORT_COLOR, zorder=5)
    ncon = len(contacts)
    ax_map.set_title(f"trajectory + contacts  (n={ncon})", fontsize=9)

    # ---------------- binary preview ----------------
    if ts is not None and ts.t.size:
        on = ts.on_mask(thr, min_duration_s).astype(float)
        ax_prev.fill_between(ts.t, 0.0, on, step="mid", color=C.ON_BAND_COLOR,
                             alpha=0.9, linewidth=0)
        ax_prev.set_xlim(ts.t[0], ts.t[-1])
    ax_prev.set_ylim(-0.05, 1.1)
    ax_prev.set_yticks([0, 1]); ax_prev.set_yticklabels(["off", "on"], fontsize=7)
    ax_prev.tick_params(labelbottom=False, labelsize=7)
    ax_prev.set_title("odor on / off at threshold", fontsize=9)
    ax_prev.grid(True, axis="x", alpha=0.15)

    # ---------------- thresholding trace ----------------
    l_thr = None
    if ts is not None and ts.t.size:
        ax_trace.plot(ts.t, ts.sig, color=C.TRACE_COLOR, lw=0.8, alpha=0.9,
                      label=("deconv" if ts.signal == C.SIGNAL_DECONV else "raw")
                      + (" - baseline" if ts.baseline_on else ""))
        # shade qualifying episodes
        for ep in contacts:
            ax_trace.axvspan(ep["t_onset"], ep["t_offset"], color=C.EPISODE_SHADE,
                             alpha=C.EPISODE_SHADE_ALPHA, lw=0, zorder=1)
        # onset ticks
        for ep in contacts:
            ax_trace.axvline(ep["t_onset"], color=C.ONSET_TICK_COLOR, lw=0.6,
                             alpha=0.5, zorder=2)
        l_thr = ax_trace.axhline(thr, color=C.THR_LINE_COLOR, ls="--", lw=1.3,
                                 zorder=6, label=f"threshold = {thr:.4g}")
        ax_trace.set_xlim(ts.t[0], ts.t[-1])
    ax_trace.set_xlabel("time (s, shared origin)", fontsize=8)
    ax_trace.set_ylabel("ethanol (baseline-sub)", fontsize=8)
    ax_trace.tick_params(labelsize=7)
    ax_trace.grid(True, alpha=0.15)
    ax_trace.legend(loc="upper right", fontsize=7, framealpha=0.85)

    fig.subplots_adjust(left=0.04, right=0.985, top=0.93, bottom=0.09)
    return {"fig": fig, "ax_map": ax_map, "ax_prev": ax_prev, "ax_trace": ax_trace,
            "thr_line": l_thr, "contacts": contacts, "distances": dists,
            "dist_summary": dsum}


# ---------------------------------------------------------------------------
# Qt wrapper (imported only when the GUI runs)
# ---------------------------------------------------------------------------
try:
    from PySide6 import QtCore, QtWidgets
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    try:
        from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
    except Exception:                                    # older/newer layout
        from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavToolbar
    from matplotlib.figure import Figure
    _HAVE_QT = True
except Exception:  # pragma: no cover
    _HAVE_QT = False


if _HAVE_QT:
    _DRAG_TOL_PX = 8

    class EthanolView(QtWidgets.QWidget):
        """Canvas + matplotlib navigation toolbar (box-zoom / pan / home) with a
        draggable threshold line on the trace panel."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.fig = Figure(figsize=(9.2, 5.4))
            self.canvas = FigureCanvas(self.fig)
            self.toolbar = NavToolbar(self.canvas, self)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            lay.addWidget(self.toolbar)
            lay.addWidget(self.canvas)

            self._thr_cb = None
            self._ax_trace = None
            self._thr_line = None
            self._thr_val = 0.0
            self._drag = False
            self.canvas.mpl_connect("button_press_event", self._on_press)
            self.canvas.mpl_connect("motion_notify_event", self._on_motion)
            self.canvas.mpl_connect("button_release_event", self._on_release)
            self._render_blank()

        def set_threshold_callback(self, fn):
            """fn(value) is called on release of the threshold line."""
            self._thr_cb = fn

        # -- interactive drag of the threshold line -----------------------
        def _toolbar_active(self):
            # matplotlib sets .mode to "zoom rect"/"pan/zoom" (or an enum) when a
            # nav tool is selected; treat any non-empty mode as active.
            m = getattr(self.toolbar, "mode", "")
            return bool(str(m))

        def _near_thr(self, event):
            if (self._ax_trace is None or self._thr_line is None
                    or event.inaxes is not self._ax_trace or event.y is None):
                return False
            y = self._thr_line.get_ydata()[0]
            _, py = self._ax_trace.transData.transform((event.xdata or 0.0, y))
            return abs(py - event.y) <= _DRAG_TOL_PX

        def _on_press(self, event):
            if event.button == 1 and not self._toolbar_active() and self._near_thr(event):
                self._drag = True

        def _on_motion(self, event):
            if not self._drag:
                if not self._toolbar_active() and self._near_thr(event):
                    self.canvas.setCursor(QtCore.Qt.SizeVerCursor)
                else:
                    self.canvas.setCursor(QtCore.Qt.ArrowCursor)
                return
            if event.inaxes is not self._ax_trace or event.ydata is None:
                return
            self._thr_val = float(event.ydata)
            self._thr_line.set_ydata([self._thr_val, self._thr_val])
            self.canvas.draw_idle()

        def _on_release(self, event):
            if not self._drag:
                return
            self._drag = False
            if self._thr_cb:
                self._thr_cb(round(float(self._thr_val), 6))

        def _render_blank(self, title="Mouse Arena Ethanol Console"):
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            ax.set_xticks([]); ax.set_yticks([])
            ax.text(0.5, 0.5, "select a trial", transform=ax.transAxes,
                    ha="center", va="center", color="#888", fontsize=11)
            ax.set_title(title, fontsize=10)
            self.canvas.draw_idle()

        def show_trial(self, ts, thr, min_duration_s=C.MIN_DURATION_S, contacts=None):
            handles = render(self.fig, ts, thr, min_duration_s, contacts=contacts)
            self._ax_trace = handles.get("ax_trace")
            self._thr_line = handles.get("thr_line")
            self._thr_val = float(thr)
            self.canvas.draw_idle()
            return handles

        def save(self, path, dpi=200):
            ext = str(path).lower().rsplit(".", 1)[-1] if "." in str(path) else "png"
            kw = dict(bbox_inches="tight", facecolor="white")
            if ext not in ("pdf", "svg"):
                kw["dpi"] = dpi
            self.fig.savefig(path, **kw)
