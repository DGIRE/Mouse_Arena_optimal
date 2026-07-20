"""Deterministic array comparison for the differential harness.

The comparison is pure arithmetic (zero model tokens): shape/dtype/orientation
first, then value closeness under a documented tolerance. This is the Validator
engine from the workflow design -- a model is only ever spent to *interpret* a
failure, never to decide pass/fail.
"""
from __future__ import annotations
import numpy as np


def as_matlab_vec(a):
    """Normalize a 1-D-ish array to a flat vector for value comparison."""
    a = np.asarray(a)
    return a.reshape(-1)


def compare_array(got, expected, rtol=1e-6, atol=1e-6, exact=False, name=""):
    """Compare two numeric arrays. Returns a result dict.

    Shapes are compared after squeezing singleton dims (so a MATLAB [N x 1]
    column and a Python (N,) vector are considered the same shape), but the
    element count must match exactly. Set exact=True for integer/boolean masks
    and IDs (bit-exact equality).
    """
    got = np.asarray(got)
    expected = np.asarray(expected)
    res = {"name": name, "ok": False}

    g2 = np.squeeze(got)
    e2 = np.squeeze(expected)
    res["got_shape"] = tuple(got.shape)
    res["exp_shape"] = tuple(expected.shape)
    if g2.size != e2.size:
        res["error"] = f"size mismatch: got {g2.size} vs expected {e2.size}"
        return res
    if g2.shape != e2.shape:
        # allow flat-vector equivalence (N,) vs (N,1) etc.
        if g2.reshape(-1).shape != e2.reshape(-1).shape:
            res["error"] = f"shape mismatch: {g2.shape} vs {e2.shape}"
            return res
        g2 = g2.reshape(-1)
        e2 = e2.reshape(-1)

    gf = g2.astype(np.float64).reshape(-1)
    ef = e2.astype(np.float64).reshape(-1)
    finite = np.isfinite(ef) & np.isfinite(gf)
    nan_mismatch = int(np.sum(np.isfinite(ef) != np.isfinite(gf)))
    res["n_nonfinite_expected"] = int(np.sum(~np.isfinite(ef)))
    res["nan_mismatch"] = nan_mismatch

    diff = np.abs(gf[finite] - ef[finite])
    denom = np.abs(ef[finite])
    res["max_abs"] = float(np.max(diff)) if diff.size else 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.where(denom > 0, diff / denom, 0.0)
    res["max_rel"] = float(np.max(rel)) if rel.size else 0.0
    # correlation (useful for time series)
    if gf[finite].size > 1 and np.std(ef[finite]) > 0 and np.std(gf[finite]) > 0:
        res["corr"] = float(np.corrcoef(gf[finite], ef[finite])[0, 1])
    else:
        res["corr"] = None

    if exact:
        res["ok"] = bool(np.array_equal(g2, e2))
        if not res["ok"]:
            res["error"] = f"not bit-exact ({int(np.sum(g2 != e2))} differing elements)"
        return res

    close = np.allclose(gf[finite], ef[finite], rtol=rtol, atol=atol)
    res["ok"] = bool(close and nan_mismatch == 0)
    if not res["ok"]:
        res["error"] = (f"not within rtol={rtol}, atol={atol}: "
                        f"max_abs={res['max_abs']:.3e} max_rel={res['max_rel']:.3e} "
                        f"nan_mismatch={nan_mismatch}")
    return res


def compare_scalar(got, expected, rtol=1e-6, atol=1e-9, name=""):
    g = float(np.asarray(got).reshape(-1)[0])
    e = float(np.asarray(expected).reshape(-1)[0])
    ok = abs(g - e) <= atol + rtol * abs(e)
    return {"name": name, "ok": bool(ok), "got": g, "expected": e,
            "abs": abs(g - e)}
