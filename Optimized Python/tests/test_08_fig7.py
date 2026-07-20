import os, pytest, numpy as np
from mouse_arena.figures import make_fig7
from mouse_arena import config
from conftest import FIX, load, assert_ok, compare_array, sc

CASES = {
 "case_11-24-2019_Loc1": dict(mat="11-24-2019-4-51 PM-Mohammad-204_Trial6_Loc1.mat",
    dat="11-24-2019-4-51 PM-Mohammad-204_Trial6_Loc1.avi.dat",
    tmin=11, tmax=29.5, th=0.11, src=(474,61)),
 "case_11-27-2019_Loc4": dict(mat="11-27-2019-10-41 AM-Mohammad-211_Trial2_Loc4.mat",
    dat="11-27-2019-10-41 AM-Mohammad-211_Trial2_Loc4.avi.dat",
    tmin=0, tmax=32.4, th=0.11, src=(453,164)),
}

@pytest.mark.parametrize("casen", list(CASES))
def test_fig7_end_to_end(casen):
    c = CASES[casen]
    base = os.path.join(FIX, "08_fig7", casen, "inputs")
    exp = load("08_fig7", casen, "outputs", "fig7_panels.mat")
    full = load("08_fig7", casen, "intermediates", "fig7_full.mat")
    r = make_fig7.compute(os.path.join(base, c["mat"]), os.path.join(base, c["dat"]),
                          tmin=c["tmin"], tmax=c["tmax"], th=c["th"], src=c["src"],
                          FR_cam=90, params=config.PARAMS)
    # intermediates (full-trace)
    assert_ok(compare_array(r["full"]["ethdec_full"], full["ethdec_full"], rtol=1e-4, atol=1e-6, name="ethdec_full"))
    assert_ok(compare_array(r["full"]["bt"], full["bt"], rtol=1e-9, atol=1e-9, name="bt"))
    # panels
    assert_ok(compare_array(r["traj_x"], exp["traj_x"], rtol=1e-4, atol=1e-4, name="traj_x"))
    assert_ok(compare_array(r["traj_y"], exp["traj_y"], rtol=1e-4, atol=1e-4, name="traj_y"))
    assert_ok(compare_array(r["speed"], exp["speed"], rtol=1e-4, atol=1e-4, name="speed"))
    assert_ok(compare_array(r["ethdec_window"], exp["ethdec_window"], rtol=1e-4, atol=1e-6, name="ethdec_window"))
    assert_ok(compare_array(r["ethresc"], exp["ethresc"], rtol=1e-5, atol=1e-6, name="ethresc"))
    assert_ok(compare_array(np.asarray(r["hit"]).astype(int), np.asarray(exp["hit"]).astype(int), exact=True, name="hit"))
    assert_ok(compare_array(r["contact_xy"], exp["contact_xy"], rtol=1e-4, atol=1e-4, name="contact_xy"))
    assert abs(sc(r["t0"]) - sc(exp["t0"])) < 1e-9
