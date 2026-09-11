r"""verify_gate1.py -- INDEPENDENT Gate-1 verifier for the Nose-Sweeps analysis.

Loads data via the accessor + reactions_common ONLY (no direct aggregate h5 walking).
RE-DERIVES velocities, v_floor, R, sweep counts, and >=3 numbers per hypothesis a
different way, then compares against data/stats.json + data/sweeps.h5. Does NOT
rewrite the analysis. Read-only w.r.t. DATA. Run with "$AR_PY".
"""
from __future__ import annotations
import os, sys, json
import numpy as np
from scipy.signal import savgol_filter, find_peaks
from scipy.stats import wilcoxon, spearmanr

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions"
CODE = os.path.join(BASE, "code")
DATA = os.path.join(BASE, "data")
ACC = r"C:\Projects\Repos\Mouse Arena\DATA\code"
AGG = r"C:\Projects\Repos\Mouse Arena\DATA\Mouse Arena Aggregate Data.h5"
for d in (CODE, ACC):
    if d not in sys.path:
        sys.path.insert(0, d)

import reactions_common as rc
from mouse_arena_aggregate_io import Aggregate

SEED = 1234
POOLED = {"Loc1", "Loc2", "Loc3", "Loc4", "Loc5", "Loc6"}
ETH_SUM_WIN = (-0.5, 0.5)
H2_WIN = (-0.25, 0.25)
GRID_DT = 0.05
N_PERM = 2000
OUT = []


