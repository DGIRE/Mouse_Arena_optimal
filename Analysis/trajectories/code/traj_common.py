r"""traj_common.py -- single source of truth for the Trajectory analysis geometry,
encounter detection and clock alignment. Imports the validated Plume-locations
plume_common (clean_track advancing-reference de-jump = LESSONS rule 1, group_of,
pooled_dejump_Q, align_signal, mad). All per-frame geometry is evaluated on the
HEAD clock after cleaning both tracks and interpolating body -> head.

Run directly for self-checks. Interpreter: "$AR_PY".
"""
from __future__ import annotations

import sys
import numpy as np

# validated shared primitives from the Plume-locations run
sys.path.insert(0, r"C:\Projects\Repos\Mouse Arena\Analysis\Plume locations\code")
import plume_common as pc  # noqa: E402

VERSION = "traj_common/1.0"
SEED = pc.SEED  # 1234
ARENA = pc.ARENA
REFRACTORY_S = 0.20
K_SCAN = (5, 6, 8, 10)
QUIET_FPR_MAX = 0.05          # /s
MIN_AXIS_PX = 1.0             # ‖head-body‖ and ‖S-p‖ floor (D2/D3)

# re-exports for convenience
group_of = pc.group_of
clean_track = pc.clean_track
pooled_dejump_Q = pc.pooled_dejump_Q
align_signal = pc.align_signal
mad = pc.mad
endpoint_of = pc.endpoint_of


# ----------------------------------------------------------------- interpolation
def interp_body_to_head(head_time, body_time, body_xy):
    """Bring the (cleaned) body track onto the head clock (D1/§3.3). Default
    np.interp edge behaviour (clamp) for position; never resample the reverse way."""
    head_time = np.asarray(head_time, float)
    body_time = np.asarray(body_time, float)
    body_xy = np.asarray(body_xy, float)
    bx = np.interp(head_time, body_time, body_xy[:, 0])
    by = np.interp(head_time, body_time, body_xy[:, 1])
    return np.column_stack([bx, by])


# --------------------------------------------------------------------- geometry
def body_axis_u(head_xy, body_h):
    """Unit body-axis vector from body to head (D2). Returns (u (N,2), valid mask
    where ‖head-body‖ >= MIN_AXIS_PX)."""
    d = np.asarray(head_xy, float) - np.asarray(body_h, float)
    n = np.linalg.norm(d, axis=1)
    valid = np.isfinite(n) & (n >= MIN_AXIS_PX)
    u = np.full_like(d, np.nan)
    u[valid] = d[valid] / n[valid, None]
    return u, valid


def to_source_s(body_h, S):
    """Unit vector from the animal (body) to the source S (D3). Returns (s, valid)."""
    S = np.asarray(S, float).reshape(2)
    d = S[None, :] - np.asarray(body_h, float)
    n = np.linalg.norm(d, axis=1)
    valid = np.isfinite(n) & (n >= MIN_AXIS_PX)
    s = np.full_like(d, np.nan)
    s[valid] = d[valid] / n[valid, None]
    return s, valid


def angle_theta(u, s):
    """Absolute unsigned angle in degrees between u and s, in [0,180] (D4). NaN
    where either vector is undefined."""
    dot = np.sum(np.asarray(u, float) * np.asarray(s, float), axis=1)
    dot = np.clip(dot, -1.0, 1.0)
    return np.degrees(np.arccos(dot))


def distance_to_source(p, S):
    """Euclidean distance from p (N,2) to the source S (D8/3.8)."""
    S = np.asarray(S, float).reshape(2)
    p = np.asarray(p, float)
    return np.hypot(p[:, 0] - S[0], p[:, 1] - S[1])


def tortuosity(path_xy):
    """path_length/straight_line on a cleaned track (D6). straight_line floored at
    1 px. Returns (tortuosity, path_length, straight_line)."""
    p = np.asarray(path_xy, float)
    if p.shape[0] < 2:
        return np.nan, 0.0, np.nan
    steps = np.linalg.norm(np.diff(p, axis=0), axis=1)
    path_length = float(np.nansum(steps))
    straight = float(np.hypot(p[-1, 0] - p[0, 0], p[-1, 1] - p[0, 1]))
    if straight < 1.0:
        return np.nan, path_length, straight
    return path_length / straight, path_length, straight


# ------------------------------------------------------------- encounter onsets
def detect_onsets(sig, time, thresh, refractory_s=REFRACTORY_S):
    """Upward threshold-crossing ONSETS (D5): index i where sig[i-1] < thresh and
    sig[i] >= thresh. A refractory gap suppresses onsets within refractory_s of the
    previous accepted onset. NaN treated as below threshold. Returns onset indices
    (sorted). Deterministic; time strictly increasing seconds."""
    s = np.asarray(sig, float)
    t = np.asarray(time, float)
    below = ~(s >= thresh)          # NaN -> True (below)
    cross = np.nonzero(below[:-1] & (s[1:] >= thresh))[0] + 1
    if cross.size == 0:
        return np.array([], int)
    accepted = []
    last_t = -np.inf
    for i in cross:
        if t[i] - last_t >= refractory_s:
            accepted.append(i)
            last_t = t[i]
    return np.asarray(accepted, int)


def quiet_baseline_mask(ethd_h, head_source_dist):
    """Quiet, far-from-source baseline (§3.6/D5): head-source distance > this trial's
    80th percentile AND ethdeconv below this trial's median. NaNs excluded."""
    ethd_h = np.asarray(ethd_h, float)
    d = np.asarray(head_source_dist, float)
    ok = np.isfinite(ethd_h) & np.isfinite(d)
    if ok.sum() == 0:
        return np.zeros_like(ethd_h, bool)
    d80 = np.percentile(d[ok], 80)
    med = np.median(ethd_h[ok])
    return ok & (d > d80) & (ethd_h < med)


