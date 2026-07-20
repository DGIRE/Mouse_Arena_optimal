"""Fixture loading utilities for the Mouse Arena MATLAB->Python differential harness.

All golden fixtures are MATLAB -v7.3 (HDF5) .mat files plus JSON manifests.
MATLAB stores arrays column-major, so h5py reads a MATLAB [N x M] array back as
(M, N); we transpose to recover the MATLAB orientation, then the caller asserts
against manifest array_specs. See Gold Fixtures/GUIDE.md sections 3-4.

The DATA_MAT struct-array loader is format-agnostic: v7.3/HDF5 via h5py, old
v5/v7 via scipy.io.loadmat. Both return the same MATLAB-oriented per-trial dicts.
"""
from __future__ import annotations
import json, os
import numpy as np
import h5py
import scipy.io as sio

# Repo-relative default: <repo>/Golden Fixtures/fixtures (stages live under fixtures/).
# __file__ = <repo>/Optimized Python/harness/fixtures.py  ->  up 2 dirs = <repo>.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FIX_ROOT = os.environ.get(
    "MA_FIXTURES",
    os.path.join(_REPO_ROOT, "Golden Fixtures", "fixtures"),
)


def _decode_char(ds, f=None):
    """Decode a MATLAB char array (stored as uint16 code units) to str."""
    a = np.array(ds)
    return "".join(chr(int(c)) for c in a.ravel())


def _load_dataset(ds):
    a = np.array(ds)
    # recover MATLAB orientation (h5py reads column-major layout)
    a = a.T
    return a


def load_mat_v73(path):
    """Load a simple -v7.3 .mat of plain arrays / char / one-level structs.

    Returns {varname: value}. Arrays are transposed to MATLAB orientation.
    uint16 char datasets are decoded to str. A one-level struct saved as a
    scalar struct (e.g. ks_result, pilot) is returned as a nested dict.
    """
    out = {}
    with h5py.File(path, "r") as f:
        for k in f.keys():
            if k == "#refs#":
                continue
            obj = f[k]
            if isinstance(obj, h5py.Group):
                sub = {}
                for fk in obj.keys():
                    d = obj[fk]
                    if isinstance(d, h5py.Dataset):
                        if d.dtype == np.uint16:
                            sub[fk] = _decode_char(d)
                        else:
                            v = _load_dataset(d)
                            sub[fk] = v
                out[k] = sub
            elif isinstance(obj, h5py.Dataset):
                if obj.dtype == np.uint16:
                    out[k] = _decode_char(obj)
                else:
                    out[k] = _load_dataset(obj)
    return out


def _data_mat_struct_h5py(path, fields=None, trials=None):
    """DATA_MAT struct array via h5py (v7.3): one HDF5 object ref per trial."""
    with h5py.File(path, "r") as f:
        g = f["DATA_MAT"]
        allfields = list(g.keys())
        use = fields if fields is not None else allfields
        n = g[allfields[0]].shape[0]
        idxs = range(n) if trials is None else trials
        rows = []
        for k in idxs:
            row = {}
            for fld in use:
                ref = g[fld][k, 0]
                d = f[ref]
                if d.dtype == np.uint16:
                    row[fld] = "".join(chr(int(c)) for c in np.array(d).ravel())
                else:
                    row[fld] = np.array(d).T
            rows.append(row)
    return rows


def _data_mat_struct_scipy(path, fields=None, trials=None):
    """DATA_MAT struct array via scipy.io (old v5/v7 .mat).

    scipy returns fields already in MATLAB orientation, so no transpose is
    applied — matching the h5py path element for element. Char fields are
    decoded to str to mirror the uint16 handling.
    """
    raw = sio.loadmat(path, struct_as_record=True, squeeze_me=False)
    if "DATA_MAT" not in raw:
        raise KeyError("variable 'DATA_MAT' not found in %s" % path)
    dm = np.asarray(raw["DATA_MAT"])
    flat = dm.ravel(order="F")                      # MATLAB column-major linear order
    allfields = list(dm.dtype.names or [])
    use = fields if fields is not None else allfields
    n = flat.size
    idxs = range(n) if trials is None else trials
    rows = []
    for k in idxs:
        elem = flat[k]
        row = {}
        for fld in use:
            v = np.asarray(elem[fld])
            if v.dtype.kind in ("U", "S"):          # MATLAB char -> str
                row[fld] = "".join(v.ravel().astype(str))
            else:
                row[fld] = v                        # already MATLAB-oriented
        rows.append(row)
    return rows


def load_data_mat_struct(path, fields=None, trials=None):
    """Read a MATLAB struct array 'DATA_MAT' into a list of per-trial dicts.

    Format-agnostic: v7.3/HDF5 via h5py (object references, arrays transposed to
    MATLAB orientation); old v5/v7 via scipy.io.loadmat (already MATLAB-oriented).
    Both paths return the same structure — one dict per trial, numeric fields as
    MATLAB-oriented ndarrays and char fields decoded to str. `trials` optionally
    restricts to given 0-based indices; `fields` optionally restricts to a subset
    of field names.
    """
    try:
        return _data_mat_struct_h5py(path, fields=fields, trials=trials)
    except OSError:
        return _data_mat_struct_scipy(path, fields=fields, trials=trials)


def load_manifest(case_dir):
    with open(os.path.join(case_dir, "manifest.json")) as fh:
        return json.load(fh)


def case_dir(stage, case):
    return os.path.join(FIX_ROOT, stage, case)


def input_path(stage, case, fname):
    return os.path.join(FIX_ROOT, stage, case, "inputs", fname)
