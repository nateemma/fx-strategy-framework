# Memory — forex

Project-specific findings and war-stories for this repo. One file per fact under `memory/`; this file
is the index. Findings that generalise across trading projects belong in
`~/.claude/quant-research-lessons.md` instead.

- [Paper track live state](memory/paper-track-live-state.md) — DUQ218063 is ~90% ETF sleeves by value; the FX book is a cash overlay on top.
- [FX legs are cash, not positions](memory/fx-legs-are-cash-not-positions.md) — settled FX is CashBalance and the carry is in AccruedCash; read the book with `forex.run.fxbook`.
- [Sleeve table is design, not deployment](memory/sleeve-table-is-design-not-deployment.md) — the README lists sleeves that may hold nothing; a sleeve that has never placed has never had its guards exercised.
- [Launchd schedule state](memory/launchd-schedule-state.md) — six agents scheduled and verified; the 2026-08-01 miss means launchd has still never exercised the fix.
- [Claude memory stranded by the repo move](memory/claude-memory-stranded-by-repo-move.md) — 25 pre-migration memories archived under `docs/archive/legacy-memory/`, deliberately not rehydrated.