def calibrate_encounter_threshold(quiet_segments):
    """k-scan calibration to a physically meaningful FPR (LESSONS rule 3).
    quiet_segments: list of (sig, time) arrays = each trial's quiet-baseline samples
    (time in seconds). threshold = k * MAD(pooled quiet sig); pick the SMALLEST k in
    K_SCAN whose pooled quiet-baseline onset FPR <= QUIET_FPR_MAX. Returns dict with
    k, threshold, fpr, mad, and the full k-scan table.
    """
    vals = np.concatenate([np.asarray(s, float)[np.isfinite(s)]
                           for s, _ in quiet_segments if len(s)]) if quiet_segments else np.array([])
    m = mad(vals) if vals.size else np.nan
    total_dur = 0.0
    for s, t in quiet_segments:
        t = np.asarray(t, float)
        if t.size >= 2:
            total_dur += float(t[-1] - t[0])
    scan = []
    chosen = None
    for k in K_SCAN:
        thr = k * m
        n_onsets = 0
        for s, t in quiet_segments:
            if len(s) >= 2:
                n_onsets += len(detect_onsets(s, t, thr))
        fpr = n_onsets / total_dur if total_dur > 0 else np.inf
        scan.append({"k": k, "threshold": float(thr), "fpr_per_s": float(fpr),
                     "n_onsets": int(n_onsets)})
        if chosen is None and fpr <= QUIET_FPR_MAX:
            chosen = {"k": k, "threshold": float(thr), "fpr_per_s": float(fpr)}
    if chosen is None:  # none met target -> use the strictest (largest k)
        chosen = {"k": K_SCAN[-1], "threshold": float(K_SCAN[-1] * m),
                  "fpr_per_s": scan[-1]["fpr_per_s"], "fallback": True}
    chosen["mad_quiet"] = float(m)
    chosen["total_quiet_dur_s"] = float(total_dur)
    chosen["k_scan"] = scan
    return chosen


def frac_above(sig, thresh):
    """Fraction of finite samples of sig exceeding thresh (context, 3.7)."""
    s = np.asarray(sig, float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return np.nan
    return float(np.mean(s > thresh))


# ------------------------------------------------------------------- self-check
def _selfcheck():
    np.random.seed(SEED)
    pc._selfcheck()  # reuse the validated primitives' self-check

    # angle convention: facing source -> ~0; facing away -> ~180; orthogonal -> 90
    u = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    s = np.array([[1.0, 0.0], [-1.0, 0.0], [1.0, 0.0]])
    th = angle_theta(u, s)
    assert abs(th[0] - 0) < 1e-6 and abs(th[1] - 180) < 1e-6 and abs(th[2] - 90) < 1e-6, th

    # body_axis / to_source with a concrete geometry: body at origin, head east,
    # source east -> theta 0
    body = np.array([[0.0, 0.0]]); head = np.array([[10.0, 0.0]]); S = np.array([100.0, 0.0])
    uu, vu = body_axis_u(head, body); ss, vs = to_source_s(body, S)
    assert vu[0] and vs[0]
    assert abs(angle_theta(uu, ss)[0] - 0) < 1e-6

    # undefined axis when head==body
    _, vbad = body_axis_u(np.array([[0.0, 0.0]]), np.array([[0.3, 0.4]]))  # norm 0.5 <1
    assert not vbad[0]

    # tortuosity: straight line -> 1.0; detour -> >1
    straight = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    t1, pl, sl = tortuosity(straight)
    assert abs(t1 - 1.0) < 1e-9 and abs(pl - 3.0) < 1e-9
    detour = np.array([[0.0, 0.0], [0.0, 5.0], [3.0, 5.0], [3.0, 0.0]])  # path 13, straight 3
    t2, _, _ = tortuosity(detour)
    assert abs(t2 - 13.0 / 3.0) < 1e-9, t2

    # onset detector: one crossing at i=2, refractory merges a re-cross within gap
    sig = np.array([0, 0, 1.0, 1.0, 0, 1.0, 0, 0, 1.0])
    t = np.arange(len(sig)) * 0.05  # 20 Hz
    on = detect_onsets(sig, t, thresh=0.5, refractory_s=0.20)
    # crossings at i=2 (0->1), i=5 (0->1), i=8 (0->1); refractory 0.2s=4 samples:
    # i=2 accepted (t=0.10); i=5 t=0.25 -> 0.15<0.2 suppressed; i=8 t=0.40 accepted
    assert on.tolist() == [2, 8], on.tolist()

    # interp body->head clamps at edges, linear inside
    bh = interp_body_to_head([0.0, 0.5, 1.0], [0.0, 1.0], np.array([[0.0, 0.0], [10.0, 20.0]]))
    assert abs(bh[1, 0] - 5.0) < 1e-9 and abs(bh[1, 1] - 10.0) < 1e-9

    # calibrate: pure-noise quiet segments -> large k drives FPR to ~0
    rng = np.random.default_rng(SEED)
    segs = [(rng.normal(0, 1, 5000), np.arange(5000) * 0.002) for _ in range(3)]
    cal = calibrate_encounter_threshold(segs)
    assert cal["k"] in K_SCAN and cal["fpr_per_s"] <= QUIET_FPR_MAX + 1e-9 or "fallback" in cal

    print("traj_common self-check: PASS")


if __name__ == "__main__":
    _selfcheck()
