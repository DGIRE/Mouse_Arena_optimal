"""lighting — ports of classify_lighting, lighting_for_trial, filter_lighting.

classify_lighting(img): RGB frame -> 'infrared'/'deep-red'/'unknown' (green-channel rule).
lighting_for_trial(name, csv_path): parse M-D-YYYY date from name, look up condition in
  config/lighting_sessions.csv; else direct label match; else 'unknown'.
filter_lighting(trials, cond): keep dict-trials whose 'lighting'==cond; 'all'/'' passthru.
"""
import csv
import os
import re
import warnings

import numpy as np

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CSV = os.path.join(_PKG_DIR, "config", "lighting_sessions.csv")

_EPS = np.finfo(float).eps


def classify_lighting(img):
    """Classify arena illumination from a COLOUR video frame (see classify_lighting.m).

    MATLAB:
        info = struct('R',NaN,'G',NaN,'B',NaN,'greenFrac',NaN);
        if ndims(img) ~= 3 || size(img,3) < 3
            cond = 'unknown'; warning(...); return;
        end
        img = double(img);
        R = mean(mean(img(:,:,1))); G = mean(mean(img(:,:,2))); B = mean(mean(img(:,:,3)));
        info.R=R; info.G=G; info.B=B; info.greenFrac = G / max(R+G+B, eps);
        if G < 0.15*max(R,B) && R > 1.5*max(G,B)
            cond = 'deep-red';
        else
            cond = 'infrared';
        end
    """
    info = {"R": float("nan"), "G": float("nan"), "B": float("nan"), "greenFrac": float("nan")}

    img = np.asarray(img)
    if img.ndim != 3 or img.shape[2] < 3:
        warnings.warn(
            "classify_lighting:grayscale: Need an RGB frame; a grayscale/meanImage "
            "cannot be classified by brightness. Use lighting_for_trial() / "
            "lighting_sessions.csv."
        )
        return "unknown", info

    img = img.astype(np.float64)
    R = float(np.mean(img[:, :, 0]))
    G = float(np.mean(img[:, :, 1]))
    B = float(np.mean(img[:, :, 2]))
    info["R"], info["G"], info["B"] = R, G, B
    info["greenFrac"] = G / max(R + G + B, _EPS)

    if G < 0.15 * max(R, B) and R > 1.5 * max(G, B):
        cond = "deep-red"
    else:
        cond = "infrared"

    return cond, info


def _read_sessions(csv_path):
    """Read session-to-condition mappings from a CSV file."""
    rows = []
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def lighting_for_trial(name, csv_path=None):
    """Look up the illumination condition for a trial/session (see lighting_for_trial.m).

    MATLAB:
        csv = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'config', ...
            'lighting_sessions.csv');
        TBL = readtable(csv, ...);
        cond = "unknown";
        tok = regexp(char(name), '(\\d{1,2}-\\d{1,2}-\\d{4})', 'tokens', 'once');
        if ~isempty(tok); key = string(tok{1}); end
        if key ~= ""; hit = TBL(TBL.session == key, :); end
        if isempty(hit)
            for i = 1:height(TBL)
                if contains(name, TBL.session(i)); hit = TBL(i,:); break; end
            end
        end
        if ~isempty(hit); cond = char(hit.condition(1)); end
    """
    if csv_path is None:
        csv_path = _DEFAULT_CSV

    name = str(name)
    rows = _read_sessions(csv_path)

    key = ""
    tok = re.search(r"(\d{1,2}-\d{1,2}-\d{4})", name)
    if tok:
        key = tok.group(1)

    hit = None
    if key != "":
        for row in rows:
            if row.get("session", "") == key:
                hit = row
                break

    if hit is None:
        for row in rows:
            session = row.get("session", "")
            if session and session in name:
                hit = row
                break

    if hit is not None:
        return hit.get("condition", "unknown")
    return "unknown"


def filter_lighting(trials, cond):
    """Keep only trials matching an illumination condition (see filter_lighting.m).

    MATLAB:
        cond = lower(strtrim(char(cond)));
        if isempty(cond) || strcmp(cond,'all'); return; end
        if isempty(DM) || ~isfield(DM,'lighting'); return; end
        keep = arrayfun(@(d) strcmpi(char(string(d.lighting)), cond), DM);
        DM = DM(keep);

    ``trials`` is a list of dicts, each carrying a 'lighting' key.
    """
    cond = str(cond).strip().lower()
    if cond == "" or cond == "all":
        return trials
    if not trials:
        return trials
    if not any("lighting" in t for t in trials):
        return trials

    return [t for t in trials if str(t.get("lighting", "")).lower() == cond]
