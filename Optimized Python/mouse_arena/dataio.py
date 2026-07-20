"""dataio — production .mat loaders (v7.3 arrays, DATA_MAT struct array).

Mirrors harness/fixtures.py so the shipped package can load paper .mat inputs
and the DATA_MAT aggregate at run time.
"""
import h5py
import numpy as np
import scipy.io as sio


def _decode_char(ds):
    """Decode a MATLAB char array (stored as uint16 code units) to str."""
    a = np.array(ds)
    return "".join(chr(int(c)) for c in a.ravel())


def _h5_value(obj):
    """Convert one HDF5 dataset/group entry to a Python/numpy value.

    Arrays are transposed to MATLAB orientation (h5py reads MATLAB's
    column-major storage back as the transpose of the original shape).
    uint16 datasets (MATLAB char arrays) are decoded to str. Groups (one-level
    scalar structs, e.g. ks_result, pilot) become nested dicts.
    """
    if isinstance(obj, h5py.Group):
        return {k: _h5_value(obj[k]) for k in obj.keys()}
    # h5py.Dataset
    if obj.dtype == np.uint16:
        return _decode_char(obj)
    a = np.array(obj)
    return a.T


def _load_mat_h5py(path):
    """Load a v7.3/HDF5 .mat file via h5py, transposing arrays to MATLAB orientation."""
    out = {}
    with h5py.File(path, "r") as f:
        for k in f.keys():
            if k.startswith("__") or k == "#refs#":
                continue
            out[k] = _h5_value(f[k])
    return out


def _load_mat_scipy(path):
    """Load a v5/v7 .mat file via scipy.io, squeezing 1x1 arrays to scalars."""
    raw = sio.loadmat(path)
    out = {}
    for k, v in raw.items():
        if k.startswith("__"):
            continue
        if isinstance(v, np.ndarray) and v.size == 1:
            v = v.reshape(-1)[0]
        out[k] = v
    return out


def load_mat(path):
    """Load a MATLAB .mat file, whether old v5/v7 or v7.3/HDF5.

    Detects the format by trying h5py first (v7.3/HDF5); on failure, falls
    back to scipy.io.loadmat (old-style v5/v7). For the h5py path, arrays are
    transposed to MATLAB orientation (a.T) and uint16 char datasets are
    decoded to str. For the scipy path, arrays are returned as-is (already
    MATLAB-oriented) with 1x1 arrays squeezed to a Python/numpy scalar.
    Returns {varname: value}, skipping '__'-prefixed keys and '#refs#'.
    """
    try:
        return _load_mat_h5py(path)
    except OSError:
        return _load_mat_scipy(path)


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
    applied — the result matches the h5py path (which transposes) element for
    element. Char fields are decoded to str to mirror the uint16 handling.
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

    Format-agnostic: v7.3/HDF5 files are read via h5py (object references,
    arrays transposed to MATLAB orientation); old v5/v7 files are read via
    scipy.io.loadmat (already MATLAB-oriented). Both paths return the SAME
    structure — one dict per trial, numeric fields as MATLAB-oriented ndarrays
    and char fields decoded to str — so downstream code is format-blind.
    `trials` optionally restricts to given 0-based indices; `fields` optionally
    restricts to a subset of field names.
    """
    try:
        return _data_mat_struct_h5py(path, fields=fields, trials=trials)
    except OSError:
        return _data_mat_struct_scipy(path, fields=fields, trials=trials)