def log(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


# ---------- independent savgol speed (do NOT call rc; re-implement) ----------
def my_speed(xy, dt, win=7, poly=2):
    xy = np.asarray(xy, float)
    n = xy.shape[0]
    if n < win:
        return np.full(n, np.nan)
    vx = savgol_filter(xy[:, 0], win, poly, deriv=1, delta=dt)
    vy = savgol_filter(xy[:, 1], win, poly, deriv=1, delta=dt)
    return np.hypot(vx, vy)


def my_interp(head_t, src_t, src_xy):
    return np.column_stack([np.interp(head_t, src_t, src_xy[:, 0]),
                            np.interp(head_t, src_t, src_xy[:, 1])])


def process(tr, Qb, Qh, v_floor):
    head = np.asarray(tr["head"], float); body = np.asarray(tr["body"], float)
    ht = np.asarray(tr["head_time"], float); bt = np.asarray(tr["body_time"], float)
    eth = np.asarray(tr["ethanol"], float); et = np.asarray(tr["ethanol_time"], float)
    _, hc, htc = rc.clean_track(head, ht, Qh)
    _, bc, btc = rc.clean_track(body, bt, Qb)
    if hc.shape[0] < 10 or bc.shape[0] < 2:
        return None
    body_h = my_interp(htc, btc, bc)
    dt = float(np.median(np.diff(htc)))
    v_nose = my_speed(hc, dt); v_com = my_speed(body_h, dt)
    bframe = my_speed(hc - body_h, dt)
    R = v_nose / np.maximum(v_com, v_floor)
    eth_bs = rc.baseline_subtract_ethanol(eth, et)
    eth_bs_h = np.interp(htc, et, eth_bs, left=np.nan, right=np.nan)
    return dict(hc=hc, body_h=body_h, htc=htc, dt=dt, v_nose=v_nose, v_com=v_com,
                bframe=bframe, R=R, eth_bs_h=eth_bs_h)


def peri_mat(sig, t, ev, win, gd=GRID_DT):
    grid = np.arange(win[0], win[1] + 1e-9, gd)
    ev = np.atleast_1d(ev)
    M = np.full((ev.size, grid.size), np.nan)
    fin = np.isfinite(sig)
    if fin.sum() < 2:
        return grid, M
    tt, ss = t[fin], sig[fin]
    for i, e in enumerate(ev):
        M[i] = np.interp(e + grid, tt, ss, left=np.nan, right=np.nan)
    return grid, M


def main():
    stats = json.load(open(os.path.join(DATA, "stats.json")))
    swj = json.load(open(os.path.join(DATA, "sweeps.json")))

    agg = Aggregate(AGG)
    trials = agg.behavior(lighting="infrared")
    agg.close()
    log("=== ACCESSOR: %d infrared trials ===" % len(trials))
    assert len(trials) == 114

    Qb = rc.pooled_dejump_Q(trials, "body")
    Qh = rc.pooled_dejump_Q(trials, "head")
    log("dejump Q body=%.4f head=%.4f" % (Qb, Qh))

    # ---- de-jump % on real data (among box-kept) ----
    bdj_rm = bdj_box = hdj_rm = hdj_box = 0
    for tr in trials:
        _, nbbox, nbk = rc.pc.clean_counts(np.asarray(tr["body"], float),
                                        np.asarray(tr["body_time"], float), Qb)
        _, nhbox, nhk = rc.pc.clean_counts(np.asarray(tr["head"], float),
                                        np.asarray(tr["head_time"], float), Qh)
        bdj_rm += nbbox - nbk; bdj_box += nbbox
        hdj_rm += nhbox - nhk; hdj_box += nhbox
    log("de-jump removed: body=%.4f%% head=%.4f%% (must be <5%%)"
        % (100 * bdj_rm / bdj_box, 100 * hdj_rm / hdj_box))

    # ---- PASS1 v_floor (pooled v_com 10th pct) ----
    pooled = []
    proc = {}
    for k, tr in enumerate(trials):
        head = np.asarray(tr["head"], float); body = np.asarray(tr["body"], float)
        ht = np.asarray(tr["head_time"], float); bt = np.asarray(tr["body_time"], float)
        _, hc, htc = rc.clean_track(head, ht, Qh)
        _, bc, btc = rc.clean_track(body, bt, Qb)
        if hc.shape[0] < 10 or bc.shape[0] < 2:
            continue
        body_h = my_interp(htc, btc, bc)
        dt = float(np.median(np.diff(htc)))
        vc = my_speed(body_h, dt)
        pooled.append(vc[np.isfinite(vc)])
    allv = np.concatenate(pooled)
    v_floor = float(np.percentile(allv, 10.0))
    log("v_floor(10th pct pooled v_com)=%.5f  vs stored %.5f  d=%.2e"
        % (v_floor, stats["meta"]["v_floor"], v_floor - stats["meta"]["v_floor"]))

    # ---- PASS2 per-trial ----
    binding = []
    per = {}
    for k, tr in enumerate(trials):
        P = process(tr, Qb, Qh, v_floor)
        if P is None:
            continue
        end_loc = rc.group_of(tr["file_name"])
        pk_R = rc.detect_sweeps_R(P["R"], P["htc"])
        pk_b = rc.detect_sweeps_bframe(P["bframe"], P["htc"])
        binding.append(float(np.mean(P["v_com"] < v_floor)))
        per[k] = dict(P=P, end_loc=end_loc, file_name=tr["file_name"],
                      pk_R=pk_R, pk_b=pk_b, in_pooled=end_loc in POOLED)
    log("binding frac mean=%.5f vs stored %.5f"
        % (np.mean(binding), stats["meta"]["v_floor_binding_frac_pooled_mean"]))

    # ---- velocity sanity ----
    vn = np.concatenate([per[k]["P"]["v_nose"][np.isfinite(per[k]["P"]["v_nose"])]
                         for k in per if per[k]["in_pooled"]])
    vc = np.concatenate([per[k]["P"]["v_com"][np.isfinite(per[k]["P"]["v_com"])]
                         for k in per if per[k]["in_pooled"]])
    log("v_nose med=%.2f p90=%.2f | v_com med=%.2f p90=%.2f px/s (sane tens)"
        % (np.median(vn), np.percentile(vn, 90), np.median(vc), np.percentile(vc, 90)))

    # ---- boundary: re-derive R-sweep count for a few trials vs h5 ----
    import h5py
    h5 = os.path.join(DATA, "sweeps.h5")
    with h5py.File(h5, "r") as f:
        for k in [9, 10, 37]:
            if k not in per:
                continue
            stored = int(f["trials"][f"{k:03d}"].attrs["sweep_count"])
            mine = int(per[k]["pk_R"].size)
            log("BOUNDARY trial %d: my R-sweep count=%d  stored=%d  diff=%d"
                % (k, mine, stored, mine - stored))

    # ============ build pooled per-sweep & per-trial arrays my way ============
    pooled_ks = sorted([k for k in per if per[k]["in_pooled"]])
    log("pooled trials: %d (expect 105)" % len(pooled_ks))

    odor_cache = {}
    per_sweep = []
    h1b_obs = {}; h1b_null = {}
    h2_during_R = {}; h2_during_b = {}; h2_base = {}
    f_sweep_d = {}; f_occ_d = {}; h3_stat_d = {}
    sweep_counts = {}; sweep_rates = {}

    for k in pooled_ks:
        P = per[k]["P"]; el = per[k]["end_loc"]
        if el not in odor_cache:
            odor_cache[el] = rc.load_odor_field(el)
        field = odor_cache[el]
        htc = P["htc"]; R = P["R"]; v_com = P["v_com"]; eth_bs_h = P["eth_bs_h"]
        pk_R = per[k]["pk_R"]; pk_b = per[k]["pk_b"]
        dur = float(htc[-1] - htc[0])
        sweep_counts[k] = pk_R.size
        sweep_rates[k] = pk_R.size / dur if dur > 0 else 0.0
        stR = htc[pk_R] if pk_R.size else np.array([])
        stB = htc[pk_b] if pk_b.size else np.array([])

        # per-sweep summed eth + in_odor
        _, Me = peri_mat(eth_bs_h, htc, stR, ETH_SUM_WIN)
        occ = rc.is_in_odor(field, P["hc"][:, 0], P["hc"][:, 1]) if field is not None else np.zeros(P["hc"].shape[0], bool)
        f_occ_d[k] = float(np.mean(occ))
        s_in = []
        for j, i in enumerate(pk_R):
            row = Me[j]
            summ = float(np.nansum(row)) if np.isfinite(row).any() else np.nan
            mn = float(np.nanmean(row)) if np.isfinite(row).any() else np.nan
            ino = bool(rc.is_in_odor(field, [P["hc"][i, 0]], [P["hc"][i, 1]])[0]) if field is not None else False
            s_in.append(ino)
            per_sweep.append(dict(k=k, R=float(R[i]), summed=summ, mean=mn, in_odor=ino,
                                  v_com=float(v_com[i])))
        f_sweep_d[k] = float(np.mean(s_in)) if s_in else np.nan

        # H1b observed/null
        sm = np.array([per_sweep[-len(s_in) + j]["mean"] for j in range(len(s_in))]) if s_in else np.array([])
        h1b_obs[k] = float(np.nanmean(sm)) if sm.size else np.nan
        if pk_R.size and dur > 0:
            rng = np.random.default_rng(SEED)
            rt = rng.uniform(htc[0], htc[-1], size=(N_PERM, pk_R.size))
            grid = np.arange(ETH_SUM_WIN[0], ETH_SUM_WIN[1] + 1e-9, GRID_DT)
            fin = np.isfinite(eth_bs_h); tt, ss = htc[fin], eth_bs_h[fin]
            pm = np.empty(N_PERM)
            for pi in range(N_PERM):
                q = rt[pi][:, None] + grid[None, :]
                vals = np.interp(q.ravel(), tt, ss, left=np.nan, right=np.nan).reshape(q.shape)
                with np.errstate(invalid="ignore"):
                    evm = np.nanmean(vals, axis=1)
                pm[pi] = np.nanmean(evm) if np.isfinite(evm).any() else np.nan
            h1b_null[k] = float(np.nanmean(pm))
        else:
            h1b_null[k] = np.nan

        # H2 during v_com (R-set & bframe)
        def during(st):
            if st.size == 0:
                return np.nan
            _, Mv = peri_mat(v_com, htc, st, H2_WIN)
            v = Mv[np.isfinite(Mv)]
            return float(np.mean(v)) if v.size else np.nan
        h2_during_R[k] = during(stR)
        h2_during_b[k] = during(stB)
        h2_base[k] = float(np.nanmedian(v_com))

        # H3 permutation null
        if pk_R.size and P["hc"].shape[0] > 0:
            rng = np.random.default_rng(SEED)
            oi = occ.astype(float)
            draws = rng.integers(0, P["hc"].shape[0], size=(N_PERM, pk_R.size))
            h3_stat_d[k] = float(f_sweep_d[k] - np.mean(oi[draws].mean(axis=1)))
        else:
            h3_stat_d[k] = np.nan

    # ---- H1a prevalence ----
    rates = np.array([sweep_rates[k] for k in pooled_ks])
    counts = np.array([sweep_counts[k] for k in pooled_ks], float)
    log("H1a: rate median=%.4f (stored %.4f) | count median=%.1f (stored %.1f) total=%d (stored %d)"
        % (np.median(rates), stats["H1a_prevalence"]["sweep_rate_per_s"]["median"],
           np.median(counts), stats["H1a_prevalence"]["median_sweeps_per_trial"],
           int(counts.sum()), stats["H1a_prevalence"]["total_sweeps_pooled"]))

    # ---- H1b Wilcoxon ----
    obs = np.array([h1b_obs[k] for k in pooled_ks])
    nul = np.array([h1b_null[k] for k in pooled_ks])
    m = np.isfinite(obs) & np.isfinite(nul)
    st, p = wilcoxon(obs[m], nul[m], alternative="greater", zero_method="wilcox")
    log("H1b Wilcoxon p=%.5f (stored %.5f) | med obs=%.5f null=%.5f"
        % (p, stats["H1b_peri_sweep_odor"]["p_value"], np.nanmedian(obs), np.nanmedian(nul)))

    # ---- H1c Spearman ----
    Rp = np.array([s["R"] for s in per_sweep]); sm = np.array([s["summed"] for s in per_sweep])
    mm = np.isfinite(Rp) & np.isfinite(sm)
    rho, pv = spearmanr(Rp[mm], sm[mm])
    log("H1c Spearman rho=%.5f (stored %.5f) n=%d (stored %d) p=%.2e"
        % (rho, stats["H1c_spearman"]["rho"], mm.sum(), stats["H1c_spearman"]["n_sweeps"], pv))

    # ---- H1 amplitude: frac mean eth > 0.01 ----
    me = np.array([s["mean"] for s in per_sweep]); me = me[np.isfinite(me)]
    log("H1 amp: frac peri-eth mean>0.01=%.4f (stored %.4f) | median=%.5f (floor 4e-4)"
        % (np.mean(me > 0.01), stats["H1_amplitude_check"]["frac_sweeps_peri_eth_mean_gt_0.01"],
           np.median(me)))

    # ---- H2 R-set & bframe Wilcoxon ----
    hR = np.array([h2_during_R[k] for k in pooled_ks])
    hB = np.array([h2_during_b[k] for k in pooled_ks])
    hbase = np.array([h2_base[k] for k in pooled_ks])
    mR = np.isfinite(hR) & np.isfinite(hbase)
    sR, pR = wilcoxon(hR[mR], hbase[mR], alternative="less", zero_method="wilcox")
    mB = np.isfinite(hB) & np.isfinite(hbase)
    sB, pB = wilcoxon(hB[mB], hbase[mB], alternative="less", zero_method="wilcox")
    log("H2 R-set during<base p=%.4f (stored %.4f) | med during=%.3f base=%.3f"
        % (pR, stats["H2"]["primary_Rset_vs_median"]["p_value"],
           np.nanmedian(hR), np.nanmedian(hbase)))
    log("H2 bframe(headline) during<base p=%.4f (stored %.4f) | med during=%.3f"
        % (pB, stats["H2"]["HEADLINE_numerator_only_bframe"]["p_value"], np.nanmedian(hB)))

    # ---- H3 ----
    fs = np.array([f_sweep_d[k] for k in pooled_ks])
    fo = np.array([f_occ_d[k] for k in pooled_ks])
    m3 = np.isfinite(fs) & np.isfinite(fo)
    s3, p3 = wilcoxon(fs[m3], fo[m3], alternative="greater", zero_method="wilcox")
    log("H3 f_sweep>f_occ p=%.4f (stored %.4f) | med f_sweep=%.4f f_occ=%.4f | frac enriched=%.4f (stored %.4f)"
        % (p3, stats["H3"]["test_f_sweep_gt_f_occ"]["p_value"],
           np.nanmedian(fs), np.nanmedian(fo), np.mean(fs[m3] > fo[m3]),
           stats["H3"]["frac_trials_enriched"]))

    # confirm one trial's f_sweep/f_occ vs stored per-trial
    tr_map = {t["file_name"]: t for t in swj["trials"]}
    for k in pooled_ks[:1]:
        fn = per[k]["file_name"]
        stored = tr_map[fn]
        log("H3 trial %s: my f_sweep=%.5f stored=%.5f | my f_occ=%.5f stored=%.5f"
            % (fn[:30], f_sweep_d[k], stored["f_sweep"], f_occ_d[k], stored["f_occ"]))

    # ---- anotherLoc excluded ----
    aloc = [k for k in per if per[k]["end_loc"] == "anotherLoc"]
    log("anotherLoc trials=%d (excluded from pooled) | pooled=%d" % (len(aloc), len(pooled_ks)))

    # ---- eth scale sanity (raw ~[-0.28,1.0], NOT ethdeconv ~0.14) ----
    ebs = np.concatenate([per[k]["P"]["eth_bs_h"][np.isfinite(per[k]["P"]["eth_bs_h"])]
                          for k in pooled_ks[:5]])
    log("eth_bs sample range [%.3f, %.3f] (raw scale, not ethdeconv 0.14)"
        % (np.nanmin(ebs), np.nanmax(ebs)))

    log("=== VERIFY DONE ===")


if __name__ == "__main__":
    main()
