# PLAN — Plume Locations: Odor-Field Mapping & Ethanol-Signal Enhancement

**Plan version:** 1.1 · **Prepared:** 2026-08-07 · **Architect:** planning-architect (Opus)

> **REVISION v1.1 (scoped, from Gate-2 audit `reports/audit_report.md`, REVISE).**
> Iteration 1 of ≤2. Fixes, each closing an audit finding:
> - **B1 (BLOCKER).** `choose_L` must return the **smallest** L (finest) meeting the
>   ≥60% ≥3-trial coverage rule, not the first/coarsest. Re-run Task 1; regenerate
>   fields/figures/report; re-derive λ & sparseness on the finer grid. Delete the
>   false "finer bins fail the coverage rule" text (the L_scan table shows L=15–30
>   pass at all six locations).
> - **M1.** Recalibrate Task-2 detection to a **physically meaningful FPR** — set the
>   BEFORE threshold at k·MAD of the quiet baseline (k s.t. quiet-baseline FPR → ~0,
>   target ≤ 0.05/s), match AFTER to that same low FPR (still after ≤ before). State
>   the expected order-of-magnitude of true encounters per trial. Re-run.
> - **M2.** Report before/after SNR as dimensionless peak/local-MAD on each trace
>   (commensurable), and if the method does not improve distal SNR, **headline that
>   honestly** (was: 106/114 negative gain). Top-10 figure = genuine highest-gain,
>   labeled with sign.
> - **M3.** Replace the trivial `gini(ones)=0` null with a **Monte-Carlo** null
>   (redistribute the observed total odor mass across the same N bins with realistic
>   per-bin sample counts, many draws → null Gini distribution + 95% CI) for H1.
> - **m1–m4.** Note Loc4 OLS CI includes 0; state MC posture (per-test CIs, no family
>   correction); suppress non-physical mean-field λ (report NA); add a 2–3-trial
>   drift-window residual validation artifact.

**Architect:** planning-architect (Opus)
**Request:** `requests/Request draft 2 (agent-ready).docx`
**Prior lessons:** `learning/LESSONS.md` — *absent at plan time* (first run; will be created on archive).

All facts below marked **[verified]** were confirmed by a read-only probe
(`code/probe_data.py` → `data/_probe.json`) run before planning. Numbers the code
recovers at runtime supersede any hard-coded value here (per request §3.1).

---

## 0. Restated goal

Two independent deliverable tasks, both reading only the `/behavior` block of the
aggregate (114 infrared foraging trials, head-mounted ethanol sensor):

- **Task 1 — Odor-field statistical maps.** Per end location (Loc1–Loc6), build a
  spatial odor field (max/mean/min/count over square bins) from deconvolved
  ethanol (`ethdeconv`) sampled along the cleaned head trajectory; summarize
  sparseness, distance-dependence, and trajectory structure. `anotherLoc`
  reported separately, excluded from the six fields.
- **Task 2 — Signal enhancement.** Per trial, separate genuine ethanol encounters
  from slow baseline drift and use high-SNR near-source encounter shape to recover
  small distal encounters via matched filtering, at a **matched false-positive
  rate**.

## Data scope, inclusion / exclusion (both tasks)

- **Source [verified]:** `DATA\Mouse Arena Aggregate Data.h5` (schema 0.1, Fs=500 Hz),
  read **only** via `mouse_arena_aggregate_io.Aggregate`. Read-only.
- **Block:** `/behavior` only. `sensor/*` blocks and calcium are **excluded**
  (bench sweeps / absent). `has_calcium=0` [verified].
- **Trials:** all 114 (lighting=`infrared` for all → not a partition) [verified].
- **End-location groups [verified]** (regex `_Loc(\d+)`; `anotherLoc` fallback):
  Loc1 n=20 (474,61) · Loc2 n=18 (506,114) · Loc3 n=17 (506,191) ·
  Loc4 n=14 (453,164) · Loc5 n=17 (441,129) · Loc6 n=19 (506,61) ·
  anotherLoc n=9 (centroid 400,103). Loc1–6 endpoint spread = **0.0 px**;
  anotherLoc heterogeneous → **excluded** from the six fields. Sum = 114.
  Code must recover these 7 groups and warn if any Loc spread > 2 px.
- **`loc` and `duration` trial attrs are all-NaN [verified]** → never used. End
  location from `file_name`; durations from the time bases.
