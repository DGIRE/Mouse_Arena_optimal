---
name: setup-venv
description: Confirm or locate the Python virtual environment used to run all analysis code. Use at the start of a session, or whenever a run fails on a missing interpreter or missing package. Establishes $AR_PY without ever installing packages mid-run.
---

# setup-venv — confirm the analysis interpreter

1. Check the default first: `AR_PY` (from `~/.claude/settings.json`). Verify the
   file exists — e.g. `ls "$AR_PY"` or `"$AR_PY" -c "import sys;print(sys.executable)"`.
2. If it works, use `"$AR_PY"` for everything and stop here. Optionally confirm
   key packages: `"$AR_PY" -c "import numpy,scipy,pandas,matplotlib,h5py,docx"`.
3. **If the default venv does not exist** (different computer, moved folder):
   - Attended session → ask the user for the path to a usable venv's
     `Scripts/python.exe` (Windows) or `bin/python` (macOS/Linux), then use that
     quoted path for the rest of the session (and suggest they update `AR_PY` in
     `~/.claude/settings.json` to make it permanent).
   - Unattended session → STOP and leave a note naming the missing path; do NOT
     fall back to a bare `python`/Anaconda and do NOT `pip install`.
4. Never create environments or install packages inside an unattended run — that
   is a deliberate, attended setup step.
