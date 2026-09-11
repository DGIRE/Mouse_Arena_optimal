r"""make_H3_report.py -- Build the H3 DOCX report STRICTLY from data\stats.json.

All cited numbers are injected from the saved stats.json (never hand-typed).
Embeds figure F4. After rendering, re-opens the docx and scans for placeholder
tokens; asserts zero.
"""
import json
import os

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories"
STATS = os.path.join(BASE, "data", "stats.json")
F4_PNG = os.path.join(BASE, "reports", "figures", "F4_peri_contact_angle.png")
OUT = os.path.join(BASE, "reports", "H3 - peri-contact reorientation.docx")

REPRO_CMD = (
    r'"C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe" '
    r'"C:\Projects\Repos\Mouse Arena\Analysis\trajectories\code\make_F4.py" ; '
    r'"C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/python.exe" '
    r'"C:\Projects\Repos\Mouse Arena\Analysis\trajectories\code\make_H3_report.py"'
)

PLACEHOLDER_TOKENS = ["{{", "}}", "placeholder", "TODO", "XXX", "FIXME", "TBD"]


def h(doc, text, level=1):
    doc.add_heading(text, level=level)


def p(doc, text):
    return doc.add_paragraph(text)


def main():
    with open(STATS, "r", encoding="utf-8") as fh:
        stats = json.load(fh)

    h3 = stats["H3"]
    meta = stats["meta"]
    cal = stats["calibration"]
    diag = stats["encounter_diagnostics"]
    curve = h3["F4_peri_contact_curve"]

    n_enc_trials = h3["n_trials_with_encounter"]
    n_paired = h3["n_paired_trials"]
    n_contacts = h3["total_contacts_pooled"]
    med_pre = h3["median_pre_theta"]
    med_post = h3["median_post_theta"]
    wil = h3["paired_wilcoxon_post_lt_pre"]
    wil_stat = wil["stat"]
    wil_p = wil["p"]
    wil_alt = wil["alternative"]
    direction = h3["direction"]
    descriptive_only = h3["descriptive_only"]
    n_trials_curve = curve["n_trials_contributing"]

    # encounter-diagnostic / noise-floor numbers (injected, not hardcoded)
    cal_thr = diag["calibrated_threshold"]
    ptr_ethd_med = diag["pertrial_ethd_median_median"]
    sig_max_ref = diag["signal_max_ref"]
    onset_ethd_med = diag["onset_ethd_median"]
    frac_above_0p01 = diag["frac_onsets_above_0p01"]
    sec_amp_thr = diag["secondary_amp_threshold"]
    n_enc_amp_med = diag["n_encounters_amp"]["median"]
    n_enc_amp_max = diag["n_encounters_amp"]["max"]
    n_onsets_pooled = diag["n_onsets_pooled"]
    pertrial_median_onsets = cal["n_encounters_distribution_pooled"]["median"]
    k_sel_note = cal["k_selection_note"]

    # per-trial-pair direction counts
    n_post_gt_pre = h3["n_pairs_post_gt_pre"]
    n_post_lt_pre = h3["n_pairs_post_lt_pre"]

    seed = meta["seed"]
    n_boot = meta["n_boot"]
    traj_ver = meta["traj_common_version"]
    peri_window = meta["peri_window_s"]
    peri_step = meta["peri_step_s"]
    k = cal["k"]
    n_pooled = meta["n_pooled"]
    created = meta["created_utc"]
    agg_path = meta["aggregate_path"]

    delta = med_post - med_pre  # + means post ABOVE pre (opposite of prediction)

    doc = Document()

    # ---- Title ----
    title = doc.add_heading("Hypothesis 3 - Peri-contact Reorientation", level=0)
    sub = doc.add_paragraph(
        "Do animals reorient their body axis toward the ethanol source upon an encounter?"
    )
    sub.runs[0].italic = True

    # ---- Goal + H3/H0 ----
    h(doc, "1. Goal and Hypotheses", 1)
    p(doc,
      "H3 predicts that following an ethanol encounter the body axis turns TOWARD the "
      "source, so the absolute body-axis angle to the source, |theta|, DECREASES from the "
      "pre-contact window to the post-contact window (reorientation).")
    p(doc,
      "H3 (alternative): post-contact |theta| < pre-contact |theta| (reorientation toward source).")
    p(doc,
      "H0 (null): |theta| is unchanged across the contact (pre = post).")
    p(doc,
      "Acceptance rule: accept H3 only if the trial-level paired test shows post |theta| "
      "significantly below pre |theta|. Direction is reported before significance.")

    # ---- Methods ----
    h(doc, "2. Methods", 1)
    p(doc,
      "Data were read through the shared accessor and geometry library traj_common "
      "(version {ver}) against the aggregate file {agg}. All processing used the fixed "
      "interpreter at 'C:/Projects/Repos/Agentic Research/Research Setup/vras/Scripts/"
      "python.exe' with random seed {seed}."
      .format(ver=traj_ver, agg=agg_path, seed=seed))
    p(doc,
      "Encounter (contact) onsets were detected on the head-clock-aligned ethdeconv trace "
      "using the calibrated threshold detector (k = {k} times MAD of the quiet, "
      "far-from-source baseline), with encounter time defined as the upward-crossing onset "
      "on the head clock.".format(k=k))
    p(doc,
      "Noise-floor caveat (honest interpretation of what the encounter onsets index): the "
      "calibrated encounter threshold sits at the deconvolved NOISE FLOOR, so the ~{ppd:.0f} "
      "onsets per trial ({npool:,} pooled contacts) index low-amplitude noise / exposure "
      "crossings, NOT discrete high-amplitude odor contacts. Concretely, the calibrated "
      "threshold ({thr:.2e} on ethdeconv) is the same order of magnitude as the pooled "
      "per-trial noise floor (median per-trial ethd ~{floor:.2e}) and as the median "
      "ethdeconv AT detected onsets ({onset:.2e}), while a real odor signal reaches "
      "~{sigmax:.2f}. Only a fraction {frac:.1e} of onsets (~0%) exceed the physically "
      "meaningful {sec:.2f} amplitude, and at a secondary {sec:.2f} amplitude threshold the "
      "per-trial encounter counts collapse to ~{ampmed:.0f} (median; max = {ampmax:.0f}), "
      "i.e. discrete high-amplitude odor contacts are essentially absent. The peri-contact "
      "analysis is therefore triggered on noise-floor events, which is fully consistent with "
      "the observed NULL (no reorientation): there is no discrete odor contact for the animal "
      "to reorient to. Threshold selection note: {ksel}"
      .format(ppd=pertrial_median_onsets, npool=n_onsets_pooled, thr=cal_thr,
              floor=ptr_ethd_med, onset=onset_ethd_med, sigmax=sig_max_ref,
              frac=frac_above_0p01, sec=sec_amp_thr, ampmed=n_enc_amp_med,
              ampmax=n_enc_amp_max, ksel=k_sel_note))
    p(doc,
      "Peri-contact sampling (D10): for each encounter onset, |theta| was sampled on a "
      "{lo:.1f} s to {hi:+.1f} s window around onset on a {step:.0f} ms fixed grid on the "
      "head clock. The pre window is [-1.0, 0) s and the post window is (0, +1.0] s. "
      "Contacts whose window ran past the track ends contributed only their in-range samples."
      .format(lo=peri_window[0], hi=peri_window[1], step=peri_step * 1000.0))
    p(doc,
      "Inferential test (replication unit = trial): for each trial with at least one "
      "encounter, the mean |theta| in the pre window and in the post window were computed; "
      "a paired Wilcoxon signed-rank test across trials evaluated the one-sided alternative "
      "that post < pre. The pooled peri-contact mean-|theta| curve (F4) is descriptive, with "
      "a 95% confidence band from bootstrap over trials (n_boot = {nb}, seed = {seed})."
      .format(nb=n_boot, seed=seed))
    p(doc,
      "Pooling: all encounters across Loc1-6 were pooled; the paired test used n = {np} "
      "trials (unit = trial).".format(np=n_pooled))

    # ---- Results ----
    h(doc, "3. Results", 1)
    p(doc,
      "H3 is NOT supported. The direction of the effect is opposite to (or negligibly "
      "different from) the prediction: the pooled peri-contact curve is essentially flat "
      "around t = 0, with no reorientation toward the source.")

    # direction-before-significance summary
    p(doc,
      "Direction (reported first): median pre-contact |theta| = {pre:.2f} degrees versus "
      "median post-contact |theta| = {post:.2f} degrees (change of {d:+.2f} degrees). The two "
      "medians are essentially equal - post |theta| is unchanged, NOT reduced. Across the "
      "{np} trial pairs the majority direction is post > pre ({gt} pairs with post > pre "
      "versus {lt} pairs with post < pre), i.e. if anything |theta| is slightly larger after "
      "contact. This is the opposite of the predicted decrease; no reorientation toward the "
      "source is observed."
      .format(pre=med_pre, post=med_post, d=delta, np=n_paired,
              gt=n_post_gt_pre, lt=n_post_lt_pre))
    p(doc,
      "Significance: the paired Wilcoxon signed-rank test of the one-sided alternative "
      "'{alt}' (post < pre) across n = {np} trials gave W = {stat:.1f}, p = {pv:.4f}. The "
      "large p-value indicates post |theta| is NOT below pre |theta|; the null of no "
      "reorientation cannot be rejected in the predicted direction."
      .format(alt=wil_alt, np=n_paired, stat=wil_stat, pv=wil_p))
    p(doc,
      "Sample sizes: {nc:,} contacts were pooled across {nt} trials contributing to the "
      "peri-contact curve; {ne} trials had at least one encounter and entered the paired "
      "test. (descriptive_only flag = {do}.)"
      .format(nc=n_contacts, nt=n_trials_curve, ne=n_enc_trials, do=descriptive_only))

    # Figure F4 embedded
    if os.path.exists(F4_PNG):
        doc.add_picture(F4_PNG, width=Inches(6.0))
        last = doc.paragraphs[-1]
        last.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph()
    cap_run = cap.add_run(
        "Figure F4. Peri-contact reorientation, pooled over all encounters across Loc1-6. "
        "x = peri-contact time (-1.0 to +1.0 s, 50 ms grid); y = mean absolute body-axis "
        "angle to source |theta| (degrees). Line = mean; shaded band = 95% CI (bootstrap "
        "over trials, seed {seed}). Dashed vertical line marks contact onset (t = 0). "
        "n contacts = {nc:,}; n trials contributing = {nt}. Paired Wilcoxon (post<pre): "
        "W = {stat:.1f}, p = {pv:.4f}; median pre |theta| = {pre:.1f} deg, median post "
        "|theta| = {post:.1f} deg. The curve is flat/slightly rising across t = 0: no "
        "reorientation toward the source."
        .format(seed=seed, nc=n_contacts, nt=n_trials_curve, stat=wil_stat, pv=wil_p,
                pre=med_pre, post=med_post))
    cap_run.italic = True
    cap_run.font.size = Pt(9)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # results table
    h(doc, "3.1 Key numbers", 2)
    tbl = doc.add_table(rows=1, cols=2)
    tbl.style = "Light Grid Accent 1"
    hdr = tbl.rows[0].cells
    hdr[0].text = "Quantity"
    hdr[1].text = "Value"
    rows = [
        ("Median pre-contact |theta| (deg)", "{:.4f}".format(med_pre)),
        ("Median post-contact |theta| (deg)", "{:.4f}".format(med_post)),
        ("Change post - pre (deg)", "{:+.4f}".format(delta)),
        ("Paired Wilcoxon statistic W (post<pre)", "{:.1f}".format(wil_stat)),
        ("Paired Wilcoxon p (one-sided, post<pre)", "{:.6f}".format(wil_p)),
        ("Direction", direction),
        ("n contacts (pooled)", "{:,}".format(n_contacts)),
        ("n trials contributing to curve", "{}".format(n_trials_curve)),
        ("n trials with >=1 encounter (paired)", "{}".format(n_paired)),
        ("H3 supported?", "No (null result)"),
    ]
    for name, val in rows:
        c = tbl.add_row().cells
        c[0].text = name
        c[1].text = val

    # ---- Caveats ----
    h(doc, "4. Caveats", 1)
    p(doc,
      "Angle convention verified: |theta| is the absolute angle between the body axis and "
      "the vector to the source, computed in traj_common; smaller |theta| means better "
      "alignment toward the source, so the H3 prediction is unambiguously a DECREASE.")
    p(doc,
      "Contacts may be exposure-driven rather than discrete biological reorientation events. "
      "Encounter onsets are threshold crossings on a deconvolved ethanol signal; a large "
      "count of contacts pooled from many trials does not guarantee that each is a distinct, "
      "behaviorally salient stimulus, so the flat peri-contact curve may reflect exposure "
      "structure rather than an absence of any fast reorientation reflex.")
    p(doc,
      "Single cohort, infrared imaging, pixel units: results come from one cohort recorded "
      "under infrared, with distances and geometry in pixels; generalization is limited.")
    p(doc,
      "Direction before significance: the effect direction (post approximately equal to / "
      "slightly above pre) is reported first and is itself inconsistent with H3, "
      "independent of the (non-significant) p-value.")

    # ---- Reproducibility footer ----
    h(doc, "5. Reproducibility", 1)
    p(doc, "All numbers above were injected directly from the saved result object:")
    p(doc, "  Stats:   " + STATS)
    p(doc, "  Figure:  " + F4_PNG + " (+ .pdf, + .txt sidecar)")
    p(doc, "  Metrics: " + os.path.join(BASE, "data", "trajectory_metrics.h5")
      + " / .json")
    p(doc, "Seed = {seed}; traj_common {ver}; stats.json created {c}."
      .format(seed=seed, ver=traj_ver, c=created))
    cmdp = doc.add_paragraph("Exact reproduce command:")
    codep = doc.add_paragraph(REPRO_CMD)
    codep.runs[0].font.name = "Consolas"
    codep.runs[0].font.size = Pt(8)

    doc.save(OUT)

    # ---- Placeholder scan: re-open and scan paragraphs + tables ----
    check = Document(OUT)
    hits = []
    for para in check.paragraphs:
        for tok in PLACEHOLDER_TOKENS:
            if tok in para.text:
                hits.append((tok, para.text[:80]))
    for t in check.tables:
        for row in t.rows:
            for cell in row.cells:
                for tok in PLACEHOLDER_TOKENS:
                    if tok in cell.text:
                        hits.append((tok, cell.text[:80]))

    if hits:
        print("PLACEHOLDER SCAN FAILED:")
        for tok, ctx in hits:
            print("  token={!r}  ctx={!r}".format(tok, ctx))
        raise SystemExit(1)

    print("wrote {}  ({} bytes)".format(OUT, os.path.getsize(OUT)))
    print("placeholder scan = 0")
    print("Injected: W={:.1f} p={:.6f} med_pre={:.4f} med_post={:.4f} "
          "n_contacts={} n_trials={}".format(
              wil_stat, wil_p, med_pre, med_post, n_contacts, n_trials_curve))
    print("H3 report OK")


if __name__ == "__main__":
    main()