- **Out-of-arena head samples excluded:** keep only x∈[0,580], y∈[0,280], finite.
  Probe: mean 2.1% of head samples out of box (max 21.2%) — real tracking
  artifacts (observed x∈[-607,929]).
- **Out-of-coverage samples excluded:** head samples whose time falls outside the
  sensor time span get `eth_at_head=NaN` and are dropped. Probe: head-in-coverage
  mean 0.98 (min 0.60).

---

## 1. Shared definitions (implemented once in `code/plume_common.py`)

To guarantee Task 1 and Task 2 use identical cleaning/alignment/grouping, a single
shared library is written and imported by both. Functions + their pre-registered rules:

- **`group_of(file_name)`** — `_Loc(\d+)` → `LocN`; else `anotherLoc` if present.
- **`clean_head(head, head_time)`** — keep finite samples with x∈[0,580],
  y∈[0,280]; **de-jump**: after box-filtering, drop a sample whose step from the
  **immediately preceding box-kept sample** exceeds `Q = 99.5th percentile of step
  sizes` computed **pooled across all trials** (single global Q; value recorded).
  The reference sample always advances (consecutive-difference rule) — an anchored
  reference cascades and deletes whole movement bouts (see LESSONS; observed
  42898→926 samples before the fix). At Q=99.5th pctile (2.86 px; step median 0.24,
  99th 1.47, 99.9th 21.7, max 222 → artifacts clearly separated) this removes
  ~0.5% of samples as intended. Log removals per-trial and overall. Body track
  cleaned identically for the robustness check.
- **`align_signal(head_time, sig_time, sig)`** —
  `np.interp(head_time, sig_time, sig, left=nan, right=nan)`. Never resample
  position onto the sensor clock. NaN samples excluded downstream.
- **`endpoint_of(trial)`** — the stored `endpoint` (2,), non-NaN for all trials.
- **Distance helper** — Euclidean head→endpoint distance per kept sample (px).

Self-checks in the module (run before heavy compute): grouping recovers 7 groups
summing to 114; each Loc spread ≤ 2 px; interp of a known ramp reproduces exact
values; a synthetic out-of-box point is dropped.

---

## 2. Task 1 — methods & parameters (each parameter justified)

- **Signal:** `ethdeconv`, aligned to head clock (D3). Scale [verified] ≈[-0.02,0.14].
- **Grid:** square bins edge `L` px tiling x∈[0,580], y∈[0,280]; **same grid for
  all 4 panels of a location.** Row = y-bin, col = x-bin, 0-based.
- **Choose L per location:** scan `L ∈ {40,30,25,20,15,10}` (descending); pick the
  **smallest L** for which **≥60%** of visited bins (≥1 sample from ≥1 trial) have
  **≥3 contributing trials**. If none reach 60%, fall back to L=40 and note it.
  Record chosen L + coverage fraction per location. *Justification:* keeps bins as
  fine as the data support while guaranteeing every displayed statistic is backed
  by ≥3 trials (request §3.1 / Table 3).
- **Observation = trial** (D6): a trial contributes to a bin if ≥1 cleaned,
  time-aligned head sample falls in it. Per-bin count = # distinct such trials.
- **Per-bin stats (D7):** pool the aligned `ethdeconv` **sample** values of all
  contributing trials in the bin → max, mean, min. Count = # distinct trials.
- **Masking:** in max/mean/min maps, bins with <3 contributing trials → **NaN**
  (not plotted/stored as value). Count map shows the true count including <3.
- **Robustness check:** recompute the **Loc-pooled** mean field (all Loc1–6 pooled
  onto one grid) using the **BODY** track; report Pearson r of head vs body mean
  maps (one sentence + supplementary correlation). Guards against cleaning driving
  the result.

### Task-1 report statistics (saved to a result file, injected into docx)

- **Sparseness.** Per location and pooled: (a) fraction of visited bins with mean
  `ethdeconv` above a **cutoff**; (b) share of total odor mass in the top-5% bins;
  (c) **concentration index** = Gini of the mean map **and** normalized Shannon
  entropy. *Cutoff rule (pre-registered):* `cutoff = max(3·MAD, small_floor)` where
  MAD = 1.4826·median(|x−median|) of all aligned `ethdeconv` sample values (robust
  noise floor); report the numeric cutoff and repeat (a) at 1×,3×,5× MAD for
  robustness. Gini/entropy are the **primary** sparseness measures (cutoff-free).
