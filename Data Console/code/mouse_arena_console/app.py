#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py -- launch the Mouse Arena Data Console.

Usage:
    python -m mouse_arena_console.app ["path\\to\\Mouse Arena Aggregate Data.h5"]

If no path is given, the default repo location is used
(../../DATA/Mouse Arena Aggregate Data.h5, resolved in arena_config).
"""
from __future__ import annotations

import os
import sys

from PySide6 import QtWidgets

from . import arena_config as C
from .main_window import MainWindow


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit = argv[0] if argv else None
    agg_path = C.resolve_aggregate(explicit)

    if not os.path.isfile(agg_path):
        app = QtWidgets.QApplication(sys.argv)
        QtWidgets.QMessageBox.critical(
            None, "Mouse Arena Data Console",
            "Could not find the aggregate file:\n\n"
            f"{agg_path}\n\n"
            "Build it with DATA\\code\\build_mouse_arena_aggregate.py, pass the "
            "path as the first argument, or place it at the default location.")
        return 2

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(agg_path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
