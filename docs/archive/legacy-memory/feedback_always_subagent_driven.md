---
name: Always execute plans subagent-driven in the forex project (don't ask)
description: For the forex project, always execute implementation plans with superpowers:subagent-driven-development. Do NOT ask which execution mode (subagent-driven vs inline) — the user has standing approval for subagent-driven.
metadata:
  node_type: memory
  type: feedback
---

2026-07-12: The user said "always use the subagent driven option for this project, no need to ask."

**Why:** it's the established, working flow (fresh implementer subagent per task on a cheap model,
sonnet spec+quality review between tasks, opus final whole-branch review). It has repeatedly caught
real defects the implementers missed (the day-0 turnover cost, the percent-vs-decimal FRED rate bug,
dead imports after refactors, the dead `--cadence` trap flag).

**How to apply:** after writing-plans produces a plan for the forex project, skip the "which execution
approach?" question and go straight to `superpowers:subagent-driven-development`. Standing conventions
for these runs: branch `impl/<feature>`, a `.superpowers/sdd/progress.md` ledger, per-task
task-brief + review-package scripts, haiku implementers / sonnet reviewers / opus final review,
fast-forward merge to `main` when the final review is clean, delete the branch.
