import numpy as np
from mouse_arena import deconvolution as dv
from conftest import load, assert_ok, compare_array, sc

STAGE, CASE = "03_deconvolve", "case_11-24-2019_Loc1"

def _inp():
    d = load(STAGE, CASE, "inputs", "deconv_input.mat")
    return np.asarray(d["eth_raw"]).ravel(), np.asarray(d["kn"]).ravel(), sc(d["Fs"])

def test_fir_taps():
    exp = load(STAGE, CASE, "intermediates", "eth_filt.mat")["fir_coeffs"]
    taps = dv.design_lowpass_fir(500.0)
    assert np.asarray(taps).size == np.asarray(exp).size, "tap count mismatch"
    assert_ok(compare_array(taps, exp, rtol=1e-8, atol=1e-12, name="fir_coeffs"))

def test_eth_filt_intermediate():
    eth, kn, Fs = _inp()
    exp = load(STAGE, CASE, "intermediates", "eth_filt.mat")["eth_filt"]
    from scipy.signal import filtfilt
    taps = dv.design_lowpass_fir(Fs)
    got = filtfilt(taps, [1.0], eth)
    assert_ok(compare_array(got, exp, rtol=1e-6, atol=1e-8, name="eth_filt"))

def test_deconv_output():
    eth, kn, Fs = _inp()
    exp = load(STAGE, CASE, "outputs", "deconv_output.mat")
    dec, norm = dv.deconvolve_eth(eth, kn, Fs)
    assert_ok(compare_array(dec, exp["eth_deconv"], rtol=1e-4, atol=1e-6, name="eth_deconv"))
    assert_ok(compare_array(norm, exp["eth_deconv_norm"], rtol=1e-4, atol=1e-5, name="eth_deconv_norm"))
