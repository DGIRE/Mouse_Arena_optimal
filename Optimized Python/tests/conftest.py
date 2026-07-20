import os, sys, json
import numpy as np
import pytest

HERE = os.path.dirname(__file__)
PKG_ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, PKG_ROOT)
FIX = os.environ.get("MA_FIXTURES", os.path.abspath(os.path.join(HERE, "..", "..", "Golden Fixtures", "fixtures")))

from harness.fixtures import load_mat_v73, load_manifest, load_data_mat_struct  # noqa
from harness.compare import compare_array, compare_scalar  # noqa

def case(stage, casename):
    return os.path.join(FIX, stage, casename)

def load(stage, casename, sub, fname):
    return load_mat_v73(os.path.join(FIX, stage, casename, sub, fname))

def manifest(stage, casename):
    return load_manifest(os.path.join(FIX, stage, casename))

def sc(x):
    return float(np.asarray(x).ravel()[0])

def _datamat_path():
    return os.path.join(FIX, "06_data_mat", "data_mat", "outputs", "DATA_MAT.mat")

def datamat_available():
    """True only when DATA_MAT.mat is present AND is a real MAT file.

    A genuine MAT file (Level-5 v5/v7 or v7.3/HDF5) begins with the ASCII text
    "MATLAB". Checking the signature lets an absent, truncated, or placeholder
    file SKIP the population test (with an accurate reason), while a real MAT
    file runs it — so an actual loader/compute regression still surfaces as a
    failure rather than being silently skipped.
    """
    p = _datamat_path()
    if not os.path.exists(p):
        return False
    try:
        with open(p, "rb") as fh:
            return fh.read(6) == b"MATLAB"
    except OSError:
        return False

def assert_ok(res):
    assert res["ok"], f"{res.get('name','')}: {res.get('error','mismatch')} | {res}"
