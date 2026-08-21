---
name: claude-memory-stranded-by-repo-move
description: 25 pre-migration memories were stranded at the old ~/Documents/forex path; they are archived in-repo and were deliberately NOT rehydrated because the docs of record supersede them
metadata:
  node_type: memory
  type: project
---

Claude Code's file-based memory lives at `~/.claude/projects/<absolute-path-slug>/memory/` — keyed by
the project's **absolute path**. Moving the repo from `~/Documents/forex` to `~/projects/forex` created
a new, empty slug and stranded 24 memory files plus their `MEMORY.md` index at
`-Users-philprice95-Documents-forex`, invisible to every session started from the new location.
Discovered 2026-08-21. The same trap applies to any project moved into `~/projects`.

They are preserved at **`docs/archive/legacy-memory/`** — in the repo, so they now survive path moves
and machines (Constitution V), which the `.claude/` location never did.

**They were deliberately not rehydrated into active memory.** Triaged file by file, essentially all of
it is already in the docs of record at equal or better fidelity: the FX factor verdicts in
`docs/strategy-research-backlog.md`; the commodity, crypto-derivative, equity-factor and cross-asset
tracks in `docs/investable-universe-survey.md` §4; the intraday closures in
`docs/intraday-fx-assessment-plan.md`; the architecture rules in `ARCHITECTURE.md` and Constitution I.

Four would have actively misled if copied forward:

- `feedback_always_subagent_driven.md` — instructs going straight to Superpowers subagent-driven
  development. Superpowers is archived; the repo runs Spec Kit.
- `project_fx_cot_positioning.md` — "WF Sharpe 1.15, best in program". True pre-financing; the actual
  IBKR spreads take it to 0.17.
- `project_fx_deployable_blend.md` — names `carry_trend_voltarget` as the production config;
  superseded by `carry_cot_mom`.
- `project_ibkr_equity_options_track.md` — sleeve allocations predating the cash and VIX sleeves.

**Why:** stale memory is worse than absent memory, because it arrives with the authority of something
already established and is not re-derived. A bulk copy would have re-imported the exact numbers that
features 002/003 were built to correct.

**How to apply:** if an old finding is needed, read `docs/archive/legacy-memory/` deliberately and
check it against the docs of record before acting on it — treat it as historical, like
`docs/archive/`. New facts go in `memory/` + `MEMORY.md`, which are versioned and travel with the repo.
