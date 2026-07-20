import json, os
from mouse_arena import config
from conftest import FIX, sc

def test_params_match_fixture():
    with open(os.path.join(FIX,"00_params","params","outputs","params.json")) as f:
        exp = json.load(f)
    p = config.PARAMS
    assert p.Fs == exp["Fs"]
    assert p.sentinel == exp["sentinel"]
    assert p.skipRecords == exp["skipRecords"]
    assert p.chan_pid == exp["chan_pid"]
    assert p.chan_beh == exp["chan_beh"]
    assert p.kernel_sensorChar == exp["kernel_sensorChar"]
    assert p.kernel_behavior == exp["kernel_behavior"]
    assert list(p.arena_px) == exp["arena_px"]
    assert p.fig8_win_samples == exp["fig8_win_samples"]
    assert p.fig8_prominence_mult == exp["fig8_prominence_mult"]
    assert p.lighting == exp["lighting"]
    for k in ("win_s","min_sep_s","min_dist_px","baseline_s","reward_px","prominence_mult"):
        assert p.contact[k] == exp["contact"][k]
