# Autonomous Coding — General Best Practices for Safe, Efficient, Unattended Agents

**Audience:** any Claude Code CLI agent, on any machine, that will write and run
code — data analysis, builds, scripts, model training, reports — **without a
human clicking permission prompts**, possibly for hours. Read this at the start
of an autonomous session and keep to it. It is environment-agnostic: it assumes
no particular project bundle, virtual environment, or set of helper agents. When
a project ships its own guide, that project's rules win where they are more
specific; this document is the baseline everywhere else.

**The four goals, in priority order:**

1. **Safe** — never destroy data, exfiltrate anything, or mutate the machine in a
   way you can't undo.
2. **Correct** — results a careful engineer or scientist can trust.
3. **Autonomous** — no stalls waiting on a prompt, no runaway loops.
4. **Frugal & fast** — few tokens, few reruns, and full use of the hardware
   without tipping it over.

Safety and correctness are never traded away for speed. Everything below serves
these four, in this order.

---

## 1. Run in the right permission mode

Pick the least-privileged mode that still lets the work proceed unattended:

- **`acceptEdits`** — auto-approves file edits and reads; individual shell
  commands are still governed by your allow/deny configuration. Good default
  when edits dominate and shell work is routine.
- **`auto`** (a.k.a. auto-accept) — auto-approves ordinary work and blocks
  actions that look dangerous. Good default for mixed edit-and-run sessions.
- **`plan`** — read-only planning; nothing is executed. Use it to scope work
  before switching to an executing mode.
- **`bypassPermissions` / `--dangerously-skip-permissions`** — skips **all**
  checks. Use **only** in a throwaway or sandboxed tree with no real data,
  never on a machine or repository you care about.

Configure guardrails once, at the start, if you control the settings: a
**deny-list** of destructive, network, install, and publish commands, and — if
available — a **pre-execution hook** that blocks the same classes shell-agnostically. Treat these as backstops that must not be circumvented.

**If an action is blocked, that is a signal, not an obstacle.** Adapt to an
allowed approach; never retry the blocked form in a cleverer shell, and never
edit your own guardrails to get around them.

---

## 2. Know your environment before you act

Most silent failures come from running the wrong interpreter, in the wrong
place, against resources you never checked. Spend the first minute establishing
ground truth, then cache it:

- **Interpreter.** Find and use the *project's* Python (or Node, etc.), not
  whichever bare `python`/`python3` happens to be first on `PATH` — that often
  resolves to a system or Anaconda install with a different package set that will
  fail on import. Prefer an activated virtual environment or an explicit absolute
  path; confirm the key packages import **before** starting a long run. If you
  can't confirm the right interpreter, **stop and leave a note** rather than
  guessing or installing.
- **OS & paths.** Note the platform, the working directory, and the absolute
  paths of inputs and outputs. Don't assume Unix tools on Windows or vice-versa.
- **Resources.** Establish the CPU core count, available RAM, free disk, and
  whether a usable GPU exists (see §6). You cannot use hardware safely without
  first measuring it.

Write these facts into a short notes file so a resumed session doesn't re-derive
them.

---

## 3. Command style that avoids needless prompts and wasted tokens

Permission heuristics can force an approval prompt — a stall, when unattended —
on commands that *look* risky. Keep commands boring and legible:

- **Write code to a file and run the file.** Avoid `python -c "…"` with long
  inline programs or heredocs; don't paste hundred-line scripts inline. Both trip
  length/parse heuristics and waste tokens.
- **One simple command at a time.** Chains like `cd "…" && … 2>&1 | tail` often
  force approval. Pass absolute paths and script arguments instead of `cd`.
- **Quote paths; prefer forward slashes; don't over-escape.**
- **Never scan the whole filesystem** (`find / …`, recursive greps from root).
  Inputs live at known paths — go straight to them.
- **Log, don't flood.** Redirect long program output to a file and read only the
  tail (`… > logs/run.log 2>&1`, then read the last lines). Dumping thousands of
  lines into context is the single biggest avoidable token cost. Use focused
  searches with caps, not unbounded dumps.
- **Don't re-read what you just wrote** or re-verify what already passed. One
  good pass beats a dozen anxious re-checks.

