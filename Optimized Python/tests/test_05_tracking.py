import numpy as np
from mouse_arena import tracking, config
from conftest import load, assert_ok, compare_array, sc

def _orient(a):
    a = np.asarray(a)
    if a.shape[0] == 2 and a.shape[1] != 2:
        a = a.T
    return a

def test_fig7_filter_path():
    ins = load("05_tracking", "fig7_filter_11-24-2019_Loc1", "inputs", "track_input.mat")
    exp = load("05_tracking", "fig7_filter_11-24-2019_Loc1", "outputs", "track_output.mat")
    cb = _orient(ins["cr_body_raw"]); ch = _orient(ins["cr_head_raw"])
    body = tracking.lowpass_jitter(cb); head = tracking.lowpass_jitter(ch)
    fr = np.asarray(ins["fr_ts_body"]).ravel(); FR = sc(ins["FR_cam"])
    bt = fr / FR; t0 = bt.min(); bt = bt - t0
    spd = tracking.compute_speed(body)
    assert_ok(compare_array(body, exp["body"], rtol=1e-6, atol=1e-6, name="body"))
    assert_ok(compare_array(head, exp["head"], rtol=1e-6, atol=1e-6, name="head"))
    assert_ok(compare_array(bt, exp["body_time"], rtol=1e-9, atol=1e-9, name="body_time"))
    assert abs(t0 - sc(exp["t0"])) < 1e-9
    assert_ok(compare_array(spd, exp["body_speed"], rtol=1e-6, atol=1e-6, name="body_speed"))

def test_fig8_clean_path():
    ins = load("05_tracking", "fig8_clean_pilot", "inputs", "track_input.mat")
    inter = load("05_tracking", "fig8_clean_pilot", "intermediates", "track_clean.mat")
    exp = load("05_tracking", "fig8_clean_pilot", "outputs", "track_output.mat")
    arena = list(config.PARAMS.arena_px)
    body_raw = _orient(ins.get("body_raw", ins.get("body")))
    head_raw = _orient(ins.get("head_raw", ins.get("head")))
    bc = tracking.clean_track(body_raw, arena)
    hc = tracking.clean_track(head_raw, arena)
    assert_ok(compare_array(bc, inter["body_clean"], rtol=1e-9, atol=1e-9, name="body_clean"))
    assert_ok(compare_array(hc, inter["head_clean"], rtol=1e-9, atol=1e-9, name="head_clean"))
    body = tracking.lowpass_jitter(bc)
    assert_ok(compare_array(body, exp["body"], rtol=1e-6, atol=1e-6, name="body"))
    spd = tracking.compute_speed(body)
    assert_ok(compare_array(spd, exp["body_speed"], rtol=1e-6, atol=1e-6, name="body_speed"))
