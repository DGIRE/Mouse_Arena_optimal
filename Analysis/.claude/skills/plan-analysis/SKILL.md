---
name: plan-analysis
description: Turn a scientific request into a pre-registered analysis PLAN with acceptance criteria before any code is written. Use FIRST on any analysis run, and again when the scientific auditor returns REVISE. Reads prior lessons.
---

# plan-analysis — request → pre-registered PLAN

1. Delegate to the `planning-architect` agent (Opus; Read/Write/Grep/Glob only —
   it does not run or write analysis code).
2. It FIRST reads `/learning/LESSONS.md` and the data docs
   (schema/README/conventions).
3. It writes `PLAN.md` (human) + `plan.json` (machine), versioned, containing:
   restated goal + hypotheses (H1/H0); exact data scope + inclusion/exclusion
   rules; methods, tests, null/control models, multiple-comparison handling, and
   every window/parameter WITH a one-line justification derived from the data;
   deliverables (result objects, what each figure must show, report sections);
   ACCEPTANCE CRITERIA (definition of done) + guardrails; risks/assumptions to
   validate on the first slice; a task graph (independent vs dependent stages).
4. On an audit REVISE: it issues a SCOPED, minimal revision directive and bumps
   the plan version — not an open-ended redo.
5. If the goal is ill-posed or the data can't support it: STOP and write
   `SESSION_NOTES.md`.

Output: the plan file paths + acceptance criteria — the baseline the
`scientific-auditor` (`/audit-science`) checks against.