- **Distance dependence.** Per bin: Euclidean distance (bin center → that location's
  endpoint). Fit mean and max bin odor vs distance with (i) OLS of `log(odor)` on
  distance (odor>cutoff bins) → decay constant, and (ii) an exponential-decay fit
  `a·exp(−d/λ)+c`. Report slope/λ with **95% CI**, per location and pooled. State
  whether odor concentrates near source and the spatial scale (px).
- **Trajectory types.** Per trial: path length (Σ cleaned head steps, px);
  tortuosity (path length ÷ straight-line start→endpoint distance); # odor
  encounters (§3 Task-2 detector definition applied to aligned `ethdeconv`);
  fraction of path above the odor threshold (= sparseness cutoff on `ethdeconv`).
  Summarize types per location (e.g. direct-to-source vs distributed-search via a
  2-cluster split or tortuosity tertiles); relate trajectory metrics to encounter
  metrics with an **effect size + 95% CI** (Spearman ρ). Replication unit = trial;
  animal-aware summary where trial counts allow (animal parsed from `file_name`).

### Task-1 hypotheses (direction reported before significance)

- **H1 (sparseness).** H1: odor concentrated in a minority of visited bins vs
  H0: uniform. Test: concentration index vs a uniform-map null (Gini of a
  same-N uniform field). Accept if index + null comparison reported per location.
- **H2 (distance).** H1: mean/max bin odor decreases with distance vs H0: slope=0.
  Test: per-location fit + CI; pooled animal-aware summary. Accept if slope + CI
  reported per location and pooled (null/positive slope is a valid result).
- **H3 (trajectory).** H1: trajectory types differ in odor encountered vs H0: no
  association. Accept if association quantified with effect size + CI per location.

## 3. Task 2 — methods & parameters (each parameter justified)

- **Input trace:** **raw `ethanol`** (carries the drift; threshold scale matches raw
  [verified]). `ethdeconv` kept as an alternative input. All per trial.
- **Drift removal:** subtract a slow baseline = rolling low-percentile (10th pctile)
  over a window `W`. *W chosen data-drivenly:* estimate the drift timescale as the
  dominant low-frequency period / autocorrelation decay of the raw trace; default
  `W = 20 s` (≈10,000 samples @500 Hz), inside the request's 10–30 s range; record
  the measured drift timescale that justifies it. Result = drift-corrected trace.
- **Template:** high-SNR near-endpoint encounters = peaks where head-to-endpoint
  distance < `D_near` (default: 20th percentile of that trial's head-endpoint
  distance) **and** drift-corrected signal > `k·MAD` (k=5) of a quiet segment.
  Extract fixed windows `±T_tmpl` (default `T_tmpl = 0.3 s` → 301 samples @500 Hz,
  ≈ deconv kernel timescale τ=0.02/2.0 s and typical transient width; recorded),
  align to peak, average → canonical template. Build **pooled** template (primary)
  and per-location (reported).
- **Enhancement:** normalized cross-correlation (matched filter) of drift-corrected
  trace with the template → **enhanced trace** (primary Task-2 product).
- **Detection (matched fairly):** encounter = threshold crossing with peak
  prominence + **refractory gap** `R` (default 0.2 s within 0.1–0.5 s; recorded).
  Detect **before** (on drift-corrected raw) and **after** (on enhanced).
  **Calibrate both detector thresholds to a shared false-positive rate** on a
  quiet, far-from-source baseline segment (samples with head-endpoint distance >
  80th percentile AND in the lowest-amplitude window); state both thresholds + the
  target FPR. This makes the "after" gain real recovery, not a looser threshold.
- **Distance / distal:** Euclidean head→endpoint px per time; **distal** = beyond
  the **per-trial median** head-endpoint distance (default).
- **SNR:** peak amplitude ÷ local baseline noise (MAD of the trace in a nearby quiet
  window); defined once, applied identically before/after.
- **"Most improved distal SNR":** per trial, mean SNR gain (after−before) of its
  distal encounters; rank trials; top 10 → Figure A.

### Task-2 hypotheses

- **H4 (recovery).** H1: enhancement increases detected encounters,
  disproportionately distal, vs H0: no net increase at matched FPR. Test: paired
  before/after counts across trials (Wilcoxon signed-rank), split proximal/distal.
