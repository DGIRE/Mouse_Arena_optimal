# Autonomous Coding — Best Practices for Safe, Unattended Runs

**Audience:** a Claude Code CLI session that will write and run data-analysis
code, build figures, and write reports **without a human clicking permission
prompts**, possibly for hours. Read this at the start of an autonomous session.
The `.claude/` bundle that ships alongside this file (installed in the home
directory, `~/.claude`) enforces most of it; this document is the reasoning and
the habits that make an unattended run finish correctly, quickly, and safely.

The four goals, in priority order: **(1) safe** — never destroy data, exfiltrate,
or mutate the machine; **(2) correct** — results a scientist can trust; **(3)
autonomous** — no prompts, no stalls; **(4) frugal & fast** — few tokens, few
reruns, and full use of the hardware without crashing it.

> For a machine- and project-agnostic version of this guide (no `.claude` bundle,
> no `$AR_PY`, no bundled agents), see
> **`AUTONOMOUS_CODING_BEST_PRACTICES_GENERAL.md`** in this folder — point any
> agent operating anywhere at that one.

---

## 1. Run it in the right mode

Launch with a permission mode that skips prompts but keeps the guardrails:

```
claude --permission-mode auto
```

`auto` auto-approves ordinary work (edit files, run the analysis venv) and blocks
dangerous actions. `acceptEdits` is a more conservative alternative (auto-approves
edits/reads; bash still governed by the allow-list). `bypassPermissions`
(`--dangerously-skip-permissions`) skips **everything** including the deny-list —
only the guard hook still fires — so use it **only** in a throwaway/sandboxed
tree, never on real data. Recommended default: **`auto`**.

Two backstops always apply and must not be circumvented:

- **deny-list** (`~/.claude/settings.json` → `permissions.deny`) — blocks
  destructive, network, install, and publish bash commands (applies in
  `default`/`acceptEdits`/`auto`).
- **guard hook** (`~/.claude/hooks/guard_bash.py`, exits 2 to block) — the same
  protections, shell-independent, active in **every** mode including bypass.

If something you try is blocked, that is the system telling you it doesn't belong
in an unattended run. **Adapt** — don't retry the blocked form, and never edit the
guard or deny-list to get around it.

---

## 2. The interpreter rule (the #1 cause of silent failures)

Run **all** Python with the quoted env var `"$AR_PY"`:

```
"$AR_PY" analysis/run_stats.py
"$AR_PY" -m pytest tests/ -q
"$AR_PY" -m compileall analysis/run_stats.py
```

`$AR_PY` is the project venv python (default
`…/vras/Scripts/python.exe`), which has numpy, scipy, pandas,
scikit-learn, statsmodels, h5py, matplotlib, and python-docx. A **bare `python`,
`py`, or `python3` resolves to Anaconda** on this machine — a different
interpreter that will fail on imports and waste a run. Never fall back to it.

The `SessionStart` hook prints a `[venv]` line confirming `$AR_PY`. If it warns
the venv wasn't found (a different computer, a moved folder), use `/setup-venv`:
ask the user for a venv path if attended; if unattended, **stop and leave a note**
— do not guess and do not `pip install`.

---

## 3. Command style that avoids accidental prompts and wasted tokens

Permission heuristics can force a prompt (a stall, when unattended) on
suspicious-looking commands. Keep commands boring:

- **Write code to a `.py` file and run the file.** Avoid `python -c "…"` with long
  inline heredocs or `#` comments, and don't paste hundred-line scripts inline —
  both can trip length/parse heuristics.
- **One simple command at a time.** Avoid `cd "…" && … 2>&1 | tail` chains; the
  "cd + redirect" pattern often forces approval. Pass absolute paths and script
  arguments instead of `cd`.
- **Quote paths; don't over-escape backslashes.** Prefer forward slashes.
- **Never scan the whole drive** (`find / …`). Inputs live at known paths.
- **Log, don't flood.** Send long program output to a file and read the tail:
  `"$AR_PY" run.py > logs/run.log 2>&1` then read the last lines. Dumping
  thousands of lines into context is the biggest avoidable token cost.

