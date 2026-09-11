r"""reactions2_common.py -- single source of truth for the Selective Sampling-Bout
analysis. Reuses plume_common (clean_track advancing-ref de-jump, mad, group_of,
pooled_dejump_Q, align_signal) and reactions_common (speed_savgol, interp_xy_to_head,
baseline_subtract_ethanol, load_odor_field, is_in_odor, peri_event_matrix, robust_sd)
-- no re-implementation (rule 15). Adds the TRANSLATION-INVARIANT head-body bearing
kinematic (rule 12) and the rare pause+cast "sampling bout" detector.

Everything on the HEAD clock. Run directly for self-checks. Interpreter: "$AR_PY".
"""
from __future__ import annotations

import sys
import numpy as np
from scipy.signal import savgol_filter, find_peaks

sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import plume_common as pc  # noqa: E402
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\reactions\code")
import reactions_common as rc  # noqa: E402

VERSION = "reactions2_common/1.0"
SEED = pc.SEED  # 1234
ARENA = pc.ARENA

# defaults (D3-D6)
SG_WIN, SG_POLY = 7, 2
V_PAUSE_PCT = 25.0
TAU_PAUSE = 0.30
DPHI_MIN = 40.0
OMEGA_PCT = 90.0
T_MERGE = 0.50
INCIDENTAL_REFRACTORY = 0.30
ODOR_CUTOFF = rc.ODOR_CUTOFF  # 0.001

# re-exports
clean_track = pc.clean_track
mad = pc.mad
group_of = pc.group_of
pooled_dejump_Q = pc.pooled_dejump_Q
align_signal = pc.align_signal
endpoint_of = pc.endpoint_of
interp_xy_to_head = rc.interp_xy_to_head
speed_savgol = rc.speed_savgol
baseline_subtract_ethanol = rc.baseline_subtract_ethanol
load_odor_field = rc.load_odor_field
is_in_odor = rc.is_in_odor
peri_event_matrix = rc.peri_event_matrix
robust_sd = rc.robust_sd


# ------------------------------------------------------- translation-invariant kinematic
def bearing_phi(head_xy, body_h):
    """Head-relative-to-body bearing phi(t) in unwrapped DEGREES (D2). Translation-
    invariant: depends only on (head - body), not on absolute position."""
    d = np.asarray(head_xy, float) - np.asarray(body_h, float)
    return np.degrees(np.unwrap(np.arctan2(d[:, 1], d[:, 0])))


def angular_speed_omega(phi, dt, win=SG_WIN, poly=SG_POLY):
    """|d phi / dt| in deg/s, smoothed via Savitzky-Golay (differentiate after
    smoothing). NaN-safe length handling."""
    phi = np.asarray(phi, float)
    n = phi.size
    if n < max(win, poly + 2):
        return np.full(n, np.nan)
    w = win if win % 2 == 1 else win + 1
    if w > n:
        w = n if n % 2 == 1 else n - 1
    return np.abs(savgol_filter(phi, w, poly, deriv=1, delta=dt))


# --------------------------------------------------------------------- run helpers
def _runs_true(mask):
    """List of (start, end_exclusive) contiguous True runs in a boolean array."""
    mask = np.asarray(mask, bool)
    idx = np.nonzero(mask)[0]
    if idx.size == 0:
        return []
    splits = np.nonzero(np.diff(idx) > 1)[0]
    starts = np.r_[idx[0], idx[splits + 1]]
    ends = np.r_[idx[splits], idx[-1]] + 1
    return list(zip(starts.tolist(), ends.tolist()))


# ------------------------------------------------------------ bout detection (D3-D6)
def detect_pauses(v_com, dt, v_pause, tau_pause=TAU_PAUSE):
    """Contiguous runs where v_com < v_pause lasting >= tau_pause (D3)."""
    v = np.asarray(v_com, float)
    min_len = max(1, int(round(tau_pause / dt)))
    return [(s, e) for (s, e) in _runs_true(np.isfinite(v) & (v < v_pause)) if (e - s) >= min_len]


