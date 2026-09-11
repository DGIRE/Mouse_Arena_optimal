#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arena_view.py -- the central canvas: the arena (top) plus an ethanol time
series (bottom).

Top panel: the arena background (an image if one is present in ``assets/``,
otherwise a neutral panel) in the tracking-pixel frame (x rightward, y downward).
On it: each selected trial's HEAD trajectory as a faint line, overlaid with
ethanol-contact dots coloured by normalised plume concentration (jet), plus a red
circle at the trial's target odor port (reward endpoint).

Bottom panel: the ethanol sensor time series for the selected trial(s), with the
alpha threshold drawn as a dashed red line.

The actual drawing lives in the module-level ``render(fig, sel, ...)`` so it can
be used both by the Qt canvas here and by a plain matplotlib Figure in tests /
image export (no Qt required).
"""
from __future__ import annotations

import numpy as np
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.patches as mp
from matplotlib.gridspec import GridSpec

from . import arena_config as C


def _cmap(name):
    try:
        from matplotlib import colormaps
        return colormaps[name]
    except Exception:
        return cm.get_cmap(name)


def _img_extent(ext):
    """(x0,x1,y0,y1) -> matplotlib (left,right,bottom,top) with y inverted
    (image convention: small y at the top)."""
    x0, x1, y0, y1 = ext
    return (x0, x1, y1, y0)


def render(fig, sel, bg=None, extent=C.ARENA_EXTENT_PX, alpha=C.DEFAULT_ALPHA,
           vmin=C.DEFAULT_VMIN, vmax=C.DEFAULT_VMAX, contacts_on=True,
           thr_on=C.DEFAULT_ALPHA_THRESH_ON, thr=C.DEFAULT_ALPHA_THRESH,
           title="", signal_label="deconvolved"):
    """Draw a data.Selection onto ``fig`` (cleared first). Pure matplotlib."""
    fig.clear()
    gs = GridSpec(2, 1, height_ratios=[3.0, 1.0], hspace=0.28, figure=fig)
    ax = fig.add_subplot(gs[0])
    axt = fig.add_subplot(gs[1])

    # ---------- arena panel ----------
    ie = _img_extent(extent)
    if bg is not None:
        ax.imshow(bg, cmap="gray", extent=ie, origin="upper", aspect="auto", zorder=0)
    else:
        x0, x1, y0, y1 = extent
        ax.add_patch(mp.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                  facecolor="#101317", edgecolor="#444",
                                  lw=1.0, zorder=0))
    x0, x1, y0, y1 = extent
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)          # y downward
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=10)

    cmap = _cmap(C.CONTACT_CMAP)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    has_data = False
    ports_drawn = set()

    for td in (sel.trials if sel else []):
        fin = np.isfinite(td.x) & np.isfinite(td.y)
        if not fin.any():
            continue
        has_data = True
        # faint head trajectory for context
        ax.plot(td.x, td.y, color=C.TRAJ_LINE_COLOR, lw=C.TRAJ_LINE_LW,
                alpha=C.TRAJ_LINE_ALPHA, zorder=2, solid_capstyle="round")
        # ethanol-contact dots coloured by normalised concentration
        if contacts_on:
            c = td.conc[fin]
            rgba = cmap(norm(c))
            a = np.full(c.shape, float(alpha))
            if thr_on:
                a[c < thr] = 0.0
            rgba[:, 3] = a
            ax.scatter(td.x[fin], td.y[fin], s=C.DEFAULT_DOT_SIZE, c=rgba,
                       edgecolors="none", zorder=3)
        # target odor port (reward endpoint) -- red circle, once per location
        if td.endpoint is not None and np.all(np.isfinite(td.endpoint)):
            key = (round(float(td.endpoint[0]), 1), round(float(td.endpoint[1]), 1))
            if key not in ports_drawn:
                ports_drawn.add(key)
                ax.scatter([td.endpoint[0]], [td.endpoint[1]], s=C.PORT_SIZE,
                           facecolors="none", edgecolors=C.PORT_COLOR,
                           linewidths=C.PORT_LW, zorder=5)
                ax.scatter([td.endpoint[0]], [td.endpoint[1]], s=14,
                           c=C.PORT_COLOR, zorder=5)

    if not has_data:
        ax.text(0.5, 0.5, "no data for this selection", transform=ax.transAxes,
                ha="center", va="center", color="#c33", fontsize=10)

    if has_data and contacts_on:
        sm = cm.ScalarMappable(norm=norm, cmap=cmap); sm.set_array([])
        cb = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02)
        cb.set_label("normalised plume concentration"
                     + (f"  (α=0 below {thr:g})" if thr_on else ""), fontsize=8)
        cb.ax.tick_params(labelsize=7)

    # ---------- ethanol time series ----------
    any_ts = False
    for td in (sel.trials if sel else []):
        if td.t_series is None or td.t_series.size == 0:
            continue
        any_ts = True
        lbl = td.label if len(sel.trials) <= 10 else "_nolegend_"
        axt.plot(td.t_series, td.sig_series, color=td.color, lw=0.9,
                 alpha=0.9, label=lbl)
    # colormap range + alpha threshold reference lines (normalised units), each
    # DRAGGABLE up/down to set its value:
    #   green  dashed = colormap MAX (vmax)
    #   cyan   dashed = colormap MIN (vmin)
    #   red    dashed = alpha threshold (the dot cutoff)
    l_max = axt.axhline(vmax, color="#0a9d0a", ls="--", lw=1.0, label=f"cmap max = {vmax:g}")
    l_min = axt.axhline(vmin, color="#00b3b3", ls="--", lw=1.0, label=f"cmap min = {vmin:g}")
    l_thr = axt.axhline(thr, color="red", ls="--", lw=1.2, label=f"α threshold = {thr:g}")
    axt.set_xlabel("time (s)", fontsize=8)
    axt.set_ylabel(f"ethanol\n({signal_label}, norm)", fontsize=8)
    axt.tick_params(labelsize=7)
    axt.set_ylim(-0.02, 1.05)
    axt.legend(loc="upper right", fontsize=6, framealpha=0.85, ncol=2)
    axt.grid(True, alpha=0.15)

    fig.subplots_adjust(left=0.03, right=0.97, top=0.94, bottom=0.12)
    return {"fig": fig, "ax": ax, "axt": axt,
            "lines": {"vmax": l_max, "vmin": l_min, "thr": l_thr}}


# ---------------------------------------------------------------------------
# Qt wrapper (imported only when the GUI runs)
# ---------------------------------------------------------------------------
try:
    from PySide6 import QtCore, QtWidgets
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    _HAVE_QT = True
except Exception:  # pragma: no cover
    _HAVE_QT = False


if _HAVE_QT:
    _DRAG_TOL_PX = 8          # how close (pixels) the cursor must be to grab a line

    class ArenaView(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.fig = Figure(figsize=(7.6, 5.2))
            self.canvas = FigureCanvas(self.fig)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self.canvas)
            self._bg = None
            self._extent = C.ARENA_EXTENT_PX
            # interactive threshold dragging on the time-series panel
            self._thr_cb = None          # callback(kind, value) into the main window
            self._axt = None             # the time-series Axes
            self._lines = {}             # kind -> Line2D (vmax/vmin/thr)
            self._vals = {"vmin": C.DEFAULT_VMIN, "vmax": C.DEFAULT_VMAX,
                          "thr": C.DEFAULT_ALPHA_THRESH}
            self._drag = None            # kind currently being dragged
            self.canvas.mpl_connect("button_press_event", self._on_press)
            self.canvas.mpl_connect("motion_notify_event", self._on_motion)
            self.canvas.mpl_connect("button_release_event", self._on_release)
            self._render_blank()

        def set_background(self, img, extent=None):
            self._bg = img
            if extent is not None:
                self._extent = extent

        def set_threshold_callback(self, fn):
            """fn(kind, value) is called on release; kind in {'vmin','vmax','thr'}."""
            self._thr_cb = fn

        # -- interactive drag of the reference lines ----------------------
        def _nearest_line(self, event):
            if self._axt is None or event.inaxes is not self._axt or event.y is None:
                return None
            best, best_px = None, 1e9
            for kind, ln in self._lines.items():
                if ln is None:
                    continue
                y = ln.get_ydata()[0]
                _, py = self._axt.transData.transform((0.0, y))
                d = abs(py - event.y)
                if d < best_px:
                    best, best_px = kind, d
            return best if best_px <= _DRAG_TOL_PX else None

        def _on_press(self, event):
            if event.button == 1:
                k = self._nearest_line(event)
                if k:
                    self._drag = k

        def _on_motion(self, event):
            if self._drag is None:
                cur = (QtCore.Qt.SizeVerCursor if self._nearest_line(event)
                       else QtCore.Qt.ArrowCursor)
                self.canvas.setCursor(cur)
                return
            if event.inaxes is not self._axt or event.ydata is None:
                return
            y = min(1.0, max(0.0, float(event.ydata)))
            if self._drag == "vmin":
                y = min(y, self._vals.get("vmax", 1.0))
            elif self._drag == "vmax":
                y = max(y, self._vals.get("vmin", 0.0))
            self._vals[self._drag] = y
            ln = self._lines.get(self._drag)
            if ln is not None:
                ln.set_ydata([y, y])
                self.canvas.draw_idle()

        def _on_release(self, event):
            if self._drag is None:
                return
            kind, self._drag = self._drag, None
            y = self._vals.get(kind)
            if y is not None and self._thr_cb:
                self._thr_cb(kind, round(float(y), 3))

        def _render_blank(self, title="Mouse Arena Data Console"):
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            x0, x1, y0, y1 = self._extent
            ax.add_patch(mp.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                      facecolor="#101317", edgecolor="#444", lw=1.0))
            ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(title, fontsize=10)
            if self._bg is None:
                ax.text(0.5, 0.5, "no arena background image (drop one in assets/)",
                        transform=ax.transAxes, ha="center", va="center",
                        color="#888", fontsize=9)
            self.canvas.draw_idle()

        def show_selection(self, sel, **kw):
            handles = render(self.fig, sel, bg=self._bg, extent=self._extent, **kw)
            self._axt = handles.get("axt")
            self._lines = handles.get("lines", {}) or {}
            self._vals = {"vmin": float(kw.get("vmin", C.DEFAULT_VMIN)),
                          "vmax": float(kw.get("vmax", C.DEFAULT_VMAX)),
                          "thr": float(kw.get("thr", C.DEFAULT_ALPHA_THRESH))}
            self.canvas.draw_idle()

        def save(self, path, dpi=200):
            ext = str(path).lower().rsplit(".", 1)[-1] if "." in str(path) else "png"
            kw = dict(bbox_inches="tight", facecolor="white")
            if ext not in ("pdf", "svg"):
                kw["dpi"] = dpi
            self.fig.savefig(path, **kw)
