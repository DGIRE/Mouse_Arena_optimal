import os, pytest, numpy as np
from scipy import stats
from mouse_arena import detection
from conftest import FIX, load, assert_ok, compare_array, sc, datamat_available

STAGE = "07_fig8"

def test_matlab_kstest2_p_formula():
    """H9: MATLAB kstest2 asymptotic p (Stephens-corrected) reproduced to ~1e-15."""
    dd = load(STAGE, "population_ks", "outputs", "fig8_ks_distributions.mat")
    res = load(STAGE, "population_ks", "outputs", "fig8_ks_result.mat")["ks_result"]
    for nm, a, b in [("head","preH","postH"), ("body","preB","postB")]:
        A = np.asarray(dd[a]).ravel(); B = np.asarray(dd[b]).ravel()
        A = A[np.isfinite(A)]; B = B[np.isfinite(B)]
        D, p = detection.ks_2samp_matlab(A, B)
        assert abs(D - sc(res[f"{nm}_stat"])) < 1e-9, f"{nm} stat"
        assert abs(p - sc(res[f"{nm}_p"])) < 1e-6, f"{nm} p: got {p} exp {sc(res[nm+'_p'])}"

@pytest.mark.skipif(not datamat_available(),
                    reason="DATA_MAT.mat not in cloud (242MB did not cross device bridge); run locally")
def test_fig8_population_end_to_end():
    from mouse_arena.figures import make_fig8
    from mouse_arena import config
    p = config.get_params()
    dm_path = os.path.join(FIX, "06_data_mat", "data_mat", "outputs", "DATA_MAT.mat")
    out = make_fig8.compute(dm_path, params=p, seed=0)
    exp_res = load(STAGE, "population_ks", "outputs", "fig8_ks_result.mat")["ks_result"]
    exp_peri = load(STAGE, "population_ks", "outputs", "fig8_peri_contact.mat")
    assert int(out["n_contacts"]) == int(sc(exp_res["n_contacts"]))
    assert int(out["n_trials"]) == int(sc(exp_res["n_trials"]))
    assert_ok(compare_array(out["Emat"], exp_peri["Emat"], rtol=1e-6, atol=1e-6, name="Emat"))
    assert_ok(compare_array(out["Hmat"], exp_peri["Hmat"], rtol=1e-6, atol=1e-6, name="Hmat"))
    assert_ok(compare_array(out["Bmat"], exp_peri["Bmat"], rtol=1e-6, atol=1e-6, name="Bmat"))
    assert abs(out["head_p"] - sc(exp_res["head_p"])) < 1e-6
    assert abs(out["body_p"] - sc(exp_res["body_p"])) < 1e-6
