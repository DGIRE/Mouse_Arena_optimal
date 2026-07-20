import os, numpy as np
from mouse_arena import config, io_labview
from conftest import FIX, load, assert_ok, compare_array, compare_scalar, sc

STAGE, CASE = "01_loader", "case_11-24-2019_Loc1"
DAT = os.path.join(FIX, STAGE, CASE, "inputs",
                   "11-24-2019-4-51 PM-Mohammad-204_Trial6_Loc1.avi.dat")

def test_loader_exact():
    exp = load(STAGE, CASE, "outputs", "loader_output.mat")
    p = config.PARAMS
    S = io_labview.read_labview_dat(DAT, p.chan_beh, p)
    for k in ("time", "TS", "ETH", "n_ten"):
        assert_ok(compare_array(S[k], exp[k], rtol=0, atol=0, exact=True, name=f"loader.{k}"))
    assert abs(sc(S["Fs"]) - sc(exp["Fs"])) < 1e-9
