# Quickstart: Running a Candidate Gate

Prerequisites: repo root, `.venv` present, `FRED_API_KEY` in `~/.config/forex/env`. **No Gateway, no
broker** — if any step here needs one, that is a bug (FR-012).

---

## 1. Offline tests (no network, ~2s)

```bash
.venv/bin/python -m pytest tests/test_yahoo.py tests/test_gate.py tests/test_curve_spread.py -q
```

**Expect** green, with no network access. The two assertions worth looking for:

- a response reporting a non-daily granularity **raises** rather than returning data (research R1 —
  the trap that returns 292 monthly bars while claiming `interval=1d`);
- a return series that beats its benchmark in one era and loses in the other yields **`reject`**, never
  `pass`.

---

## 2. The data cull (US2, minutes)

```bash
.venv/bin/python scripts/gate_data_feasibility.py
```

**Expect** a table over all six candidates. The expected shape of the answer, per the spec's own
prediction (SC-007):

| Candidate | Expected |
|---|---|
| A3, B5, B6 | `testable` — macro series plus ~24y of adjusted ETF closes |
| B4 | `testable` on data, then likely `dead_on_economics` once the basis is compared to commission |
| B2, B3 | likely `dead_on_data` — free discount/NAV and bulk earnings-surprise history |

**A candidate that comes back `testable` when it was expected dead is a finding, not a problem** —
write it down and gate it properly.

---

## 3. One candidate's verdict (US1, an afternoon)

```bash
.venv/bin/python scripts/gate_candidate.py --candidate A3
```

**Expect** a per-window table and a verdict. What to check before believing it:

- **Two windows**, both reported. One window is `inconclusive` by construction.
- Figures **net** of cost and financing — there is no gross number anywhere to compare against, by
  design.
- `borrow_excluded` stated. For A3's ETF-proxy screen it will be `True`, which caps the verdict at
  `inconclusive` (research R2). That is correct and not a failure: it means the screen informs the
  futures question rather than answering it.
- A benchmark named and beaten, or not.

---

## 4. Sanity checks worth doing once

**Confirm the granularity guard actually fires**, since it is the guard against this feature's worst
failure mode:

```bash
.venv/bin/python -c "
from forex.data.yahoo import load_prices
s = load_prices('IEF', force=True)
print(f'{len(s)} bars, {s.index.min().date()} -> {s.index.max().date()}')
print('median gap (days):', s.index.to_series().diff().dt.days.median())
"
```

**Expect** ~6,000 bars from 2002 and a **median gap of 1 day**. A median gap near 30 means monthly bars
got through and the assertion is not doing its job — stop and fix the loader before any verdict.

**Confirm the cache makes a verdict reproducible** (FR-013):

```bash
.venv/bin/python scripts/gate_candidate.py --candidate A3    # second run, no --refresh
```

**Expect** identical numbers, and no network access.

---

## 5. Recording the verdict

Every candidate ends in `docs/standalone-longshort-findings.md` with its numbers, its benchmark, its
cost basis, and the reasoning — and its backlog row in `specs/000-baseline/baseline.md` updated to the
resolved state.

**A candidate is not finished when its number is computed; it is finished when its verdict is written
down.** The research record is this feature's only output, and the rejections are the most valuable part
of it — they are what stops the same six ideas being reconsidered next year.
