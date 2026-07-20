import os, pytest, numpy as np
from mouse_arena.stage1 import s1b_import_frequency as s1b
from conftest import FIX, load, assert_ok, compare_array, sc

def _has(p): return os.path.exists(p)

def test_s1b_frequency_full():
    inp = os.path.join(FIX, "09_sensor_char", "fig3_frequency", "inputs", "data.mat")
    if not _has(inp):
        pytest.skip("fig3 input not staged")
    exp = load("09_sensor_char", "fig3_frequency", "outputs", "fig3_frequency.mat")
    out = s1b.import_from(inp)
    for k in ("ETH_all_sorted", "PID_all_sorted"):
        assert_ok(compare_array(out[k], exp[k], rtol=1e-9, atol=1e-9, name=f"s1b.{k}"))
    assert_ok(compare_array(np.asarray(out["freqs"]).ravel(), np.asarray(exp["freqs"]).ravel(),
                            rtol=1e-9, atol=1e-9, name="s1b.freqs"))
    assert_ok(compare_array(out["t"], exp["t"], rtol=1e-9, atol=1e-9, name="s1b.t"))
    assert abs(sc(out["Fs"]) - sc(exp["Fs"])) < 1e-9

def test_s1c_spatial_structural():
    """fig5 input (90MB) did not cross the bridge; verify output-fixture structure only."""
    exp = load("09_sensor_char", "fig5_spatial", "outputs", "fig5_spatial.mat")
    assert np.asarray(exp["ETH_all_sorted"]).shape == (35, 150001)
    assert np.asarray(exp["locations_sorted"]).size == 35
    assert sorted(np.unique(np.asarray(exp["locations_sorted"]).ravel()).tolist()) == [1, 2, 3]
