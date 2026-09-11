# -*- coding: utf-8 -*-
"""Build H1 DOCX report strictly from saved result objects (numbers injected, none typed).
Honest framing: H1 is NOT supported (null). Direction before significance; lead with
magnitude/rate, not p-values."""
import json
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\reactions"
DATA = BASE + r"\data"
FIGS = BASE + r"\reports\figures"
OUT = BASE + r"\reports\H1 - nose sweeps and odor.docx"

with open(DATA + r"\stats.json") as fh:
    S = json.load(fh)
with open(DATA + r"\_f2b_plot_stats.json") as fh:
    F2 = json.load(fh)

M = S["meta"]
A = S["H1a_prevalence"]
B = S["H1b_peri_sweep_odor"]
C = S["H1c_spearman"]
AMP = S["H1_amplitude_check"]
F1A = S["F1A_peri_eth"]
vp = M["velocity_pct"]
win = M["windows"]

# ---- numeric shortcuts (all injected) ----
rate_med = A["sweep_rate_per_s"]["median"]
rate_mean = A["sweep_rate_per_s"]["mean"]
rate_min = A["sweep_rate_per_s"]["min"]
rate_max = A["sweep_rate_per_s"]["max"]
cnt_med = A["sweep_count_per_trial"]["median"]
cnt_mean = A["sweep_count_per_trial"]["mean"]
cnt_min = A["sweep_count_per_trial"]["min"]
cnt_max = A["sweep_count_per_trial"]["max"]
n_pooled = A["total_sweeps_pooled"]
n_trials = A["n_trials"]

b_p = B["p_value"]
b_stat = B["statistic"]
b_obs = B["median_observed"]
b_null = B["median_null"]

c_rho = C["rho"]
c_p = C["p_value"]
c_lo, c_hi = C["ci95"]
c_n = C["n_sweeps"]

amp_med = AMP["peri_eth_mean"]["median"]
amp_p90 = AMP["peri_eth_mean"]["p90"]
amp_frac = AMP["frac_sweeps_peri_eth_mean_gt_0.01"]
amp_range = AMP["real_range_ref"]
amp_floor = AMP["noise_floor_ref"]

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)


def H(text, level=1):
    doc.add_heading(text, level=level)


