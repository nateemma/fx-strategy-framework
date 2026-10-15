# Memory — forex

Project-specific findings and war-stories for this repo. One file per fact under `memory/`; this file
is the index. Findings that generalise across trading projects belong in
`~/.claude/quant-research-lessons.md` instead.

- [Paper track live state](memory/paper-track-live-state.md) — **STOPPED 2026-10-14**; what DUQ218063 held when it froze (~90% ETF sleeves, FX as a cash overlay), positions left in place.
- [FX legs are cash, not positions](memory/fx-legs-are-cash-not-positions.md) — settled FX is CashBalance and the carry is in AccruedCash; read the book with `forex.run.fxbook`.
- [Sleeve table is design, not deployment](memory/sleeve-table-is-design-not-deployment.md) — the README lists sleeves that may hold nothing; a sleeve that has never placed has never had its guards exercised.
- [Launchd schedule state](memory/launchd-schedule-state.md) — **all seven agents unloaded 2026-10-14**; historical record of how the schedule worked and what it taught.
- [Claude memory stranded by the repo move](memory/claude-memory-stranded-by-repo-move.md) — 25 pre-migration memories archived under `docs/archive/legacy-memory/`, deliberately not rehydrated.
- [Gateway Sunday re-authentication](memory/gateway-sunday-reauth.md) — both outages began on a Sunday; IBC retries an expired TOKEN auth instead of falling back to PASSWORD auth, which works unattended in 4s.
- [Free data ceiling](memory/free-data-ceiling.md) — what FRED + the chart API can and cannot supply, the three measured traps, and why data is the binding purchase.
- [IBKR futures history is too short](memory/ibkr-futures-history-is-too-short.md) — **subscription cancelled 2026-10-15**; ~2 years of micros was always the real blocker, and a competing login zeroes all market data.
