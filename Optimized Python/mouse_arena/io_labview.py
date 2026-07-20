"""io_labview — port of common/read_labview_dat.m (fixture 01_loader). [High risk]

read_labview_dat(fn, chan_map, params): read big-endian float64; find record
sentinels (== params.sentinel, -500); drop the first params.skipRecords (20);
guard so n_ten+max(offset) <= N; channel k = data[n_ten + offset_k]; Fs =
1/(median(diff(time))/1000) when a 'time' channel exists. n_ten are the 1-based
MATLAB sentinel indices *after* the skip (the fixture stores them). ETH offset
is +3 for the 2019 head-sensor 5-ch map. Returns dict with one entry per channel
name plus 'n_ten' and 'Fs'.
"""
import numpy as np


def read_labview_dat(fn, chan_map, params=None):
    """Read a LabView .dat / .avi.dat acquisition file (see read_labview_dat.m).

    Faithful translation of the MATLAB routine:
      data  = fread(fid,'float64','ieee-be')          -> big-endian float64
      n_ten = find(data == sentinel)                  -> 1-based sentinel indices
      n_ten = n_ten(skipRecords:end)                  -> drop initial records
      n_ten = n_ten(n_ten + max(offset) <= numel)     -> end-of-file guard
      S.(name) = data(n_ten + offset)                 -> per-channel extraction
      Fs = 1/(median(diff(time))/1000)                -> ms -> Hz

    Returns a dict with one (N,1) array per channel name, plus 'n_ten'
    (1-based MATLAB indices, as stored by the fixture) and 'Fs'.
    """
    if params is None:
        from mouse_arena import config
        params = config.PARAMS

    sentinel = params.sentinel
    skip_records = int(params.skipRecords)

    data = np.fromfile(fn, dtype=">f8")
    N = data.size

    # MATLAB find() is 1-based; the fixture stores n_ten as 1-based indices.
    pos = np.flatnonzero(data == sentinel)      # 0-based positions
    n_ten = pos + 1                             # -> 1-based MATLAB indices

    # MATLAB: if numel(n_ten) > skipRecords; n_ten = n_ten(skipRecords:end);
    # n_ten(20:end) keeps from the 20th element -> 0-based slice [19:].
    if n_ten.size > skip_records:
        n_ten = n_ten[skip_records - 1:]

    # Guard against reading past end of file: n_ten + max(offset) <= N.
    max_offset = max(chan_map.values())
    n_ten = n_ten[n_ten + max_offset <= N]

    S = {}
    for name, offset in chan_map.items():
        # MATLAB data(n_ten + offset), 1-based -> data[(n_ten-1)+offset] in 0-based.
        idx = (n_ten - 1) + offset
        S[name] = data[idx].reshape(-1, 1)

    S["n_ten"] = n_ten.astype(np.float64).reshape(-1, 1)

    if "time" in S:
        dt = np.median(np.diff(S["time"].ravel()))   # ms
        S["Fs"] = 1.0 / (dt / 1000.0)
    else:
        S["Fs"] = params.Fs

    return S
