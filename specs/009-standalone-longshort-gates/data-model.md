# Phase 1 Data Model: Standalone Long/Short Candidate Gates

No database. A candidate register, two verdict records, and a cache layout.

---

## 1. `Candidate` — the register

One row per candidate, defined in code so the gate scripts iterate it rather than hardcoding six
paths. Survey IDs are kept because they are how the backlog refers to these.

| Field | Meaning |
|---|---|
| `id` | Survey ID — `A3`, `B2`, `B3`, `B4`, `B5`, `B6` |
| `name` | Human name, e.g. "Treasury curve 2s10s" |
| `hypothesis` | One sentence: what edge is claimed |
| `signal_series` | Free macro series the signal needs (may be empty) |
| `screen_symbols` | Instruments used to *screen* it |
| `deploy_instrument` | What it would actually trade — **may differ from the screen** |
| `kill_criterion` | The cheap test that ends it, evaluable in hours (FR-007) |
| `shortable_cleanly` | Whether its short leg can be honestly costed — see [research.md](./research.md) R2 |

### The register as planned

| ID | Name | Screen | Deploy | Short leg costable? | Kill criterion |
|---|---|---|---|---|---|
| **A3** | Treasury curve 2s10s | SHY/IEF or SHY/TLT | Treasury futures | Screen: **no**; deploy: **yes** (futures) | No edge in both eras net of cost |
| **B4** | Index futures basis | Index future vs index ETF | Futures vs cash | **Yes** — short side is the future | Basis narrower than round-trip commission |
| **B5** | TIPS breakeven | TIP vs IEF | Pair, or futures | **No** (ETF short) | No edge in both eras net of cost |
| **B6** | Credit spread | HYG/LQD vs IEF/TLT | Pair | **No** (ETF short) | No edge in both eras net of cost |
| **B2** | CEF discount reversion | CEF prices + NAV history | Long-only basket | **N/A** — long only | **No free NAV/discount history** |
| **B3** | Post-earnings drift | Prices + earnings surprises | Long-only basket | **N/A** — long only | **No free bulk surprise history** |

B2 and B3 are expected to die at their kill criterion, which is a *data* question answered before any
modelling (FR-005). Their `screen_symbols` are deliberately unset until the data gate passes.

---

## 2. `DataFeasibility` — the US2 cull record

| Field | Meaning |
|---|---|
| `candidate_id` | — |
| `status` | `testable` / `dead_on_data` / `dead_on_economics` |
| `source_checked` | Where it was looked for, specifically enough to re-check |
| `usable_history` | First and last usable date, and the bar count |
| `granularity_confirmed` | What the source *reported*, not what was requested — see R1 |
| `note` | What was missing, when dead |

`dead_on_data` and `dead_on_economics` are terminal: no model is built (FR-005, FR-006).

---

## 3. `GateVerdict` — the standalone verdict

The output of `forex/backtest/gate.py`, one per surviving candidate. Deliberately carries the
*ingredients* of the verdict, not only the conclusion, so FR-009 holds — a reader can see what was
measured.

| Field | Meaning |
|---|---|
| `candidate_id` | — |
| `verdict` | `pass` / `reject` / `inconclusive` |
| `per_window` | One `WindowResult` per era — **at least two** (FR-004) |
| `benchmark` | What it was measured against, named (FR-002) |
| `cost_basis` | The cost and financing model actually applied |
| `borrow_excluded` | **True when a short leg could not be costed** — then the result is an upper bound (R2) |
| `reasoning` | Why the verdict follows from the numbers |

### `WindowResult`

| Field | Meaning |
|---|---|
| `label`, `start`, `end`, `n_days` | Which era |
| `sharpe_net`, `return_net`, `max_dd` | Net of cost and financing — **gross figures are not stored at all** |
| `benchmark_sharpe` | The same metric for the benchmark over the same window |
| `beats_benchmark` | The comparison FR-002 requires |

**Validation rules, enforced by the evaluator rather than remembered:**

1. `len(per_window) >= 2`, else `inconclusive` — never `pass` (FR-004, SC-003).
2. `verdict == "pass"` requires `beats_benchmark` **in every window**. One good era is a reject.
3. No field holds a gross-of-cost figure. There is nowhere to put one (SC-004).
4. `borrow_excluded == True` forbids `pass` — the strongest such a candidate can reach is
   `inconclusive`, because a result that assumes free shorting is not a result (R2).

Rule 4 is the design consequence of R2 and the reason it is a rule rather than a note: it makes the
honest limit structural.

---

## 4. Cache layout

Parquet per series, mirroring `fred.py` so there is one cache convention:

```text
data_cache/
├── <FRED_SERIES>.parquet     # existing: DGS2, DGS10, T10YIE, …
└── yahoo/
    └── <SYMBOL>.parquet      # new: adjusted daily closes, one file per symbol
```

A cached file is sufficient to reproduce a verdict without refetching (FR-013) — which also means a
verdict can be re-derived after the free source changes shape or disappears.
