import pytest, numpy as np
from mouse_arena import kernels
from conftest import load, manifest, assert_ok, compare_array

@pytest.mark.parametrize("casen", ["behavior", "sensor_char", "unit"])
def test_doe_kernel(casen):
    m = manifest("02_kernel", casen)["params"]
    exp = load("02_kernel", casen, "outputs", "kernel.mat")["kn"]
    kn = kernels.doe_kernel(m["tau_rise"], m["tau_decay"], int(m["N"]), m["Fs"])
    assert_ok(compare_array(kn, exp, rtol=1e-10, atol=1e-12, name=f"kernel.{casen}"))