---

## 4. The efficient, bug-averse loop

Producing correct code quickly is mostly about catching errors while they are
cheap, not about cleverness.

1. **Plan in a few lines, then act.** Name the inputs, outputs, and the 2–4 real
   steps. Don't over-plan or narrate every keystroke.
2. **Skeleton before compute.** Write the module with a `main()`, a **fixed
   random seed**, and a tiny assert-based self-check (expected shapes, a known
   value) *before* the expensive part.
3. **Static-check every file the moment you write it.** A compile/syntax check is
   instant and catches typos; a fast unit test on a small fixture catches logic
   errors. This is orders of magnitude cheaper than discovering the bug an hour
   into the full run.
4. **Slice first, then scale.** Run on one item / a small subset, confirm shapes
   and ranges are sane (not all-NaN, not all-zero, units plausible), *then* run
   the full job.
5. **Checkpoint to disk.** Write intermediate results and guard heavy stages with
   "if a fresh output already exists, skip it." A crash or a context compaction
   then resumes instead of restarting from zero.
6. **Isolate failures.** Wrap each independent stage so one failure degrades to a
   logged skip/NaN and the run continues; only the headline result is allowed to
   hard-fail.
7. **Prefer complete, working edits over partial stubs**, and don't repeat work
   already done.

---

## 5. Parallelize independent work

Parallelism is a force multiplier at three levels. Use whichever fit; the rule
that spans all three is **parallelize independent work, pipeline dependent work.**

**Agent level (your own tool calls).**
- When several tool calls have **no dependency on each other's results**, issue
  them **in a single message** so they run concurrently — batched reads, greps,
  and independent shell probes finish in one round-trip instead of many.
