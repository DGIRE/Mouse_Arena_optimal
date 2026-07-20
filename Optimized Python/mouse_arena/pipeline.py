"""pipeline — Python equivalent of MATLAB RUN_ALL.m.

Fully-automatic driver: Stage-1 import (s1a-s1e) then Stage-2 figures
(make_fig1-8). Each step is independent and wrapped so a missing dataset skips
only its own figure (mirrors RUN_ALL's try/catch run_safe). Edit paths via
config / the `paths` argument; the numeric components are validated against the
golden fixtures (see VALIDATION_REPORT.md).

Reference: Tariq et al. (2021), eNeuro 8(1) ENEURO.0285-20.2020.
"""
from __future__ import annotations
import traceback

from . import config
from .stage1 import (
    s1a_import_pulses, s1b_import_frequency, s1c_import_spatial,
    s1d_import_calcium_OB, s1e_import_behavior,
)
from .figures import (
    make_fig1, make_fig2, make_fig3, make_fig4,
    make_fig5, make_fig6, make_fig7, make_fig8,
)

STAGE1 = [
    ("s1a_import_pulses", s1a_import_pulses),
    ("s1b_import_frequency", s1b_import_frequency),
    ("s1c_import_spatial", s1c_import_spatial),
    ("s1d_import_calcium_OB", s1d_import_calcium_OB),
    ("s1e_import_behavior", s1e_import_behavior),
]
STAGE2 = [
    ("make_fig1_deconv_kernel", make_fig1),
    ("make_fig2_peak_times", make_fig2),
    ("make_fig3_frequency", make_fig3),
    ("make_fig4_crosscorr", make_fig4),
    ("make_fig5_spatial_corr", make_fig5),
    ("make_fig6_calcium_OB", make_fig6),
    ("make_fig7_example_trials", make_fig7),
    ("make_fig8_plume_contacts", make_fig8),
]


def _run_safe(name, fn):
    """Run one step in isolation; a failure skips only this step (RUN_ALL.run_safe)."""
    try:
        fn()
        print(f"  [ok]   {name}")
        return True
    except Exception as exc:  # noqa: BLE001 - mirror MATLAB catch-and-continue
        print(f"  [skip] {name} : {exc}")
        return False


def run_all(params=None, paths=None):
    """Import every dataset (Stage 1) and regenerate every figure (Stage 2).

    Steps are independent; a missing dataset skips only its own figure. Returns a
    dict of per-step ok/skip status. Provide `paths` to point at local data;
    numeric equivalence to the MATLAB is proven per-component by the harness.
    """
    params = params or config.get_params()
    print(f"=== Tariq 2020 reconstruction (Python) :: lighting={params.lighting} ===")
    status = {}
    print("--- STAGE 1: import ---")
    for name, mod in STAGE1:
        status[name] = _run_safe(name, lambda m=mod: m.run(params=params, paths=paths))
    print("--- STAGE 2: figures ---")
    for name, mod in STAGE2:
        status[name] = _run_safe(name, lambda m=mod: getattr(m, "run", m.compute)(params=params))
    print("=== done ===")
    return status


if __name__ == "__main__":
    run_all()
