---
name: archive-lessons
description: At end of run (PASS, STOP, or FAIL) distill reusable lessons and APPEND them to /learning/LESSONS.md for future runs. Never overwrites. Keeps an INDEX.
---

# archive-lessons — write the run's lessons forward

1. Delegate to the `lesson-archivist` agent (Sonnet; Read/Write/Grep/Glob).
2. Create `/learning/` if absent. APPEND a dated entry to `/learning/LESSONS.md`
   (never overwrite); keep `/learning/INDEX.md` (one line per entry).
3. Entry: date; experimental purpose/goal; run metadata (interpreter/venv, seed,
   data version/commit, models used, wall-clock, revision iterations); what worked
   (reusable); what failed + ROOT CAUSE; concrete standing rules (next time do X /
   avoid Y); any pitfall the auditor caught + how to prevent it earlier; open
   follow-ups.
4. Keep entries compressed and de-duplicated; promote a recurring lesson into a
   "Standing rules" section at the top of `LESSONS.md`.
5. The `planning-architect` (`/plan-analysis`) reads `/learning` at the start of
   every run — this feed-forward is the point.

Output: the appended entry + the `LESSONS.md` path.
