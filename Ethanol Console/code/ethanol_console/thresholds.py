#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
thresholds.py -- the master per-trial threshold JSON store (no Qt).

One JSON file, keyed by recording (file) name, accumulates every trial the user
has thresholded. It is written to ``Ethanol Console/output`` and mirrored to
``DATA`` so downstream analyses can reference either copy.

Structure::

    {
      "meta": {
        "schema": "mouse_arena/ethanol_thresholds/1.0",
        "console": "Mouse Arena Ethanol Console",
        "version": "0.1.0",
        "aggregate_path": "...\\Mouse Arena Aggregate Data.h5",
        "created_utc": "2026-08-11T17:03:22Z",   # first creation of the file
        "updated_utc": "2026-08-11T18:10:44Z",   # last write
        "generated_local": "2026-08-11 11:10:44 PDT"
      },
      "trials": {
        "<file_name>": {
          "file_name": "...", "trial_index": 37, "loc": 3, "animal": 204,
          "date": "11-22-2019", "lighting": "infrared",
          "signal": "deconv", "baseline_subtracted": true,
          "baseline": {"method": "rolling_pct", "pct": 10.0,
                       "window_s": 20.0, "step_s": 0.1},
          "threshold": 0.0123,
          "threshold_units": "ethdeconv_baseline_subtracted",
          "min_duration_s": 0.05,
          "n_contacts": 5,
          "contact_onsets_s": [...],
          "contact_distances_px": [...],
          "endpoint_px": [506.0, 191.0],
          "set_utc": "2026-08-11T18:10:44Z",
          "set_local": "2026-08-11 11:10:44 PDT"
        }
      }
    }

A downstream program reproduces the odor-on mask by taking the named signal,
baseline-subtracting with the recorded ``baseline`` params, and keeping
above-``threshold`` episodes of at least ``min_duration_s``.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone

from . import console_config as C


def _now():
    """(utc_iso, local_str) -- production timestamps for the JSON metadata."""
    now_utc = datetime.now(timezone.utc)
    utc_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    local = now_utc.astimezone()
    tz = local.tzname() or ""
    local_str = local.strftime("%Y-%m-%d %H:%M:%S") + (f" {tz}" if tz else "")
    return utc_iso, local_str


def _atomic_write(path, text):
    """Write text to path atomically (tmp in same dir -> os.replace)."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".eththr_", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


class ThresholdStore:
    """Load / update / persist the master threshold JSON and its DATA mirror."""

    def __init__(self, aggregate_path, output_path=None, mirror_path=None,
                 version="0.1.0"):
        self.aggregate_path = str(aggregate_path)
        self.output_path = output_path or C.output_json_path()
        self.mirror_path = mirror_path or C.mirror_json_path()
        self.version = version
        self.doc = self._load()

    # -- load ------------------------------------------------------------
    def _skeleton(self):
        utc_iso, local_str = _now()
        return {
            "meta": {
                "schema": C.JSON_SCHEMA,
                "console": "Mouse Arena Ethanol Console",
                "version": self.version,
                "aggregate_path": self.aggregate_path,
                "created_utc": utc_iso,
                "updated_utc": utc_iso,
                "generated_local": local_str,
            },
            "trials": {},
        }

    def _load(self):
        for p in (self.output_path, self.mirror_path):
            if p and os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        doc = json.load(f)
                    doc.setdefault("meta", {})
                    doc.setdefault("trials", {})
                    doc["meta"].setdefault("schema", C.JSON_SCHEMA)
                    doc["meta"].setdefault("created_utc", _now()[0])
                    return doc
                except Exception:
                    continue
        return self._skeleton()

    # -- query -----------------------------------------------------------
    def get(self, file_name):
        return self.doc.get("trials", {}).get(str(file_name))

    def has(self, file_name):
        return str(file_name) in self.doc.get("trials", {})

    def count(self):
        return len(self.doc.get("trials", {}))

    # -- update ----------------------------------------------------------
    def set_trial(self, entry):
        """Insert/replace a trial entry (dict with a 'file_name') and persist.

        Returns (utc_iso, local_str) of the write."""
        fn = str(entry["file_name"])
        utc_iso, local_str = _now()
        entry = dict(entry)
        entry["set_utc"] = utc_iso
        entry["set_local"] = local_str
        self.doc.setdefault("trials", {})[fn] = entry
        self.doc.setdefault("meta", {})["updated_utc"] = utc_iso
        self.doc["meta"]["generated_local"] = local_str
        self.doc["meta"]["version"] = self.version
        self.doc["meta"]["aggregate_path"] = self.aggregate_path
        self.save()
        return utc_iso, local_str

    def save(self):
        text = json.dumps(self.doc, indent=2, sort_keys=False)
        _atomic_write(self.output_path, text)
        # mirror to DATA (best-effort; report failure to caller via exception)
        if os.path.abspath(self.mirror_path) != os.path.abspath(self.output_path):
            try:
                _atomic_write(self.mirror_path, text)
            except Exception:
                # fall back to a plain copy of the primary if the atomic mirror fails
                shutil.copyfile(self.output_path, self.mirror_path)