def P(text, bold=False, italic=False, size=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = RGBColor(*color)
    return p


def bullet(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
        p.add_run(text)
    else:
        p.add_run(text)
    return p


# ================= Title =================
title = doc.add_heading("H1 — Nose Sweeps and Odor", level=0)
sub = P("Are nose sweeps prevalent AND temporally/quantitatively associated with ethanol?",
        italic=True, color=(0x55, 0x55, 0x55))
verdict = doc.add_paragraph()
vr = verdict.add_run("Verdict: H1 is NOT supported (null result).")
vr.bold = True
vr.font.size = Pt(13)
vr.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)

# ================= Goal + Hypothesis =================
H("1. Goal and Hypotheses", 1)
P("Goal: test whether discrete nose sweeps are (a) prevalent, (b) temporally locked to "
  "elevated local ethanol, and (c) larger when local odor is stronger — the signature "
  "expected if sweeps are an odor-guided search behavior.")
P("H1 (alternative): nose sweeps are prevalent AND temporally associated with ethanol; "
  "peri-sweep baseline-subtracted ethanol exceeds a matched-count random-time null, and "
  "sweep magnitude R correlates positively with local odor.", bold=True)
P("H0 (null): peri-sweep ethanol is at or below the time-shuffled null, and sweep "
  "magnitude R is independent of local ethanol (Spearman rho not positive / CI includes 0).")
P("Pre-registered acceptance rule (PLAN.md sec.4): accept H1 iff peri-sweep ethanol > null "
  "AND rho > 0 with the 95% CI excluding 0. Both conditions must hold.", italic=True)

# ================= Methods =================
H("2. Methods", 1)
P("Pipeline and accessor.", bold=True)
P("Trajectories were loaded via the project data accessor and processed with the shared "
  "reactions_common library ({ver}). All randomness used a fixed seed ({seed}); "
  "{nperm} permutations for null construction and {nboot} bootstraps for confidence "
  "intervals.".format(ver=M["VERSION"], seed=M["seed"],
                       nperm=M["n_permutations"], nboot=M["n_bootstrap"]))
P("Interpreter: the project virtual environment "
  "(vras\\Scripts\\python.exe), matplotlib in headless (Agg) mode.")

P("Kinematics.", bold=True)
P("The nose was taken as the head keypoint and the COM as the body keypoint, both "
  "resampled onto the head clock (monotonic interpolation, never reversed). Per-axis "
  "velocities were computed with a Savitzky-Golay filter (window 7 frames ~70 ms, "
  "polynomial order 2, first derivative, delta = frame dt). De-jump cleaning removed "
  "{hd:.2%} of head and {bd:.2%} of body samples. Median speeds: v_nose {vn50:.1f} px/s "
  "(90th pct {vn90:.1f}), v_com {vc50:.1f} px/s (90th pct {vc90:.1f}).".format(
      hd=M["dejump_removed_frac_head"], bd=M["dejump_removed_frac_body"],
      vn50=vp["v_nose_px_s"]["50"], vn90=vp["v_nose_px_s"]["90"],
      vc50=vp["v_com_px_s"]["50"], vc90=vp["v_com_px_s"]["90"]))

P("Sweep magnitude R and floor.", bold=True)
P("Sweep magnitude was defined as R = v_nose / max(v_com, v_floor), where v_floor = "
  "{vf:.3f} px/s (the 10th percentile of pooled v_com) guards against divide-by-near-zero "
  "when the animal is stationary. The floor was binding on {bf:.1%} of pooled samples "
  "(mean fraction across trials).".format(
      vf=M["v_floor"], bf=M["v_floor_binding_frac_pooled_mean"]))

P("Sweep detector.", bold=True)
P("Sweeps were detected on the R time series with scipy find_peaks: height >= 1.5, "
  "prominence >= 0.5, refractory (min inter-peak distance) 0.30 s. The prominence/height "
  "thresholds are editable; because R is high whenever the nose moves and the body does "
  "not, the detector fires frequently (see Caveats).")

P("Baseline-subtracted ethanol and peri-sweep windows.", bold=True)
P("Local ethanol was baseline-subtracted on the RAW scale by subtracting a rolling "
  "10th-percentile computed over a W = 20 s window (raw minus rolling floor). Peri-sweep "
  "signals were sampled on a {gdt:.2f} s grid over the peri window {peri} s (used for the "
  "F1 curves); the summed-odor statistic integrates baseline-subtracted ethanol over the "
  "{esum} s window around each sweep peak.".format(
      gdt=win["grid_dt"], peri=win["peri"], esum=win["eth_sum"]))

P("Unit of analysis and pooling.", bold=True)
P("The unit of analysis for per-trial tests is the trial. Location-pooled analyses use "
  "the pooled Loc1-6 set: n = {ntp} trials (of {npr} processed), {nsw:,} pooled sweeps. "
  "The 'anotherLoc' condition is excluded from the pooled set.".format(
      ntp=M["n_trials_pooled"], npr=M["n_trials_processed"], nsw=M["n_sweeps_pooled"]))
P("Tests: (a) prevalence = sweep rate (sweeps/s) and count per trial; (b) paired Wilcoxon "
  "of per-trial peri-sweep ethanol vs a matched-count random-time null (observed > null); "
  "(c) Spearman rho(R@peak, summed peri-sweep ethanol), one point per sweep, CI "
  "bootstrapped over trials. No family-wise correction is applied across H1-H3 "
  "(per-test CIs only).")

# ================= Results =================
H("3. Results", 1)

P("3.1 Prevalence — lead with rate, not count.", bold=True)
P("Sweeps are numerically abundant but the RATE shows why that abundance is not evidence "
  "of discrete search. Median sweep rate = {rm:.3f} sweeps/s (mean {ra:.3f}; range "
  "{rmin:.3f}-{rmax:.3f}); median count = {cm:.0f} sweeps/trial (mean {ca:.0f}; range "
  "{cmin:.0f}-{cmax:.0f}); {nsw:,} sweeps pooled across {nt} trials. A median of ~{rm:.1f} "
  "'sweeps' every second is far faster than deliberate, discrete search sweeps: the count "
  "is duration-driven and most detected events are routine nose motion rather than "
  "goal-directed sweeps.".format(
      rm=rate_med, ra=rate_mean, rmin=rate_min, rmax=rate_max,
      cm=cnt_med, ca=cnt_mean, cmin=cnt_min, cmax=cnt_max, nsw=n_pooled, nt=n_trials))

P("3.2 Peri-sweep ethanol vs matched-count random-time null.", bold=True)
P("Peri-sweep baseline-subtracted ethanol is NOT significantly above the matched-count "
  "random-time null. Paired Wilcoxon (observed > null), per trial: statistic = {stat:.1f}, "
  "p = {p:.3f} (n = {nt} trials). The per-trial medians are nearly identical — observed "
  "{obs:.4f} vs null {nul:.4f} — a difference of only {diff:.4f} a.u. that does not reach "
  "significance. Odor is not reliably elevated at sweep times beyond what random timing "
  "produces.".format(stat=b_stat, p=b_p, nt=n_trials, obs=b_obs, nul=b_null,
                      diff=b_obs - b_null))

P("Figure F1 (below) shows the peri-sweep time course. In F1A the mean "
  "baseline-subtracted ethanol is essentially flat across the peri window with no peak at "
  "t = 0 (the sweep peak); the first grid sample already sits at ~{first:.3f} a.u. and the "
  "curve does not rise into the sweep. This flatness is the visual counterpart of the "
  "non-significant Wilcoxon test: there is no odor transient time-locked to sweeps. F1B "
  "shows the expected kinematic signature (a sharp v_com trough at t = 0), confirming the "
  "sweeps are real motor events even though they carry no odor signal.".format(
      first=F1A["mean"][0]))

# insert F1
doc.add_picture(FIGS + r"\F1_peri_sweep_odor_and_com.png", width=Inches(5.6))
cap = doc.add_paragraph()
cr = cap.add_run(
    "Figure F1. Peri-sweep dynamics (pooled Loc1-6; n(sweeps) = {ns:,}, n(trials) = {nt}). "
    "(F1A, top) Mean baseline-subtracted ethanol (a.u.) vs time to sweep peak over "
    "{peri} s, 95% CI band; dashed line at t = 0. The curve is flat — no odor transient at "
    "the sweep. (F1B, bottom) Mean COM speed v_com (px/s), same window and CI; the trough "
    "at t = 0 confirms sweeps are genuine motor events. Source: stats.json "
    "F1A_peri_eth / F1B_peri_vcom.".format(
        ns=F1A["n_sweeps"], nt=F1A["n_trials"], peri=win["peri"]))
cr.italic = True
cr.font.size = Pt(9)
cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

P("3.3 Sweep magnitude vs local odor (H1c) — magnitude first.", bold=True)
P("The pre-registered H1(c) statistic is the Spearman correlation between sweep magnitude "
  "R at the peak and summed peri-sweep baseline-subtracted ethanol (one point per sweep, "
  "n = {n:,}). rho = {rho:+.4f}. This is NEGLIGIBLE in magnitude (essentially zero) and "
  "NEGATIVE in direction — the opposite of the predicted positive relationship. Although "
  "the 95% CI [{lo:+.4f}, {hi:+.4f}] barely excludes zero and the p-value is small "
  "(p = {p:.2e}), that significance is an artifact of the enormous number of sweeps, not a "
  "meaningful effect. An effect size of ~0 in the wrong direction cannot support H1 "
  "regardless of its p-value.".format(
      n=c_n, rho=c_rho, lo=c_lo, hi=c_hi, p=c_p))
P("Figure F2B (below) plots the same relationship using nose speed at the peak on the "
  "x-axis (per the figure spec) against summed peri-sweep odor. The plotted-point Spearman "
  "is rho = {prho:+.3f} (95% CI [{plo:+.3f}, {phi:+.3f}], p = {pp:.2e}, n = {pn:,}) — again "
  "a near-zero, non-positive relationship. Whether the axis is sweep magnitude R (the "
  "inferential test) or nose speed (the figure), stronger nose motion is not accompanied "
  "by more local odor.".format(
      prho=F2["rho"], plo=F2["ci_lo"], phi=F2["ci_hi"], pp=F2["p"], pn=F2["n_points"]))

# insert F2B
doc.add_picture(FIGS + r"\F2B_nose_vs_summed_odor.png", width=Inches(5.6))
cap2 = doc.add_paragraph()
cr2 = cap2.add_run(
    "Figure F2B. Nose speed at sweep peak (px/s) vs summed baseline-subtracted ethanol over "
    "{esum} s (a.u.), one point per pooled Loc1-6 sweep (n = {pn:,}). Annotated Spearman "
    "rho = {prho:+.3f}, 95% CI [{plo:+.3f}, {phi:+.3f}], p = {pp:.2e} describe the plotted "
    "points (seed {seed}). The pre-registered H1(c) inferential statistic is the R-based "
    "rho = {crho:+.4f} (CI [{clo:+.4f}, {chi:+.4f}], p = {cp:.2e}) reported in the text; "
    "both are near-zero, non-positive nulls. Source: sweeps.h5 /sweeps columns "
    "v_nose, summed_eth, in_pooled.".format(
        esum=win["eth_sum"], pn=F2["n_points"], prho=F2["rho"], plo=F2["ci_lo"],
        phi=F2["ci_hi"], pp=F2["p"], seed=F2["seed"],
        crho=c_rho, clo=c_lo, chi=c_hi, cp=c_p))
cr2.italic = True
cr2.font.size = Pt(9)
cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER

P("3.4 Absolute-amplitude check.", bold=True)
P("Peri-sweep baseline-subtracted ethanol (median {med:.4f} a.u., 90th pct {p90:.4f}) sits "
  "above the deconvolution noise floor (~{fl:.0e} a.u.) — {abv} — and {frac:.1%} of sweeps "
  "have mean peri-sweep ethanol > 0.01. So sweeps do occur where SOME odor is present. "
  "However, that amplitude is a small fraction of the real dynamic range of the signal "
  "(~{rng:.2f} a.u.): the odor present at sweeps is weak, and (per 3.2-3.3) it is neither "
  "elevated relative to random timing nor scaled with sweep size. Being above the noise "
  "floor is necessary but not sufficient for an odor-guided-search claim.".format(
      med=amp_med, p90=amp_p90, fl=amp_floor,
      abv=("confirmed above floor" if AMP["above_noise_floor"] else "NOT above floor"),
      frac=amp_frac, rng=amp_range))

# Summary table
H("3.5 Result summary", 2)
tbl = doc.add_table(rows=1, cols=4)
tbl.style = "Light Grid Accent 1"
hdr = tbl.rows[0].cells
for i, t in enumerate(["Test", "Result", "Predicted / criterion", "Supports H1?"]):
    hdr[i].paragraphs[0].add_run(t).bold = True
rows = [
    ("(a) Prevalence (rate)",
     "median {:.3f} sweeps/s; median {:.0f}/trial; {:,} pooled".format(rate_med, cnt_med, n_pooled),
     "prevalent AND discrete",
     "Abundant but rate too high -> routine motion, not discrete search"),
    ("(b) Peri-sweep eth vs null",
     "Wilcoxon p = {:.3f}; obs {:.4f} vs null {:.4f}".format(b_p, b_obs, b_null),
     "observed > null (p < 0.05)",
     "No (not significant)"),
    ("(c) rho(R, summed odor)",
     "rho = {:+.4f}; CI [{:+.4f}, {:+.4f}]; p = {:.1e}".format(c_rho, c_lo, c_hi, c_p),
     "rho > 0, CI excludes 0",
     "No (~0 and negative)"),
    ("Amplitude check",
     "median {:.4f} a.u.; {:.1%} sweeps > 0.01; above floor".format(amp_med, amp_frac),
     "above noise floor",
     "Above floor but weak vs ~{:.2f} range".format(amp_range)),
]
for r in rows:
    cells = tbl.add_row().cells
    for i, t in enumerate(r):
        cells[i].paragraphs[0].add_run(t).font.size = Pt(9)

P("Bottom line: acceptance requires peri-sweep ethanol > null AND rho > 0 with CI "
  "excluding 0. Neither holds — the peri-vs-null test is non-significant and rho is ~0 and "
  "negative. H1 is NOT supported.", bold=True)

# ================= Caveats =================
H("4. Caveats and limitations", 1)
bullet(" The R-based sweep detector (height >= 1.5, prominence >= 0.5, refractory 0.30 s) "
       "fires at a median ~{:.1f}/s. At that rate the great majority of detected 'sweeps' "
       "are routine nose motion, not discrete, deliberate search sweeps. Thresholds are "
       "editable; a stricter detector would yield fewer, more sweep-like events but was "
       "not the pre-registered analysis.".format(rate_med),
       bold_lead="Sweeps are mostly routine motion. ")
bullet(" The H1(c) correlation is statistically significant (p = {:.1e}) only because n = "
       "{:,} sweeps makes even a rho of {:+.3f} 'significant'. The effect size is ~0 and "
       "in the wrong direction; significance here reflects sample size, not biology. We "
       "lead with magnitude and direction, not the p-value.".format(c_p, c_n, c_rho),
       bold_lead="Tiny-but-significant N artifact. ")
bullet(" Ethanol is in uncalibrated arbitrary units and positions in pixels; the amplitude "
       "check is relative to an internal range/noise-floor reference, not an absolute "
       "concentration. Results are from a single cohort/experimental setup, so "
       "generalization is unestablished.",
       bold_lead="Uncalibrated units, single cohort. ")

# ================= Reproducibility =================
H("5. Reproducibility", 1)
P("Random seed {seed}; library {ver}; results generated {utc}.".format(
    seed=M["seed"], ver=M["VERSION"], utc=M["created_utc"]))
P("Exact commands (interpreter = vras\\Scripts\\python.exe):")
codep = doc.add_paragraph()
cc = codep.add_run(
    '"$AR_PY" code\\build_h1_figures.py    # builds F1 and F2B (png+pdf+txt)\n'
    '"$AR_PY" code\\build_h1_report.py     # builds this DOCX')
cc.font.name = "Consolas"
cc.font.size = Pt(9)
P("Result files consumed: data\\stats.json (keys H1a_prevalence, H1b_peri_sweep_odor, "
  "H1c_spearman, H1_amplitude_check, F1A_peri_eth, F1B_peri_vcom, meta); "
  "data\\sweeps.h5 (/sweeps columns v_nose, summed_eth, in_pooled). "
  "Figures: reports\\figures\\F1_peri_sweep_odor_and_com.{png,pdf,txt}, "
  "reports\\figures\\F2B_nose_vs_summed_odor.{png,pdf,txt}. "
  "All reported numbers are injected from these objects; the science was not recomputed "
  "(the only in-report computation is the Spearman of F2B's plotted points, which "
  "describes the figure).")

doc.save(OUT)
print("Saved:", OUT)