def detect_bouts(v_com, phi, omega, t, v_pause, omega_min,
                 tau_pause=TAU_PAUSE, dphi_min=DPHI_MIN, t_merge=T_MERGE):
    """Sampling bouts (D5) = locomotor pauses (D3) that contain a qualifying head cast
    (D4: cumulative |d phi| over the pause >= dphi_min AND peak omega in the pause >=
    omega_min). Bouts whose ONSET times are < t_merge apart are merged (keep earliest).
    Returns a list of dicts (onset_idx, peak_idx, dur_s, peak_omega, excursion_deg,
    v_com_during) sorted by onset.
    """
    phi = np.asarray(phi, float); omega = np.asarray(omega, float)
    t = np.asarray(t, float)
    raw = []
    for (s, e) in detect_pauses(v_com, np.median(np.diff(t)) if t.size > 1 else 0.01,
                                v_pause, tau_pause):
        seg_phi = phi[s:e]; seg_om = omega[s:e]
        if seg_phi.size < 2:
            continue
        excursion = float(np.nansum(np.abs(np.diff(seg_phi))))
        peak = float(np.nanmax(seg_om)) if np.any(np.isfinite(seg_om)) else 0.0
        if excursion >= dphi_min and peak >= omega_min:
            pk_idx = s + int(np.nanargmax(np.where(np.isfinite(seg_om), seg_om, -np.inf)))
            raw.append({"onset_idx": int(s), "peak_idx": pk_idx,
                        "dur_s": float(t[e - 1] - t[s]),
                        "peak_omega": peak, "excursion_deg": excursion,
                        "v_com_during": float(np.nanmean(np.asarray(v_com)[s:e]))})
    # merge by onset time
    raw.sort(key=lambda b: b["onset_idx"])
    merged = []
    last_t = -np.inf
    for b in raw:
        if t[b["onset_idx"]] - last_t >= t_merge:
            merged.append(b)
            last_t = t[b["onset_idx"]]
    return merged


def detect_incidental(v_com, omega, t, v_pause, omega_min, refractory_s=INCIDENTAL_REFRACTORY):
    """Incidental head-motion events (D7): high-omega peaks that occur WHILE MOVING
    (v_com >= v_pause) -- the contrast class (NOT sampling bouts). Same omega height /
    refractory logic. Returns peak indices."""
    omega = np.asarray(omega, float); v_com = np.asarray(v_com, float)
    dt = np.median(np.diff(np.asarray(t, float))) if t.size > 1 else 0.01
    oc = np.where(np.isfinite(omega), omega, 0.0)
    pk, _ = find_peaks(oc, height=omega_min, distance=max(1, int(round(refractory_s / dt))))
    return np.array([p for p in pk if np.isfinite(v_com[p]) and v_com[p] >= v_pause], int)


# ------------------------------------------------------------------- self-check
def _selfcheck():
    np.random.seed(SEED)
    rc._selfcheck()

    # bearing: head east of body -> ~0 deg; head north -> ~90 deg
    body = np.array([[0.0, 0.0], [0.0, 0.0]])
    head = np.array([[10.0, 0.0], [0.0, 10.0]])
    phi = bearing_phi(head, body)
    assert abs(phi[0] - 0.0) < 1e-6 and abs(((phi[1] - 90.0 + 180) % 360) - 180) < 1e-6, phi

    # constant rotation -> constant omega. head rotates at 100 deg/s, dt=0.01
    dt = 0.01
    ang = np.deg2rad(np.arange(60) * 100 * dt)  # 100 deg/s
    h = np.column_stack([10 * np.cos(ang), 10 * np.sin(ang)])
    b = np.zeros_like(h)
    ph = bearing_phi(h, b)
    om = angular_speed_omega(ph, dt)
    assert np.nanmax(np.abs(om[5:-5] - 100.0)) < 1e-3, om[5:-5][:3]

    # pause detection: v_com low for a sustained run
    v = np.r_[np.full(50, 20.0), np.full(50, 1.0), np.full(50, 20.0)]
    t = np.arange(150) * dt
    pauses = detect_pauses(v, dt, v_pause=5.0, tau_pause=0.30)
    assert len(pauses) == 1 and pauses[0][0] == 50, pauses

    # bout: a pause containing a big cast (phi sweeps 90 deg, high omega) -> 1 bout
    n = 150
    v2 = np.r_[np.full(50, 20.0), np.full(50, 1.0), np.full(50, 20.0)]
    phi2 = np.zeros(n)
    # within the pause (50:100) sweep out 90 deg and back (cumulative ~180) fast
    phi2[50:75] = np.linspace(0, 90, 25)
    phi2[75:100] = np.linspace(90, 0, 25)
    phi2[100:] = 0
    om2 = angular_speed_omega(phi2, dt)
    tt = np.arange(n) * dt
    bouts = detect_bouts(v2, phi2, om2, tt, v_pause=5.0, omega_min=50.0)
    assert len(bouts) == 1, len(bouts)
    assert bouts[0]["onset_idx"] == 50

    # a pause with NO cast (phi flat) -> 0 bouts
    bouts0 = detect_bouts(v2, np.zeros(n), np.zeros(n), tt, v_pause=5.0, omega_min=50.0)
    assert len(bouts0) == 0, len(bouts0)

    # incidental: high omega while MOVING -> detected; the paused cast is NOT incidental
    om3 = np.zeros(n); om3[20] = 300.0   # moving region (v=20)
    inc = detect_incidental(v2, om3, tt, v_pause=5.0, omega_min=100.0)
    assert 20 in inc.tolist(), inc
    om4 = np.zeros(n); om4[60] = 300.0   # paused region (v=1) -> not incidental
    inc2 = detect_incidental(v2, om4, tt, v_pause=5.0, omega_min=100.0)
    assert 60 not in inc2.tolist(), inc2

    print("reactions2_common self-check: PASS")


if __name__ == "__main__":
    _selfcheck()
