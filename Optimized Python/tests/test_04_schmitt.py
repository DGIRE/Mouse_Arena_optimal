import pytest, numpy as np
from mouse_arena import detection
from conftest import load, assert_ok, compare_array, sc

@pytest.mark.parametrize("casen", ["unit_synthetic", "case_11-24-2019_Loc1"])
def test_schmitt(casen):
    ins = load("04_schmitt", casen, "inputs", "schmitt_input.mat")
    out = load("04_schmitt", casen, "outputs", "schmitt_output.mat")
    x = np.asarray(ins.get("x", ins.get("ethresc"))).ravel()
    hi, lo = sc(ins["hi"]), sc(ins["lo"])
    y = detection.schmitt_trigger(x, hi, lo)
    assert_ok(compare_array(np.asarray(y).astype(int), np.asarray(out["y"]).astype(int),
                            exact=True, name=f"schmitt.{casen}"))
    if "contact_count" in out:
        assert int(np.asarray(y).sum()) == int(sc(out["contact_count"]))
