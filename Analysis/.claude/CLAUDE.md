# Autonomous Data-Analysis Operating Manual (home `~/.claude`)

This file is loaded into every Claude Code session started from this machine. It
configures Claude to write data-analysis code, produce figures (PNG/PDF), and
write reports (DOCX/PDF) **autonomously and safely** — running for hours without
asking the user to click permission prompts. Full rationale lives in
`AUTONOMOUS_CODING_BEST_PRACTICES.md` (same repo folder). The rules below are
binding.

## 1. Interpreter — the single most important rule
Run **all** Python (analysis, figures, reports, tests) with the quoted env var:

```
"$AR_PY" path/to/script.py
"$AR_PY" -m pytest tests/ -q
```

`$AR_PY` points at the project venv (default: `…/vras/Scripts/python.exe`)
and has numpy, scipy, pandas, scikit-learn, statsmodels, h5py, matplotlib, and
python-docx. **Never** use bare `python`, `py`, `python3`, or an Anaconda path —
on this machine those resolve to the wrong interpreter and will fail on import.
If the SessionStart `[venv]` line reports the venv was **not** found, ask the
user for a venv path once; if unattended and none can be confirmed, STOP and
leave a note. Do not `pip install` mid-run (the guard blocks it) — if a package
is missing, record it and continue with what is available.

## 2. Autonomy & safety model (why you won't be prompted, and what's blocked)
Run mode is `--permission-mode auto` (or `acceptEdits`). Prompts are skipped; you
are trusted to edit files and run analysis. Two backstops keep it safe and always
apply — do **not** try to work around them:
- **deny-list** (settings.json): blocks destructive/network/install/publish bash.
- **guard hook** (`hooks/guard_bash.py`, exit 2): the same, shell-independent,
  active even in bypass mode.
If a command is blocked, it means it doesn't belong in an unattended run. Adapt
(write to a new file, use the venv you have, skip the fetch) — never retry the
blocked form or disable the guard. Treat raw data and anything under a `data/`,
`raw/`, `DATA/`, `fixtures/`, or kernel folder as **read-only** unless the user
explicitly told you to write there.

## 3. Command style that keeps the run smooth (avoids accidental prompts)
- Put analysis code in a **`.py` file** and run the file. Do **not** use
  `python -c "…"` with long inline heredocs/`#` comments, and do not paste
  multi-hundred-line scripts inline — both can trip permission heuristics.
- Prefer **single, simple commands** over `cd "…" && … 2>&1 | tail` chains. Use
  absolute paths and script args instead of `cd`.
- Keep paths quoted; avoid gratuitous backslash escaping. Never scan the whole
  drive (`find / …`).
- Send long program output to a **log file** and read the tail, rather than
  dumping thousands of lines into context (saves tokens).

## 4. The efficient, bug-averse loop (swift + frugal)
1. **Plan briefly** (a few lines): inputs, outputs, the 2–4 real steps. Don't
   over-plan; don't narrate.
2. **Skeleton first**: write the module with a `main()`, a fixed random seed, and
   a tiny self-check (assert shapes / a known value) before the heavy compute.
3. **Static-check every file you write** immediately:
   `"$AR_PY" -m compileall <file>` and, for logic, a fast `pytest` on a small
   fixture. Catching a syntax/shape error here is far cheaper than a 40-minute
   rerun.
4. **Run on a small slice first** (a subset / one session), confirm it's sane,
   then run the full job.
5. **Checkpoint**: write intermediate results to disk (`.npz`, `.parquet`,
   `.json`) so a long job resumes instead of restarting. Guard heavy stages with
   "if output exists and is fresh, skip."
6. **Fail loudly, isolate locally**: wrap each independent stage so one failure
   degrades to a logged NaN/skip rather than killing the whole run.
7. Don't re-read files you just wrote; don't re-verify what already passed.

## 5. Sub-agents, the run flow, and the two gates
Delegate with the Task tool to keep the main context lean and to get independent
review. Keep each sub-agent's job small with the exact files/paths; run
independent work as parallel `Task` calls and **pipeline dependent steps**. The
full run flow:

1. **Plan.** `planning-architect` (Opus) reads the request, the data docs, and
   **`/learning/LESSONS.md`**, then writes a pre-registered `PLAN.md`/`plan.json`
   (goal + hypotheses, methods, null/control models, exclusion rules, and
   concrete **acceptance criteria**). No analysis code is written here.
2. **Analyze.** `data-analyst` (Sonnet) implements the plan → saved result
   objects. Independent analyses run as parallel `Task` calls.
3. **Verify — Gate 1.** `code-verifier` (Sonnet, fresh) checks the
   *implementation*. Defects → back to the analyst (≤ 2 fix cycles). Must PASS
   before figures/report.
4. **Figures & report.** `figure-builder` then `report-writer` (Sonnet), from
   saved results only.
5. **Audit — Gate 2.** `scientific-auditor` (Opus, independent) audits the
   *science* against the plan → `audit_report.md` (PASS / REVISE / FAIL).
   REVISE/FAIL → `planning-architect` issues a **scoped** re-plan → re-analyze →
   re-audit, capped at **2 iterations**, then STOP with `SESSION_NOTES.md`.
6. **Archive.** `lesson-archivist` (Sonnet) appends a dated entry to
   **`/learning/LESSONS.md`** (what worked, what failed + root cause, standing
   rules). Runs on PASS and on a bounded STOP/FAIL.

Invariants: no agent approves its own work; the auditor is independent of the
analyst; never mark results human-approved without a human. A bounded stop is the
safety model working, not a failure — hand off via `SESSION_NOTES.md`.

Available agents: `planning-architect`, `data-analyst`, `code-verifier`,
`figure-builder`, `report-writer`, `scientific-auditor`, `lesson-archivist`.
Available skills: `/plan-analysis`, `/run-analysis`, `/verify-code`,
`/make-figures`, `/write-report`, `/audit-science`, `/archive-lessons`,
`/setup-venv`.

## 6. Figures
Matplotlib is headless (`MPLBACKEND=Agg`). Save **both** `.png` (150–200 dpi,
`bbox_inches="tight"`) and `.pdf` (vector) to a `figures/` folder. A figure is
built from a saved result object, never by recomputing science in the plot code.
Label axes/units; state N and any exclusions. See `/make-figures`.

## 7. Reports
Default deliverable is **`.docx`** via python-docx (installed in the venv). Every
number, N, p-value, and table cell is **injected from a saved result object** —
never hand-typed. Leave zero `{{placeholder}}` tokens. Embed the figures with
captions. For PDF, render the docx (if a converter is available) or build a
figure-based PDF with matplotlib's `PdfPages`; if neither is possible, deliver
the DOCX and say so. See `/write-report`.

## 8. When to stop and leave a note (don't guess on irreversible things)
Stop and write a short `SESSION_NOTES.md` (what ran, what's left, the exact next
command) when: the interpreter can't be confirmed; a result contradicts a stated
assumption; the only way forward is a blocked/irreversible action; or the task is
genuinely ambiguous in a way that changes the output. Otherwise: state your
assumption in one line and proceed.