---

## 4. The efficient, bug-averse loop

Producing bug-free code fast is mostly about catching errors when they are cheap,
not about being clever.

1. **Plan in a few lines**, then act. Name inputs, outputs, and the 2–4 real
   steps. Don't over-plan or narrate every action.
2. **Skeleton before compute.** Write the module with a `main()`, a **fixed
   random seed**, and a tiny assert-based self-check (expected shapes, a known
   value) *before* the expensive part.
3. **Static-check every file the moment you write it:**
   `"$AR_PY" -m compileall <file>` catches syntax errors instantly; a fast
   `pytest` on a small fixture catches logic errors. This is 100× cheaper than
   discovering the bug 40 minutes into the full run.
4. **Slice first, then scale.** Run on one session / a subset, confirm ranges and
   shapes are sane (not all-NaN, not all-zero), *then* run the full job.
5. **Checkpoint to disk.** Write intermediate results (`.npz`, `.parquet`,
   `.json`) and guard heavy stages with "if fresh output exists, skip." A crash
   or a context compaction then resumes instead of restarting.
6. **Isolate failures.** Wrap each independent stage so one failure degrades to a
   logged NaN/skip and the run continues; only the headline result is allowed to
   hard-fail.
7. **Don't repeat work.** Don't re-read files you just wrote or re-verify what
   already passed (see the execution-frugality note in the repo). One good pass
   beats many small corrections.

---

## 5. The pipeline: plan → verify → audit → archive, and the two gates

Analysis runs as an ordered team of sub-agents with two quality gates. The order
is fixed; independent work *within* a stage is parallelized (§5.1) and dependent
stages are pipelined. Delegate each stage with the `Task` tool:

1. **Plan.** `planning-architect` (Opus) reads the request, the data docs, and
   **`/learning/LESSONS.md`**, then writes a pre-registered `PLAN.md`/`plan.json`
   — goal + hypotheses (H1/H0), methods, null/control models, exclusion rules,
   every window/parameter with a data-derived justification, and concrete
   **acceptance criteria**. No analysis code is written here.
2. **Analyze.** `data-analyst` (Sonnet) implements the plan into saved result
   objects. Independent analyses/datasets run as parallel `Task` calls.
3. **Verify — Gate 1.** `code-verifier` (Sonnet, fresh context) checks the
   *implementation*: logic vs. the plan, static checks, tests, and one independent
   re-derivation of a headline number. Defects go back to the analyst,
   **≤ 2 fix cycles**; must PASS before any figures/report.
4. **Figures & report.** `figure-builder` then `report-writer` (Sonnet), built
   from saved results only — never recomputing science in plot/report code.
5. **Audit — Gate 2.** `scientific-auditor` (Opus, independent) audits the
   *science* against the plan → `audit_report.md` (PASS / REVISE / FAIL). On
   REVISE/FAIL the `planning-architect` issues a **scoped** re-plan → re-analyze →
   re-audit, capped at **2 iterations**, then STOP with `SESSION_NOTES.md` rather
   than ship a questionable result.
6. **Archive.** `lesson-archivist` (Sonnet) appends a dated entry to
   **`/learning/LESSONS.md`** (what worked, what failed + root cause, standing
   rules); it runs on PASS and on a bounded STOP/FAIL. That file is **fed
   forward** — the architect reads it at the start of the next run, so the
   pipeline stops repeating the same mistakes.

**Invariants (never violate):** no agent approves its own work; the auditor is
independent of the analyst and reads no self-justifications; a result is never
marked human-approved without a human. A bounded stop is the safety model working
as intended, not a failure — hand off via `SESSION_NOTES.md`.

