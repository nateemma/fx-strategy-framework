# Phase 1 Contracts: Standalone Long/Short Candidate Gates

Library functions, script behaviour, and the findings document. No external API is exposed.

---

## A. `forex/data/yahoo.py` (new)

```python
def load_prices(symbol: str, cache_dir="data_cache/yahoo", force: bool = False,
                client=None, start: date | None = None) -> pd.Series
```

Deliberately the same shape as `forex.data.fred.load_series`: positional symbol, `cache_dir`, `force`,
injectable client, parquet cache.

| Concern | Contract |
|---|---|
| Returns | Adjusted daily closes, `DatetimeIndex`, named for the symbol. **Adjusted, not raw** — these are distributing bond and credit ETFs and raw closes would omit most of the return (research R4). |
| Request form | Explicit `period1`/`period2` with `interval=1d`. **Never** `range=max`, which silently returns monthly bars (research R1). |
| **Granularity assertion** | MUST read the granularity the response reports and **raise** if it is not daily. This is the only cheap guard against silently receiving the wrong data, and it guards the feature's worst failure mode — a plausible number computed from the wrong bars. |
| Cache | Parquet per symbol. `force=False` reads cache when present; `force=True` refetches and rewrites. |
| Client | `client=None` uses a lazily-imported `urllib.request` default. Tests inject a stub, so the suite performs **no network I/O** (FR-014, Principle III). |
| Dependencies | Standard library only. No new package. |
| Failure | A failed fetch with a usable cache present returns the cache and says so; with no cache it raises. It MUST never return a silently short series. |

---

## B. `forex/backtest/gate.py` (new)

Pure. No I/O, no network, no broker.

```python
def evaluate(returns: pd.Series, benchmark: pd.Series, *, holdout_years: int,
             cost_bps: float, financing_annual: float,
             borrow_excluded: bool = False, label: str = "") -> GateVerdict
```

| Concern | Contract |
|---|---|
| Era split | Delegates to `validation.distant_window(index, holdout_years)`. `holdout_years` is **required, not defaulted** — the function's own default of 3 is tuned to the FX sample and is wrong for a 24-year history (research R3). |
| Metrics | Delegates to `portfolio.metrics()`, so these figures mean the same thing as every other number in the repo. |
| Costs | Applies `cost_bps` per unit turnover and `financing_annual` on gross exposure **before** any metric is computed. There is no code path that computes a metric on gross returns. |
| Benchmark | Required, not optional. A verdict without a comparator is not a verdict (FR-002). |
| Verdict rules | `pass` requires beating the benchmark in **every** window; fewer than two windows ⇒ `inconclusive`; `borrow_excluded=True` caps the verdict at `inconclusive`. |
| Purity | Same inputs ⇒ same `GateVerdict`. No clock, no filesystem. |

**Invariants, each with a test:**

1. A series beating the benchmark in one window and losing in the other ⇒ `reject`, never `pass`.
2. `borrow_excluded=True` can never yield `pass`.
3. No public function accepts or returns a gross-of-cost return series.

---

## C. `scripts/gate_data_feasibility.py` (new) — the US2 cull

```text
.venv/bin/python scripts/gate_data_feasibility.py [--candidate A3|B2|…]
```

| Concern | Contract |
|---|---|
| Does | One cheap probe per candidate: can the required history be obtained free, and how deep. |
| Emits | A table of `testable` / `dead_on_data` / `dead_on_economics`, with the source checked and the usable span. |
| Does **not** | Build, fit, or backtest anything. It runs *before* modelling (FR-005). |
| Network | Hits only free sources, and caches what it fetches so a probe is not repeated. |
| Budget | Minutes per candidate, not hours. |

---

## D. `scripts/gate_candidate.py` (new)

```text
.venv/bin/python scripts/gate_candidate.py --candidate A3 [--refresh]
```

Loads cached data, computes the candidate's signal and net returns, calls `gate.evaluate()`, and prints
the verdict with its per-window table. Writes nothing to the repo except the data cache; the findings
doc is authored from its output.

---

## E. `docs/standalone-longshort-findings.md` (new)

One document, one section per candidate. The contract here is on **content**, because this document is
the feature's only real output (FR-008, FR-009).

Each section MUST carry: the hypothesis in one sentence; the verdict (`pass` / `reject` /
`inconclusive`); the per-window numbers with the benchmark alongside; the cost and financing basis,
stating explicitly whether borrow cost was excluded; and the reasoning connecting the numbers to the
verdict.

A rejection MUST be reproducible from its section alone — what was measured, against what, and why it
failed — without re-running anything (FR-009). A `pass` MUST state what would have to be true to
deploy, because for several candidates the screen instrument is not the deployable one (FR-011).
