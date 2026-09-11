r"""make_F4.py -- Build figure F4 (peri-contact reorientation) STRICTLY from stats.json.

Never recomputes science. Reads the H3.F4_peri_contact_curve block and H3 summary
from data\stats.json and renders png (dpi=200), pdf, and a .txt sidecar.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

BASE = r"C:\Projects\Repos\Mouse Arena\Analysis\trajectories"
STATS = os.path.join(BASE, "data", "stats.json")
FIGDIR = os.path.join(BASE, "reports", "figures")
STEM = os.path.join(FIGDIR, "F4_peri_contact_angle")


def main():
    os.makedirs(FIGDIR, exist_ok=True)
    with open(STATS, "r", encoding="utf-8") as fh:
        stats = json.load(fh)

    h3 = stats["H3"]
    curve = h3["F4_peri_contact_curve"]

    x = curve["rel_times_s"]
    y = curve["mean_theta"]
    lo = curve["ci_lo"]
    hi = curve["ci_hi"]
    n_contacts = curve["n_contacts"]
    n_trials = curve["n_trials_contributing"]

    wil = h3["paired_wilcoxon_post_lt_pre"]
    wil_stat = wil["stat"]
    wil_p = wil["p"]
    med_pre = h3["median_pre_theta"]
    med_post = h3["median_post_theta"]

    seed = stats["meta"]["seed"]
    n_boot = stats["meta"]["n_boot"]

    # ---- figure ----
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.fill_between(x, lo, hi, color="#4c72b0", alpha=0.25,
                    label="95% CI (bootstrap over trials)")
    ax.plot(x, y, color="#1f3f7a", lw=2.0, label="mean |θ|")
    ax.axvline(0.0, color="crimson", ls="--", lw=1.5, label="contact onset (t=0)")

    ax.set_xlabel("Peri-contact time (s)  [0 = ethanol encounter onset]")
    ax.set_ylabel("Mean absolute body-axis angle to source  |θ| (degrees)")
    ax.set_title("F4 - Peri-contact reorientation (pooled Loc1-6)")
    ax.set_xlim(min(x), max(x))
    ax.grid(True, alpha=0.3)

    annotation = (
        "H3 (post < pre) NOT supported\n"
        "median pre |θ| = {:.1f}°   median post |θ| = {:.1f}°\n"
        "paired Wilcoxon (post<pre): W = {:.1f}, p = {:.3f}\n"
        "n contacts = {:,}   n trials contributing = {}"
    ).format(med_pre, med_post, wil_stat, wil_p, n_contacts, n_trials)
    ax.text(0.02, 0.02, annotation, transform=ax.transAxes,
            fontsize=8.5, va="bottom", ha="left",
            bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))

    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.tight_layout()

    fig.savefig(STEM + ".png", dpi=200, bbox_inches="tight")
    fig.savefig(STEM + ".pdf", bbox_inches="tight")
    plt.close(fig)

    # ---- sidecar ----
    lines = []
    lines.append("F4 - Peri-contact reorientation")
    lines.append("Source: " + STATS)
    lines.append("Rendered from stats.json H3.F4_peri_contact_curve (no recomputation).")
    lines.append("Pooled over all encounters across Loc1-6.")
    lines.append("Bootstrap over trials, n_boot={}, seed={}.".format(n_boot, seed))
    lines.append("")
    lines.append("H3 summary (from stats.json H3):")
    lines.append("  n_trials_with_encounter = {}".format(h3["n_trials_with_encounter"]))
    lines.append("  n_paired_trials         = {}".format(h3["n_paired_trials"]))
    lines.append("  total_contacts_pooled   = {}".format(h3["total_contacts_pooled"]))
    lines.append("  median_pre_theta_deg    = {:.6f}".format(med_pre))
    lines.append("  median_post_theta_deg   = {:.6f}".format(med_post))
    lines.append("  paired_wilcoxon(post<pre): stat={}, p={:.10f}, alt={}".format(
        wil_stat, wil_p, wil["alternative"]))
    lines.append("  direction               = {}".format(h3["direction"]))
    lines.append("  descriptive_only        = {}".format(h3["descriptive_only"]))
    lines.append("  n_contacts (curve)      = {}".format(n_contacts))
    lines.append("  n_trials_contributing   = {}".format(n_trials))
    lines.append("")
    lines.append("Curve data (rel_time_s, mean_theta_deg, ci_lo_deg, ci_hi_deg, n_trials_per_bin):")
    npb = curve["n_trials_contributing_per_bin"]
    for i in range(len(x)):
        lines.append("  {:+.3f}\t{:.6f}\t{:.6f}\t{:.6f}\t{}".format(
            x[i], y[i], lo[i], hi[i], npb[i]))
    with open(STEM + ".txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # sanity: non-empty
    for ext in (".png", ".pdf", ".txt"):
        sz = os.path.getsize(STEM + ext)
        print("wrote {}{}  ({} bytes)".format(STEM, ext, sz))
        assert sz > 0, "empty output: " + ext
    print("F4 OK")


if __name__ == "__main__":
    main()
