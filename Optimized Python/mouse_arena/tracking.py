"""tracking — ports of lowpass_jitter, clean_track, compute_speed, normalize_dxdx (fixture 05). [High]

Faithful translations of MATLAB common/lowpass_jitter.m, clean_track.m,
compute_speed.m, normalize_dxdx.m (Tariq et al. 2020).

lowpass_jitter(xy, cutoff_norm=0.1): filtfilt(butter(3, cutoff, 'low'), xy) per column.
clean_track(xy, bnds): out-of-arena/non-finite -> NaN, then fillmissing linear w/
  EndValues 'nearest' per column (MATLAB fillmissing). bnds=[xmin xmax ymin ymax].
compute_speed(xy): spd[0]=0; spd[i]=hypot(dx,dy).
normalize_dxdx(x, baseline_idx): (x-mean(x[baseline]))/mean(x[baseline]).
"""
import numpy as np
from scipy.signal import butter, filtfilt


def lowpass_jitter(xy, cutoff_norm=0.1):
    """Low-pass filter body/head coordinates to remove tracking jitter.

    MATLAB: ``xy = filtfilt(butter(3,cutoff_norm,'low'), xy)`` applied per column.

    H5: MATLAB ``filtfilt`` default padding length is ``3*(max(len(a),len(b))-1)``
    (odd reflection), which differs from SciPy's default of ``3*max(len(a),len(b))``
    by one sample. We set ``padlen`` explicitly so the filtered edges match the
    MATLAB fixture bit-for-bit.
    """
    xy = np.asarray(xy, dtype=float)
    b, a = butter(3, cutoff_norm, 'low')
    padlen = 3 * (max(len(a), len(b)) - 1)
    # axis=0 -> filter each column independently, as MATLAB filtfilt does.
    return filtfilt(b, a, xy, axis=0, padtype='odd', padlen=padlen)


def clean_track(xy, bnds):
    """Remove out-of-arena tracking outliers and fill gaps.

    MATLAB clean_track.m: points outside ``bnds=[xmin xmax ymin ymax]`` (or any
    NaN/Inf) become NaN, then each column is filled with
    ``fillmissing(...,'linear','EndValues','nearest')`` — linear interpolation of
    interior gaps, nearest-value fill at the ends. If an entire column is NaN it
    is set to the arena centre (mean of the bounds).

    H6: implemented with ``np.interp`` over finite indices for interior NaNs and
    first/last finite value for the leading/trailing ends.
    """
    xy = np.asarray(xy, dtype=float)
    x = xy[:, 0].copy()
    y = xy[:, 1].copy()
    xmin, xmax, ymin, ymax = bnds[0], bnds[1], bnds[2], bnds[3]

    bad = (~np.isfinite(x)) | (~np.isfinite(y)) | \
          (x < xmin) | (x > xmax) | (y < ymin) | (y > ymax)
    x[bad] = np.nan
    y[bad] = np.nan

    if np.all(np.isnan(x)):
        x[:] = 0.5 * (xmin + xmax)
        y[:] = 0.5 * (ymin + ymax)
    else:
        x = _fillmissing_linear_nearest(x)
        y = _fillmissing_linear_nearest(y)

    return np.column_stack([x, y])


def _fillmissing_linear_nearest(v):
    """MATLAB fillmissing(v,'linear','EndValues','nearest') for a 1-D array.

    Interior NaNs are linearly interpolated by sample index; leading/trailing
    NaNs are filled with the nearest finite value.
    """
    v = np.asarray(v, dtype=float).copy()
    n = v.size
    finite = np.isfinite(v)
    if not np.any(finite):
        return v
    idx = np.arange(n)
    fi = idx[finite]
    # np.interp holds endpoints constant outside [fi[0], fi[-1]] -> equivalent to
    # 'EndValues','nearest'; interior gaps are linearly interpolated.
    v[~finite] = np.interp(idx[~finite], fi, v[finite])
    return v


def compute_speed(xy):
    """Frame-to-frame speed from an [nFrames x 2] position array.

    MATLAB compute_speed.m: ``spd(1)=0; spd(i)=hypot(dx,dy)``.
    """
    xy = np.asarray(xy, dtype=float)
    spd = np.zeros(xy.shape[0])
    if xy.shape[0] > 1:
        d = np.diff(xy, axis=0)
        spd[1:] = np.hypot(d[:, 0], d[:, 1])
    return spd


def normalize_dxdx(x, baseline_idx):
    """Fractional deviation from baseline: ``(x - x0)/x0``.

    MATLAB normalize_dxdx.m: ``x0 = mean(x(baseline_idx))``.
    """
    x = np.asarray(x, dtype=float).ravel()
    x0 = np.mean(x[baseline_idx])
    return (x - x0) / x0