**The bundled agents (7):** `planning-architect` (Opus), `data-analyst` (Sonnet),
`code-verifier` (Sonnet), `figure-builder` (Sonnet), `report-writer` (Sonnet),
`scientific-auditor` (Opus), `lesson-archivist` (Sonnet). **The bundled skills
(8):** `/plan-analysis`, `/run-analysis`, `/verify-code`, `/make-figures`,
`/write-report`, `/audit-science`, `/archive-lessons`, `/setup-venv`. The
architect and the auditor use the most capable model because their judgment sets
the quality of everything downstream; the rest use a faster, cheaper model.

### 5.1 Parallelize independent work within the flow

The rule that spans every level: **parallelize independent work, pipeline
dependent work.** Never parallelize steps that consume each other's output —
sequence those. Use whichever levels fit; keep everything under the caps in §6.

**Sub-agent level (the `Task` tool).** Run independent work concurrently and keep
the main context small. Send independent `Task` calls **in one message** so they
run at once. Good uses:

- **Independent analyses / datasets** in parallel (one agent each).
- **Write vs. verify:** the `data-analyst` writes; a fresh `code-verifier` reviews
  and tests it independently — the single best way to drive bugs out fast.
- **Overlap phases:** build figures while the report outline is drafted.

Give each sub-agent a small, well-scoped job and the exact files/paths it needs.
The single best pairing is **write vs. verify** — the `data-analyst` writes while
a fresh `code-verifier` reviews and tests independently (Gate 1). (The full
agent/skill roster and the order they run in are in the flow above.)

**Your own tool calls.** When several reads, greps, or independent shell probes
don't depend on each other, issue them **in a single message** so they run
concurrently instead of costing a round-trip each.

**Code level (inside the analysis).** Reach for these in order:

- **Vectorize first.** NumPy/pandas array ops beat Python loops by far and add no
  process overhead — this is usually the biggest single speedup.
- **Then a pool for independent CPU-bound work:** `joblib.Parallel` or
  `concurrent.futures.ProcessPoolExecutor` over independent sessions/animals/
  folds; a `ThreadPoolExecutor` is enough for I/O-bound work.
- **Chunk** large inputs, map over chunks, and stream each result to disk as it
  finishes so a failure loses only one chunk.

**OS level.** Independent commands can run as concurrent background jobs, but only
a **bounded** number at once.

---

## 6. Use the machine's compute (CPU threads + GPU) without crashing it

Full utilization is a goal, but a thrashing or OOM-killed machine finishes
nothing. **Measure first, leave headroom, cap everything.**

**Measure before you allocate.** Read the logical core count
(`os.cpu_count()`), check *available* (not total) RAM before big allocations,
confirm free disk before large writes, and probe the GPU before using it
(`nvidia-smi`, or `torch.cuda.is_available()` / `torch.cuda.mem_get_info()`).
**Always keep a CPU fallback** — never hard-crash because the GPU is absent or
busy. Cache these facts in `SESSION_NOTES.md`.

**Leave headroom — don't grab everything.**

- **Worker count = `min(cores − 1 or − 2, n_tasks)`.** Leaving a core or two free
  keeps the machine responsive.
- **RAM:** budget a fraction of *free* memory (≤ ~70–80%); size chunk/batch
  counts to that. Estimate an array's bytes (elements × dtype size) and refuse
  jobs that won't fit with margin.
- **VRAM:** size batches to fit with margin; don't pre-allocate all of it. Use
  **mixed precision** to cut memory and time, and free/empty the cache between
  large stages.

**Avoid the oversubscription trap (the most common self-inflicted slowdown).**
NumPy/SciPy/scikit-learn/PyTorch already spawn one BLAS/OpenMP thread per core.
If you *also* launch a pool of size *N*, you get up to *N × cores* threads
fighting over *cores* CPUs — it pegs at 100% doing less work, and can exhaust
memory. **Pick one layer to parallelize, not both:**