- **H5 (no fabrication — guard).** On a quiet far-from-source baseline segment,
  the **after** detector FPR must be **≤** the **before** FPR. If higher → the run
  FAILS and thresholds recalibrate. Report measured baseline FPRs. This is a hard
  auditor gate.

---

## 4. Deliverables (exact paths, under `Analysis\Plume locations\`)

| Artifact | Path | Task |
|---|---|---|
| Odor-field figures (7) | `reports\figures\fields\field_Loc1..6.{png,pdf}`, `field_anotherLoc.*` (+ `.txt` sidecars) | 1 |
| Odor-field data | `data\odor_fields.h5` | 1 |
| Task-1 stats result | `data\odor_field_stats.json` (+ arrays as needed) | 1 |
| Odor-field report | `reports\Odor field report.docx` | 1 |
| Enhancement figures (2) | `reports\figures\enhancement\enhance_examples.{png,pdf}`, `enhance_count_scatter.{png,pdf}` (+ sidecars) | 2 |
| Enhanced data | `data\enhanced_ethanol.h5` | 2 |
| Task-2 stats result | `data\enhancement_stats.json` | 2 |
| Enhancement report | `reports\Signal enhancement report.docx` | 2 |
| Plan / audit / notes | `PLAN.md`, `plan.json`, `audit_report.md`, `SESSION_NOTES.md` | both |
| Lessons | `learning\LESSONS.md` (append) | both |

**HDF5 contracts** exactly per request §4.4 / §5.3: groups, datasets, root+group
attrs, gzip4+shuffle on numeric ≥256 elements, `.tmp`→`os.replace`,
`build_complete=1` set last, README attr, `created_utc`, generator name/version.

---

## 5. Acceptance criteria / definition of done

1. `PLAN.md`+`plan.json` pre-register both tasks with H1–H5, every parameter
   justified, exclusions, acceptance — **this file**.
2. **Gate 1 (code-verifier):** static checks + tests pass; one headline number
   independently re-derived (a bin mean; a trial before/after count).
3. All **9** figures exist as non-empty PNG+PDF with `.txt` sidecars; both `.h5`
   open via a fresh `h5py` read and expose documented groups/attrs
   (`build_complete=1`); both reports have **zero** `{{placeholder}}` tokens and
   every number traces to a saved result object.
4. **Gate 2 (scientific-auditor):** sparseness/distance/trajectory claims supported
   and directionally reported; **H5 guard holds (baseline FPR after ≤ before)**.
   REVISE/FAIL → one scoped re-plan (≤2 iterations) then STOP with
   `SESSION_NOTES.md`.
5. `lesson-archivist` appends a dated entry to `learning\LESSONS.md`.

## 6. Risks / assumptions to validate on the first slice

- Chosen `L` may hit the 40 px fallback for small-N locations (Loc4 n=14) → check
  coverage table; acceptable if noted.
- Matched-FPR calibration must actually equalize FPR; verify on baseline segment
  before trusting count gains (H5). If AFTER FPR > BEFORE, recalibrate before scaling.
- Drift-window W must exceed encounter width but not erase real slow structure;
  validate on 2–3 trials (visual + residual check) before full run.
- `ethdeconv` cutoff MAD may be ~0 if signal is very sparse; floor prevents a
  degenerate cutoff.

## 7. Task graph (independent = parallel, dependent = pipelined)

1. **[me] Plan** (this file) + **shared lib** `plume_common.py` (+ self-check).
2. **[parallel subagents] Analyze:** `data-analyst`×2 — Task 1 fields+stats;
   Task 2 enhancement. Both import `plume_common`. Write `.h5` + stats `.json`
   + logs. Slice-first then full.
3. **[fresh subagent] Gate 1 — code-verifier** on both. ≤2 fix cycles.
4. **[parallel subagents] Figures + reports** from saved results only:
   Task-1 (7 figs + docx), Task-2 (2 figs + docx).
5. **[fresh subagent] Gate 2 — scientific-auditor** → `audit_report.md`.
6. **[me] Archive** → `learning\LESSONS.md`; `SESSION_NOTES.md`.

**Invariants:** no agent approves its own work; verifier & auditor run in fresh
context and read no self-justifications; never mark human-approved; a bounded stop
is success, handed off via `SESSION_NOTES.md`.
