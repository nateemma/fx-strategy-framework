---
name: free-data-ceiling
description: What the free data tier (FRED + the Yahoo chart API) can and cannot supply, with the measured traps — this is the constraint that closed half of spec 009, and the reason the highest-value purchase is data rather than a model or a broker
metadata:
  node_type: memory
  type: project
---

Measured during spec `009` (2026-10-15), when six candidates were gated and **three died because the
free tier does not reach**. Worth one place to look before proposing any strategy, because the
answer to "can I test this for free?" decided more verdicts than any model did.

## What the free tier HAS

| Source | Supplies | Depth measured |
|---|---|---|
| FRED | Treasury yields (`DGS2`, `DGS10`) | **1976** → present, 12,588 obs |
| FRED | TIPS / breakevens (`T10YIE`, `DFII10`) | 2003 → present, ~5,950 obs |
| Chart API | Adjusted daily closes, equities and ETFs | ETF inception (IEF/SHY 2002, TIP 2003, HYG 2007) |
| Chart API | Index levels (`^GSPC`) and continuous futures (`ES=F`) | 1990 / 2000 → present |

## What it does NOT have — the three that killed candidates

- **ICE BofA credit spreads are licence-limited to a rolling ~3 years.** `BAMLH0A0HYM2` (high yield)
  and `BAMLC0A0CM` (investment grade) **both start 2023-10-16** — the same date, while Treasury
  series go back decades. That is a licence window, not an outage, and three years cannot span two
  temporally distant eras, so any credit-spread signal is untestable at any level of effort.
- **No per-fund NAV / discount history.** Killed CEF discount mean-reversion.
- **No bulk earnings dates or surprise magnitudes.** Killed post-earnings-announcement drift.

## Three traps in the chart API, each measured

1. **`range=max&interval=1d` silently returns MONTHLY bars.** 292 bars for IEF against **6,093** from
   an explicit `period1`/`period2` range. Nothing errors and the response still claims daily. Always
   send an explicit period range and **assert `meta.dataGranularity`** — `forex/data/yahoo.py` does.
2. **Bars are stamped at the market open, not midnight.** Joining an un-normalised index to a
   FRED series produced a **zero-length** intersection. It failed loudly here; a partial overlap
   would have been silent. The loader normalises.
3. **`SPY × 10` is not SPX.** SPY pays its dividends out, so it drifts ~24% below the index over two
   decades. Using it as an index proxy produced a nonsense "+2416bp futures basis" that was actually
   cumulative dividend drift. Use `^GSPC`.

**Why:** these are not code facts — they are properties of external sources that will be
rediscovered expensively, and two of the three traps produce a *plausible wrong number* rather than
an error, which is this repo's documented failure mode.

**How to apply:** before costing any new strategy, check whether its *signal* series is deep enough
for a two-era split — not merely whether it loads. Spec 009's feasibility probe originally checked
only that a series loaded, so the credit candidate passed the cull and came back from its gate with
one usable window.

And the standing conclusion: of everything that blocked this programme, **data is the binding
purchase** — credit history, CEF NAV, earnings surprises, and the Databento futures series that
already blocks the trend sleeve and commodity carry. Not a better model, and not a different broker.
See [[ibkr-futures-history-is-too-short]] and [[paper-track-live-state]].
