#!/usr/bin/env python3
"""SessionStart hook: confirm the analysis interpreter before any work starts.

Emits a short line to stdout (Claude Code adds SessionStart stdout to the
session context). It tells the agent EXACTLY which python to run and, if the
default venv is missing, tells it to ASK the user for a path instead of
silently falling back to a bare `python` (which on this machine resolves to
Anaconda -- the wrong interpreter, without scipy/statsmodels/h5py/python-docx).

Bulletproof: everything is wrapped so it can never block session startup; on
any error it exits 0 and simply prints nothing useful. It only READS env/paths.
"""
import os, sys

try:
    py = os.environ.get("AR_PY", "").strip().strip('"')
    venv = os.environ.get("AR_VENV", "").strip().strip('"')

    def exists(p):
        try:
            return bool(p) and os.path.isfile(p)
        except Exception:
            return False

    if exists(py):
        print(f"[venv] Analysis interpreter CONFIRMED: AR_PY = {py}")
        print("[venv] Run ALL analysis/figure/report code with \"$AR_PY\" "
              "(never bare `python`, `py`, or an Anaconda path).")
    else:
        print("[venv] WARNING: the default analysis venv was NOT found at "
              f"AR_PY={py!r}.")
        print("[venv] Do NOT fall back to a bare `python`. Before running any "
              "analysis code, ASK THE USER for the path to a usable venv "
              "python.exe, then use that path (quoted) for every run. "
              "If the session is unattended and no interpreter can be "
              "confirmed, STOP and leave a note rather than guessing.")
except Exception:
    pass

sys.exit(0)
