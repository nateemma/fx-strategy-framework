# Memory — forex

Project-specific findings and war-stories for this repo. One file per fact under `memory/`; this file
is the index. Findings that generalise across trading projects belong in
`~/.claude/quant-research-lessons.md` instead.

- [Paper track live state](memory/paper-track-live-state.md) — DUQ218063 is ~90% ETF sleeves by value; the FX book is a cash overlay on top.
- [FX legs are cash, not positions](memory/fx-legs-are-cash-not-positions.md) — settled FX is CashBalance and the carry is in AccruedCash; read the book with `forex.run.fxbook`.
- [Cash sleeve never deployed](memory/cash-sleeve-never-deployed.md) — documented in the README, but no SGOV is held and ~96k sits unparked.
- [Launchd schedule gaps](memory/launchd-schedule-gaps.md) — 3 of the jobs scheduled; the 2026-08-01 FX rebalance silently failed after the repo move and is unvalidated until 2026-09-01.
