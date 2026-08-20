# Prediction Markets (ForecastEx) — Gate Findings (2026-08-20)

Backlog #9, the only genuinely independent, unblocked, uninvestigated strategy on the list. Gated
under the new standalone-first rule (Constitution v1.1.0): would this be worth running on its own
capital?

**Verdict: REJECT on liquidity. The data is the best of any candidate in this program — free, rich,
daily, ~2 years deep — but the market is far too thin to absorb meaningful capital, and my own
attempt to measure an edge produced three contradictory answers.**

---

## 1. What it is

ForecastEx is a **CFTC-registered** Designated Contract Market and clearinghouse for Forecast
Contracts — binary yes/no claims on economic, political and climate outcomes, reachable through IBKR.
Contracts settle at $1.00 or $0.00. Maturities run from weeks to **2047**.

Two structural features are unlike anything else in this program:

- **Fully collateralised.** A YES/NO pair is minted from $1.00, so there is no borrowing and no
  financing drag — the constraint that has killed almost everything else here simply does not exist.
- **Interest is paid on collateral.** Holding a position earns carry rather than paying it.

## 2. Data gate — PASS, and it is excellent

Free, unauthenticated CSV over a plain URL:

```
https://www.forecastex.com/api/download?type=prices&date=YYYYMMDD
```

Three file types daily (`prices`, `pairs`, `summary`). The prices schema is complete:

```
event_contract, subtype, expiration_date, date, start_price, high_price,
low_price, end_price, settlement_price, pair_quantity, open_interest, vwap
```

History runs back to at least 2024-09 (421 rows) and grows to 25,818 rows by 2026-08. A fortnightly
sample over ~2 years gives **377,485 observations across 86,121 contracts**.

**This is the best data situation of any candidate assessed.** No subscription, no roll-adjustment
problem, explicit settlement prices, and volume and open interest included.

## 3. No arbitrage in the pair

YES + NO sums to **exactly 1.0000** for every contract with both sides quoted — complementarity is
structurally enforced, as it must be when pairs are minted from $1 collateral. The apparent
violations (7,229 of 12,909 contracts) are all unquoted contracts showing 0.00 on both sides.

## 4. The liquidity finding — this is what rejects it

Most recent full day (2026-08-19):

| | |
|---|---|
| Contracts listed | 12,909 |
| Contracts that traded **at all** | **1,028** (8%) |
| Median daily volume among those that traded | **49 pairs** |
| 75th percentile | 188 pairs |
| Contracts trading >1,000 pairs/day | **200** |

A contract is $1, so the median traded contract turns over **$49 a day**. Even the ~200 most active
names do about $1,000 a day. Open interest is meaningful in aggregate (17.4M) but daily flow is not.

**A strategy that cannot be filled is not a strategy.** Building even a $30k position — the size of
the VIX satellite deployed this week — would mean being a large fraction of daily volume across
dozens of contracts for days. This fails the same cost-and-liquidity filter that killed intraday FX.

## 5. The calibration question — unresolved, and my analysis was biased

I tried three times to measure whether prices predict outcomes, and got three different answers:

| Definition of a "genuine" price | n | mean price | realised YES | apparent edge |
|---|---|---|---|---|
| `0 < price < 1` | 140 | 0.544 | 0.636 | **+9.2pp** (p=0.034) |
| `YES + NO == 1.00` | 22 | 1.000 | 1.000 | 0.0pp |
| `vwap > 0` (actually traded) | 44 | 0.409 | 0.750 | **+34pp** |

**None of these should be believed, and the first one was my own fault.** Requiring `price > 0`
systematically deletes contracts whose YES price decayed to zero — that is, the losers. A filter that
drops losers will always find an edge.

The deeper problem is that **every cut shows realised YES above price**, which is not what a real
mispricing looks like — a genuine favourite-longshot bias produces errors in *opposite* directions at
the two ends. A uniform positive bias across every definition is the signature of selection in how
resolved contracts are identified: a contract enters the sample only if a fortnightly snapshot happens
to catch it at or after expiry, and there is no reason to assume that capture is independent of outcome.

Two further problems: the samples are 22–140 contracts, and the data does not distinguish "priced at
zero" from "not quoted" — both appear as 0.00.

**So: no edge is claimed, in either direction.** The question is open, and answering it would need
daily rather than fortnightly downloads, the `pairs` and `summary` files to disambiguate quoting
conventions, and a proper settled-contract universe rather than one inferred from snapshots.

## 6. What would change the verdict

- **Liquidity growing.** The venue is young and the contract count is rising fast (421 → 25,818 rows
  in under two years). If daily volume follows, revisit. That is a "check again in a year" item, not
  a research task.
- **A capital-light expression.** The liquidity objection is about size, not about the edge. If the
  calibration question were resolved *and* the answer were large, a few thousand dollars could still
  be deployed — but that is not worth the operational cost at this book's scale.
- **The interest-on-collateral angle** is the one structurally interesting feature and it is a
  cash-management idea, not a strategy: a YES/NO pair is a synthetic $1 held to settlement, so the
  return is whatever interest is credited. Worth a look only if that rate beats SGOV, and it is capped
  by the same liquidity.

## 7. What this cost

An afternoon, no money, no code committed. The data-acquisition path is written down above and works,
so a future revisit starts from a URL rather than from scratch.

**And it produced a reusable methodological warning**: a filter that requires a non-zero price
silently deletes the losers. That mistake would have been invisible in any strategy backtest built on
this data, and it very nearly went into the record as a significant result.
