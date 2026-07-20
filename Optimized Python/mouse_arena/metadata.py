"""metadata — ports of parse_trial_meta, extract_pulse_metrics, ma_first.

parse_trial_meta(name): regex Pulse_Ns->duration, Frequency_NHz->freq, Loc_N->loc (NaN if absent).
extract_pulse_metrics(val, Fs): binarize valve>midpoint; rising edges=onsets; high-run/Fs=durations;
  freq=1/(median(diff(onsets))/Fs).
ma_first(cands, must_exist=False): first existing path in list.
"""
import os
import re

import numpy as np


def parse_trial_meta(name):
    """Extract experiment metadata from a recording filename (see parse_trial_meta.m).

    MATLAB:
        m = struct('duration',NaN,'freq',NaN,'loc',NaN);
        tok = regexpi(name,'Pulse[_ ]?(\\d+(?:\\.\\d+)?)\\s*s','tokens','once');
        tok = regexpi(name,'Frequency[_ ]?(\\d+(?:\\.\\d+)?)\\s*Hz','tokens','once');
        tok = regexpi(name,'Loc[_ ]?(\\d+)','tokens','once');
    """
    name = str(name)
    m = {"duration": float("nan"), "freq": float("nan"), "loc": float("nan")}

    tok = re.search(r"Pulse[_ ]?(\d+(?:\.\d+)?)\s*s", name, re.IGNORECASE)
    if tok:
        m["duration"] = float(tok.group(1))

    tok = re.search(r"Frequency[_ ]?(\d+(?:\.\d+)?)\s*Hz", name, re.IGNORECASE)
    if tok:
        m["freq"] = float(tok.group(1))

    tok = re.search(r"Loc[_ ]?(\d+)", name, re.IGNORECASE)
    if tok:
        m["loc"] = float(tok.group(1))

    return m


def extract_pulse_metrics(val, Fs):
    """Derive stimulus timing from the VALVE channel itself (see extract_pulse_metrics.m).

    MATLAB:
        val = val(:);
        hi  = val > (min(val)+max(val))/2;
        d   = diff([0; hi; 0]);
        onsets  = find(d==1);
        offsets = find(d==-1);
        n = min(numel(onsets),numel(offsets));
        durations_s = (offsets(1:n)-onsets(1:n))/Fs;
        if numel(onsets) >= 2
            freq_hz = 1/(median(diff(onsets))/Fs);
        else
            freq_hz = NaN;
        end

    Returns (onsets, durations_s, freq_hz). ``onsets`` are 1-based sample
    indices, matching MATLAB's find().
    """
    val = np.asarray(val, dtype=np.float64).reshape(-1)
    hi = (val > (val.min() + val.max()) / 2.0).astype(np.int64)
    d = np.diff(np.concatenate(([0], hi, [0])))
    # MATLAB find() returns 1-based indices
    onsets = np.flatnonzero(d == 1) + 1
    offsets = np.flatnonzero(d == -1) + 1

    n = min(onsets.size, offsets.size)
    durations_s = (offsets[:n] - onsets[:n]) / Fs

    if onsets.size >= 2:
        freq_hz = 1.0 / (np.median(np.diff(onsets)) / Fs)
    else:
        freq_hz = float("nan")

    return onsets, durations_s, freq_hz


def ma_first(cands, must_exist=False):
    """Return the first existing path from an ordered candidate list (see ma_first.m).

    MATLAB:
        if ischar(cands); cands = {cands}; end
        p = '';
        for i=1:numel(cands)
            if exist(cands{i},'file') || exist(cands{i},'dir'); p = cands{i}; return; end
        end
        if mustExist && isempty(p)
            error('ma_first:notFound', ...);
        end
    """
    if isinstance(cands, str):
        cands = [cands]

    p = ""
    for c in cands:
        if os.path.isfile(c) or os.path.isdir(c):
            p = c
            return p

    if must_exist and not p:
        raise FileNotFoundError(
            "None of these exist:\n" + "\n".join(cands)
        )
    return p