- Delegate large, independent sub-tasks to **sub-agents launched together in one
  message** (e.g. one per dataset, or a "write" agent and an independent "review
  and test" agent). Parallel independent analyses keep the main context small and
  surface bugs faster. Give each a tightly scoped job and the exact paths it
  needs.
- **Do not** parallelize steps where one needs another's output — sequence those
  as a pipeline.

**Code level (inside your programs).**
- Prefer **vectorization** (NumPy/array ops, dataframe operations) over Python
  loops before reaching for parallelism at all — it is usually the biggest win.
- For genuinely independent CPU-bound work, use a **process pool**
  (`concurrent.futures.ProcessPoolExecutor`, `multiprocessing`, or `joblib`);
  for I/O-bound work, a **thread pool** is enough.
- **Chunk** large inputs and map over chunks; stream results to disk as they
  complete so a failure loses only one chunk.

**OS level (independent commands).**
- Independent shell jobs can run concurrently (background jobs, or a small job
  runner), but always with a **bounded** number in flight.

**The caps that keep parallelism from backfiring** are in §6 — unbounded
fan-out is how a fast run becomes a crashed machine.

---

## 6. Use the machine's compute (CPU threads + GPU) without crashing it

Full utilization is a goal, but a crashed or thrashing machine finishes nothing.
Measure first, leave headroom, and cap everything.

### Measure before you allocate
- **CPU:** read the logical core count (e.g. `os.cpu_count()`); note that logical
  ≠ physical when hyper-threading is on.
- **RAM:** check available (not total) memory before allocating big arrays;
  estimate an array's bytes (elements × dtype size) and refuse jobs that won't
  fit with headroom.
- **GPU:** detect presence and free memory before use (`nvidia-smi`, or the
  framework's own probe such as `torch.cuda.is_available()` /
  `torch.cuda.mem_get_info()`). **Always have a CPU fallback** if no usable GPU
  is found — never hard-crash because a GPU is absent or busy.
- **Disk:** confirm free space before writing large outputs; a full disk fails
  writes while deletes still work.

### Leave headroom — don't grab everything
- **Worker count = `min(cores − 1 or − 2, number_of_tasks)`.** Leaving a core or
  two free keeps the machine responsive and leaves room for the OS and for you.
- **Memory:** target a fraction of *free* RAM (e.g. ≤ 70–80%), not total; size
  batch/chunk counts to that budget.
- **GPU memory:** size batches to fit VRAM with margin; don't pre-allocate all of
  it. Where the framework allows, enable incremental/growth allocation, use
  **mixed precision** to cut memory and speed things up, and **free/empty the
  cache** between large stages.

### Avoid the classic oversubscription trap
This is the most common way "more parallelism" makes things *slower* or crashes
them: **nested parallelism multiplies threads.** BLAS/OpenMP-backed libraries
(NumPy, SciPy, scikit-learn, PyTorch CPU) each already spawn one thread per core.
If you then launch a process pool of size *N*, you can get *N × cores* threads
fighting over *cores* CPUs — cache-thrashing that pegs the machine at 100% while
doing less work.

- When you run your own multiprocessing/`joblib` pool, **pin each worker's math
  libraries to one thread**: set `OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
  `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS` (and `VECLIB_MAXIMUM_THREADS` on
  macOS) to `1` in the workers, *or* let the library thread internally and don't
  also fan out with processes. **Pick one layer to parallelize, not both.**
- Set these env vars **before** NumPy/BLAS is imported, or use a thread-limit
  context manager (e.g. `threadpoolctl`).

### Memory discipline for large data
- **Stream and chunk** instead of loading everything: read HDF5/Parquet/CSV in
  pieces, process, write, release.
- **Memory-map** big arrays (`numpy.memmap`, chunked `h5py` reads) so the OS pages
  them instead of holding all of it resident.
- Delete large temporaries promptly and avoid keeping every intermediate in a
  list. Watch for the OOM killer silently killing a worker — bound memory so it
  never gets there.

### GPU discipline
- **One process per GPU** for training/inference unless you deliberately share;
  concurrent processes on one GPU usually just exhaust VRAM.
- Move data to the device in **batches**, not all at once; keep the input
  pipeline off the critical path.
- On out-of-memory, **halve the batch size and retry** (bounded), rather than
  crashing the run.

### Monitor and back off
- For long jobs, **sample utilization periodically** (a lightweight `nvidia-smi`
  or `psutil` probe) and log it. If memory or load is near the ceiling, reduce
  concurrency or batch size rather than pushing until it dies.
- Prefer **throughput to disk over speed into a wall**: a job that runs at 80%
  and finishes beats one that maxes out and gets killed at hour three.

---

## 7. Data hygiene

- Treat raw inputs — anything under `data/`, `raw/`, `DATA/`, `fixtures/`, or a
  known validated-data folder — as **read-only** unless the user explicitly said
  to write there. Read freely; never overwrite in place.
- **Reuse existing validated functions** instead of re-deriving logic that
  already exists and is tested.
- **Add no new dependency mid-run** unless installs are explicitly permitted —
  they are commonly blocked, and a half-installed environment is worse than a
  missing feature. If a package is missing, log it and continue with what's
  available, or stop and note it.
- Keep all new outputs under the working project (e.g. `analysis/`, `results/`,
  `figures/`, `report/`), never scattered across the machine.

---

## 8. Long unattended runs — durability

- **Checkpoint often** (§4.5) so progress survives a crash or a context
  compaction.
- **Bound every loop.** Never write an unbounded retry or `while True`; give each
  retry a small cap and log when the cap is hit.
- If running fully headless (a single non-interactive invocation), set a sensible
  turn/step limit to prevent runaway loops, capture the run's cost/turn summary if
  available, and target the intended model explicitly.
- Keep a running **`SESSION_NOTES.md`**: what ran, where the outputs are, the
  resource facts from §2, and the exact next command. It is the handoff if the
  run ends early.

---

## 9. When to stop instead of guessing

Autonomy is not a license to guess on irreversible or ambiguous things. **Stop
and write a short `SESSION_NOTES.md`** (what ran, what remains, the exact next
command) when:

- the correct interpreter/environment can't be confirmed;
- a result contradicts a stated assumption or looks clearly wrong;
- the only way forward is a blocked or irreversible action;
- the task is genuinely ambiguous in a way that changes the deliverable.

Otherwise: **state your assumption in one line and proceed.** Finish by
summarizing what was produced and where — and never sign off on results as
human-approved when no human approved them.
