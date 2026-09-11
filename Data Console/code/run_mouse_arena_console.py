#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_mouse_arena_console.py -- convenience launcher.

Run from anywhere:
    python "run_mouse_arena_console.py" ["path\\to\\Mouse Arena Aggregate Data.h5"]

This just makes the package importable and calls mouse_arena_console.app.main.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mouse_arena_console.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