- When you run your own `joblib`/multiprocessing pool, pin each worker's math
  libraries to one thread — set `OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
  `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS` (and `VECLIB_MAXIMUM_THREADS` on
  macOS) to `1` — **before** NumPy is imported, or use a `threadpoolctl`
  limiter. Otherwise let the library thread internally and don't also fan out.

**Memory discipline for large data.** Stream and chunk instead of loading
everything; memory-map big arrays (`numpy.memmap`, chunked `h5py` reads); delete
large temporaries promptly; don't accumulate every intermediate in a list. Bound
memory so the OOM killer never silently takes a worker.

**GPU discipline.** One process per GPU unless you deliberately share; move data
to the device in **batches**, not all at once; on out-of-memory, **halve the
batch size and retry** (bounded) rather than crashing.

**Monitor and back off.** For long jobs, sample `nvidia-smi`/`psutil`
periodically and log it; if memory or load nears the ceiling, cut concurrency or
batch size. A job that runs at 80% and finishes beats one that maxes out and gets
killed at hour three.

---

## 7. Data hygiene

- Treat raw data and anything under `data/`, `raw/`, `DATA/`, `fixtures/`, or a
  validated-kernel folder as **read-only** unless the user explicitly said to
  write there. Read freely; never overwrite.
- Reuse existing validated functions instead of re-deriving them.
- Add **no new dependency** — installs are blocked mid-run. If a package is
  missing, log it and continue with what's available, or stop and note it.
- Keep all new outputs under the working project (e.g. `analysis/`, `results/`,
  `figures/`, `report/`).

---

## 8. Figures (PNG + PDF)

- Headless matplotlib (`MPLBACKEND=Agg`, set by the bundle).
- Build figures **from saved result objects**, never by recomputing science in
  plot code.
- Save each figure as **both** `figures/<name>.png` (dpi≈200,
  `bbox_inches="tight"`) and `figures/<name>.pdf` (vector); add a `.txt` sidecar
  naming the source result file.
- Label axes with units, add legends, state N and exclusions, use a
  colorblind-safe palette, and keep panels consistent. Confirm each file is
  non-empty.

---

## 9. Reports (DOCX by default, optional PDF)

- Build `.docx` with python-docx via `"$AR_PY"`.
- **Every number is injected from a saved result object** — N, means, effect
  sizes, p-values, CIs, table cells. Never hand-type a statistic. Resolve derived
  aggregates (counts, joins) to literal values.
- **Zero leftover `{{placeholder}}` tokens:** after rendering, scan the document
  text and re-render if any remain.
- Include Methods (data source, interpreter/venv, seed, key parameters), Results
  with embedded figures + captions, brief Discussion/Caveats, and a
  reproducibility footer (exact command + result-file names).
- PDF only if requested and a converter or matplotlib `PdfPages` path is
  available; otherwise deliver the DOCX and say PDF wasn't produced.

---

## 10. Long unattended runs — durability

- **Checkpoint often** (§4.5) so progress survives a crash or a context
  compaction.
- Bound loops: never write an unbounded retry/`while True`. Give every retry a
  small cap and log when the cap is hit.
- If running headless via `-p`/`--print`, set a sensible `--max-turns` to prevent
  runaway loops, capture `--output-format json` for the cost/turn summary, and
  point the run at the right model with `--model`.
- Keep a running `SESSION_NOTES.md`: what ran, where outputs are, the resource
  facts from §6, and the exact next command. It is the handoff if the run ends
  early.

---

## 11. When to stop instead of guessing

Autonomy does not mean guessing on irreversible or ambiguous things. **Stop and
write a short `SESSION_NOTES.md`** (what ran, what remains, the exact next
command) when:

- the interpreter/venv can't be confirmed;
- a result contradicts a stated assumption or looks scientifically wrong;
- the only way forward is a blocked or irreversible action;
- the task is genuinely ambiguous in a way that changes the deliverable.

Otherwise: state your assumption in one line and proceed. Finish by summarizing
what was produced and where — never sign off on results as human-approved.
