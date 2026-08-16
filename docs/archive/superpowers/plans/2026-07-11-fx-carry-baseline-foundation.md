# FX Carry Baseline + Research Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the offline research foundation (FRED data layer with point-in-time correctness, a vectorized portfolio backtester, and a walk-forward + distant-window validation harness) and produce a validated **bare G10 carry-basket backtest** — the reusable base for the ML crash overlay and all later strategy phases.

**Architecture:** A small Python package (`forex/`) with isolated units: `data/` (FRED loaders → cached parquet feature store with release-date/as-of joins), `features/` (carry signal + basket construction), `backtest/` (portfolio simulator + metrics + validation splits), and `research/` (one script per experiment). Everything in this plan is free and offline-testable — spot FX and short rates both come from FRED (H.10 + OECD series); no broker connection is needed until the later paper-gate plan.

**Tech Stack:** Python 3.11+, pandas, numpy, pyarrow (parquet), fredapi (FRED client), pytest. ML stack (MLX/sklearn) and `ib_async` are NOT used in this plan — they arrive in follow-on plans.

## Global Constraints

- Project root: `~/Documents/forex` (its own git repo, separate from the crypto freqtrade repo).
- Package layout: all importable code under `forex/`; tests under `tests/`.
- **Point-in-time correctness is mandatory:** every data series is joined to the trading calendar with a publication lag; a value dated for reference period T is only visible on/after its release date. No series may be used at a timestamp earlier than its release.
- **Judge strategies on out-of-sample P&L / risk-adjusted return, never on model fit.** (No models in this plan, but the validation harness is built to this standard.)
- **Distant-window validation:** any edge claim must survive a temporally-distant era, not just adjacent walk-forward windows.
- FRED access requires a free API key in the `FRED_API_KEY` environment variable. Tests must NOT hit the network — they use CSV fixtures under `tests/fixtures/`.
- Commit after every task. Conventional-commit messages.

---

## File Structure

- `pyproject.toml` — package + dependency + pytest config.
- `forex/__init__.py`
- `forex/config.py` — the G10 universe: per-currency FRED series IDs, inversion flags, publication lags.
- `forex/data/fred.py` — thin FRED fetch wrapper (series → tidy DataFrame), cache to parquet.
- `forex/data/store.py` — parquet cache + `asof_join` (point-in-time merge with publication lag).
- `forex/data/prices.py` — build the G10 USD-based spot panel (normalized quote convention) + daily FX returns.
- `forex/features/carry.py` — short-rate differential (carry signal) + beta-neutral basket weights.
- `forex/backtest/portfolio.py` — vectorized simulator (spot P&L + carry accrual + costs) + metrics.
- `forex/backtest/validation.py` — walk-forward and distant-window split generators.
- `forex/research/carry_baseline.py` — end-to-end bare-carry backtest script.
- `tests/…` — one test module per unit; fixtures under `tests/fixtures/`.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `forex/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installed `forex` package; `pytest` runs green.

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import forex
    assert forex.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex'`.

- [ ] **Step 3: Write minimal implementation**

`pyproject.toml`:
```toml
[project]
name = "forex"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pandas>=2.0", "numpy>=1.26", "pyarrow>=14", "fredapi>=0.5"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["forex*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`forex/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Install and run the test**

Run: `pip install -e ".[dev]" && pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml forex/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold forex package with pytest"
```

---

### Task 2: G10 universe config

**Files:**
- Create: `forex/config.py`, `forex/data/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CURRENCIES: dict[str, Currency]` where `Currency` is a dataclass with fields
  `code: str`, `spot_fred: str | None`, `spot_invert: bool`, `rate_fred: str`, `pub_lag_days: int`.
  USD is the base (no spot series). `spot_invert=True` means the FRED series is quoted
  FX-per-USD and must be inverted to USD-per-FX.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from forex.config import CURRENCIES

def test_universe_is_g10():
    assert set(CURRENCIES) == {"USD","EUR","JPY","GBP","CHF","AUD","NZD","CAD","NOK","SEK"}

def test_usd_is_base():
    assert CURRENCIES["USD"].spot_fred is None

def test_jpy_is_inverted():
    # DEXJPUS is JPY-per-USD, so it must be flagged for inversion to USD-per-JPY
    assert CURRENCIES["JPY"].spot_invert is True
    assert CURRENCIES["EUR"].spot_invert is False  # DEXUSEU is already USD-per-EUR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.config'`.

- [ ] **Step 3: Write minimal implementation**

`forex/data/__init__.py`: (empty)

`forex/config.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Currency:
    code: str
    spot_fred: str | None   # FRED series for USD spot; None for the USD base
    spot_invert: bool       # True if series is FX-per-USD (invert to USD-per-FX)
    rate_fred: str          # FRED short-rate series (3-month interbank, OECD)
    pub_lag_days: int       # release lag in days (0 for daily market data)

# Spot: FRED H.10. Rates: OECD 3-month interbank (IR3TIB01<CC>M156N), monthly, ffill.
# spot_invert=True where the H.10 series is quoted FX-per-USD.
CURRENCIES: dict[str, Currency] = {
    "USD": Currency("USD", None,       False, "IR3TIB01USM156N", 0),
    "EUR": Currency("EUR", "DEXUSEU",  False, "IR3TIB01EZM156N", 0),
    "JPY": Currency("JPY", "DEXJPUS",  True,  "IR3TIB01JPM156N", 0),
    "GBP": Currency("GBP", "DEXUSUK",  False, "IR3TIB01GBM156N", 0),
    "CHF": Currency("CHF", "DEXSZUS",  True,  "IR3TIB01CHM156N", 0),
    "AUD": Currency("AUD", "DEXUSAL",  False, "IR3TIB01AUM156N", 0),
    "NZD": Currency("NZD", "DEXUSNZ",  False, "IR3TIB01NZM156N", 0),
    "CAD": Currency("CAD", "DEXCAUS",  True,  "IR3TIB01CAM156N", 0),
    "NOK": Currency("NOK", "DEXNOUS",  True,  "IR3TIB01NOM156N", 0),
    "SEK": Currency("SEK", "DEXSDUS",  True,  "IR3TIB01SEM156N", 0),
}
```

Note to implementer: FRED series IDs occasionally get revised/discontinued. Before the first
live fetch (Task 3, Step 6), spot-check each ID at https://fred.stlouisfed.org/series/<ID>; if
one is dead, substitute the nearest 3-month rate for that country and update this dict. Tests use
fixtures and do not depend on the IDs being live.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forex/config.py forex/data/__init__.py tests/test_config.py
git commit -m "feat: G10 universe config (FRED series, inversion, pub lag)"
```

---

### Task 3: FRED fetch wrapper with parquet cache

**Files:**
- Create: `forex/data/fred.py`, `tests/test_fred.py`, `tests/fixtures/DEXUSEU.csv`

**Interfaces:**
- Consumes: nothing (reads `FRED_API_KEY` from env at call time).
- Produces:
  - `load_series(series_id: str, *, cache_dir: Path, client=None) -> pd.Series` — a
    float Series indexed by a tz-naive `DatetimeIndex` named `date`, sorted ascending, NaNs
    dropped. Reads `<cache_dir>/<series_id>.parquet` if present, else fetches via `client`
    (default: a real `fredapi.Fred`) and writes the cache.
  - `_read_cache` / `_write_cache` helpers (parquet).

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/DEXUSEU.csv`:
```
date,value
2020-01-02,1.1194
2020-01-03,1.1160
2020-01-06,1.1195
```

`tests/test_fred.py`:
```python
from pathlib import Path
import pandas as pd
from forex.data.fred import load_series

class FakeFred:
    """Stand-in for fredapi.Fred that reads a CSV fixture."""
    def __init__(self, fixture): self.fixture = fixture
    def get_series(self, series_id):
        df = pd.read_csv(self.fixture, parse_dates=["date"]).set_index("date")["value"]
        return df

def test_load_series_from_client_and_caches(tmp_path):
    client = FakeFred("tests/fixtures/DEXUSEU.csv")
    s = load_series("DEXUSEU", cache_dir=tmp_path, client=client)
    assert s.index.name == "date"
    assert s.iloc[0] == 1.1194
    assert (tmp_path / "DEXUSEU.parquet").exists()   # cache written

def test_load_series_reads_cache_without_client(tmp_path):
    client = FakeFred("tests/fixtures/DEXUSEU.csv")
    load_series("DEXUSEU", cache_dir=tmp_path, client=client)   # populate cache
    s = load_series("DEXUSEU", cache_dir=tmp_path, client=None)  # no client -> must hit cache
    assert len(s) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fred.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.data.fred'`.

- [ ] **Step 3: Write minimal implementation**

`forex/data/fred.py`:
```python
import os
from pathlib import Path
import pandas as pd

def _cache_path(cache_dir: Path, series_id: str) -> Path:
    return Path(cache_dir) / f"{series_id}.parquet"

def _read_cache(cache_dir: Path, series_id: str) -> pd.Series | None:
    p = _cache_path(cache_dir, series_id)
    if not p.exists():
        return None
    return pd.read_parquet(p)["value"]

def _write_cache(cache_dir: Path, series_id: str, s: pd.Series) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    s.rename("value").to_frame().to_parquet(_cache_path(cache_dir, series_id))

def _default_client():
    from fredapi import Fred
    return Fred(api_key=os.environ["FRED_API_KEY"])

def load_series(series_id: str, *, cache_dir: Path, client=None) -> pd.Series:
    cached = _read_cache(cache_dir, series_id)
    if cached is not None:
        return cached
    if client is None:
        client = _default_client()
    raw = client.get_series(series_id)
    s = pd.Series(raw, dtype="float64").dropna().sort_index()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None)
    s.index.name = "date"
    s.name = "value"
    _write_cache(cache_dir, series_id, s)
    return s
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fred.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add forex/data/fred.py tests/test_fred.py tests/fixtures/DEXUSEU.csv
git commit -m "feat: FRED series loader with parquet cache"
```

- [ ] **Step 6: Live smoke check (manual, not a test)**

With `FRED_API_KEY` set, run in a REPL: `from forex.data.fred import load_series; load_series("DEXUSEU", cache_dir="data_cache")` and confirm a non-empty series. This is also where you validate every series ID in `CURRENCIES` (Task 2 note). Do not commit `data_cache/`.

---

### Task 4: Point-in-time as-of join

**Files:**
- Create: `forex/data/store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `asof_join(calendar: pd.DatetimeIndex, series: pd.Series, pub_lag_days: int) -> pd.Series`
    — returns, for each date in `calendar`, the most recent value of `series` whose
    **release date** (series index + `pub_lag_days`) is `<= date`. Backward as-of; never uses a
    value before it was released. Result is indexed by `calendar`, name preserved.

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:
```python
import pandas as pd
from forex.data.store import asof_join

def test_asof_respects_publication_lag():
    # value for 2020-01-31 is only *released* 5 days later (2020-02-05)
    s = pd.Series([1.0, 2.0],
                  index=pd.to_datetime(["2020-01-31", "2020-02-29"]), name="rate")
    cal = pd.to_datetime(["2020-02-03", "2020-02-06", "2020-03-10"])
    out = asof_join(cal, s, pub_lag_days=5)
    # 2020-02-03: Jan value not released until 02-05 -> NaN (nothing available yet)
    # 2020-02-06: Jan value now visible -> 1.0
    # 2020-03-10: Feb value (released 03-05) visible -> 2.0
    assert pd.isna(out.loc["2020-02-03"])
    assert out.loc["2020-02-06"] == 1.0
    assert out.loc["2020-03-10"] == 2.0

def test_zero_lag_is_same_day():
    s = pd.Series([5.0], index=pd.to_datetime(["2020-01-02"]), name="fx")
    cal = pd.to_datetime(["2020-01-02", "2020-01-03"])
    out = asof_join(cal, s, pub_lag_days=0)
    assert out.loc["2020-01-02"] == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.data.store'`.

- [ ] **Step 3: Write minimal implementation**

`forex/data/store.py`:
```python
import pandas as pd

def asof_join(calendar: pd.DatetimeIndex, series: pd.Series,
              pub_lag_days: int) -> pd.Series:
    """As-of (backward) join that respects a publication lag: a value dated T is
    only visible on/after T + pub_lag_days."""
    released = series.copy()
    released.index = series.index + pd.Timedelta(days=pub_lag_days)
    released = released.sort_index()
    left = pd.DataFrame(index=pd.DatetimeIndex(calendar).sort_values())
    right = released.rename("value").to_frame()
    merged = pd.merge_asof(left, right, left_index=True, right_index=True,
                           direction="backward")
    out = merged["value"]
    out.index.name = "date"
    out.name = series.name
    return out.reindex(calendar)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forex/data/store.py tests/test_store.py
git commit -m "feat: point-in-time as-of join with publication lag"
```

---

### Task 5: G10 spot panel + returns

**Files:**
- Create: `forex/data/prices.py`, `tests/test_prices.py`

**Interfaces:**
- Consumes: `forex.config.CURRENCIES`, `forex.data.fred.load_series`.
- Produces:
  - `build_spot_panel(cache_dir, loader=load_series) -> pd.DataFrame` — columns = the 9
    non-USD currency codes, values = **USD per 1 unit of foreign currency** (inverting the
    `spot_invert` series), indexed by date, forward-filled across the common calendar. A rise in
    a column means the foreign currency appreciated vs USD.
  - `spot_returns(panel: pd.DataFrame) -> pd.DataFrame` — daily simple returns of the panel
    (a long position in the foreign currency earns this).

- [ ] **Step 1: Write the failing test**

`tests/test_prices.py`:
```python
import pandas as pd
from forex.data.prices import build_spot_panel, spot_returns

def make_loader(data):
    def _loader(series_id, *, cache_dir, client=None):
        return data[series_id]
    return _loader

def test_inversion_and_returns():
    idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
    data = {
        "DEXUSEU": pd.Series([1.10, 1.21], index=idx, name="value"),  # already USD/EUR
        "DEXJPUS": pd.Series([100.0, 125.0], index=idx, name="value"),# JPY/USD -> invert
    }
    # restrict the universe to EUR+JPY for the test by monkeypatching is unnecessary:
    panel = build_spot_panel(cache_dir="unused", loader=make_loader(data),
                             codes=["EUR", "JPY"])
    # EUR: unchanged; JPY inverted -> USD/JPY = 1/100 then 1/125
    assert round(panel.loc["2020-01-02", "EUR"], 4) == 1.10
    assert round(panel.loc["2020-01-02", "JPY"], 6) == round(1/100, 6)
    rets = spot_returns(panel)
    assert round(rets.loc["2020-01-03", "EUR"], 4) == 0.10      # +10%
    assert round(rets.loc["2020-01-03", "JPY"], 4) == -0.20     # 1/125 vs 1/100 = -20%
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_prices.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.data.prices'`.

- [ ] **Step 3: Write minimal implementation**

`forex/data/prices.py`:
```python
import pandas as pd
from forex.config import CURRENCIES
from forex.data.fred import load_series

def build_spot_panel(cache_dir, loader=load_series, codes=None) -> pd.DataFrame:
    """USD per 1 unit of each foreign currency (spot_invert series inverted)."""
    if codes is None:
        codes = [c for c in CURRENCIES if c != "USD"]
    cols = {}
    for code in codes:
        cur = CURRENCIES[code]
        s = loader(cur.spot_fred, cache_dir=cache_dir).astype("float64")
        cols[code] = (1.0 / s) if cur.spot_invert else s
    panel = pd.DataFrame(cols).sort_index()
    panel = panel.ffill().dropna(how="all")
    panel.index.name = "date"
    return panel

def spot_returns(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.pct_change().dropna(how="all")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_prices.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forex/data/prices.py tests/test_prices.py
git commit -m "feat: G10 USD spot panel (normalized convention) + returns"
```

---

### Task 6: Carry signal + beta-neutral basket weights

**Files:**
- Create: `forex/features/__init__.py`, `forex/features/carry.py`, `tests/test_carry.py`

**Interfaces:**
- Consumes: `forex.config.CURRENCIES`, `forex.data.store.asof_join`.
- Produces:
  - `carry_signal(calendar, rates: dict[str, pd.Series]) -> pd.DataFrame` — for each date and
    each non-USD currency, the **short-rate differential vs USD** (foreign short rate − USD short
    rate, in annualized decimal), point-in-time via `asof_join` with each currency's `pub_lag_days`.
  - `basket_weights(signal: pd.DataFrame, n_long: int = 3, n_short: int = 3) -> pd.DataFrame` —
    per date, +1/n_long to the top-`n_long` carry currencies, −1/n_short to the bottom-`n_short`,
    0 otherwise (dollar-neutral: longs sum to +1, shorts to −1). Currencies with NaN signal on a
    date are excluded from ranking.

- [ ] **Step 1: Write the failing test**

`tests/test_carry.py`:
```python
import numpy as np, pandas as pd
from forex.features.carry import carry_signal, basket_weights

def test_carry_is_differential_vs_usd():
    cal = pd.to_datetime(["2020-06-01"])
    rates = {
        "USD": pd.Series([0.01], index=pd.to_datetime(["2020-06-01"]), name="USD"),
        "AUD": pd.Series([0.05], index=pd.to_datetime(["2020-06-01"]), name="AUD"),
    }
    sig = carry_signal(cal, rates)
    assert round(sig.loc["2020-06-01", "AUD"], 4) == 0.04  # 5% - 1%

def test_basket_weights_are_dollar_neutral():
    sig = pd.DataFrame(
        {"A": [0.05], "B": [0.04], "C": [0.03], "D": [-0.01], "E": [-0.02]},
        index=pd.to_datetime(["2020-06-01"]),
    )
    w = basket_weights(sig, n_long=2, n_short=2)
    row = w.loc["2020-06-01"]
    assert row["A"] == 0.5 and row["B"] == 0.5      # top-2 long
    assert row["D"] == -0.5 and row["E"] == -0.5    # bottom-2 short
    assert row["C"] == 0.0                          # middle excluded
    assert abs(row.sum()) < 1e-9                    # dollar-neutral
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_carry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.features.carry'`.

- [ ] **Step 3: Write minimal implementation**

`forex/features/__init__.py`: (empty)

`forex/features/carry.py`:
```python
import numpy as np
import pandas as pd
from forex.config import CURRENCIES

def carry_signal(calendar, rates: dict[str, pd.Series]) -> pd.DataFrame:
    from forex.data.store import asof_join
    cal = pd.DatetimeIndex(calendar)
    usd = asof_join(cal, rates["USD"], CURRENCIES["USD"].pub_lag_days)
    cols = {}
    for code, s in rates.items():
        if code == "USD":
            continue
        r = asof_join(cal, s, CURRENCIES[code].pub_lag_days)
        cols[code] = r - usd
    out = pd.DataFrame(cols, index=cal)
    out.index.name = "date"
    return out

def basket_weights(signal: pd.DataFrame, n_long: int = 3,
                   n_short: int = 3) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    for dt, row in signal.iterrows():
        r = row.dropna()
        if len(r) < n_long + n_short:
            continue
        ranked = r.sort_values(ascending=False)
        longs = ranked.index[:n_long]
        shorts = ranked.index[-n_short:]
        w.loc[dt, longs] = 1.0 / n_long
        w.loc[dt, shorts] = -1.0 / n_short
    return w
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_carry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forex/features/__init__.py forex/features/carry.py tests/test_carry.py
git commit -m "feat: carry signal (rate differential) + dollar-neutral basket weights"
```

---

### Task 7: Portfolio simulator + metrics

**Files:**
- Create: `forex/backtest/__init__.py`, `forex/backtest/portfolio.py`, `tests/test_portfolio.py`

**Interfaces:**
- Consumes: nothing (pure numpy/pandas).
- Produces:
  - `simulate(weights, spot_rets, carry, cost_bps=1.0) -> pd.Series` — daily portfolio
    returns. Position weights are applied to the NEXT day's returns (`weights.shift(1)`) to avoid
    lookahead. Total return per position = spot return + daily carry accrual (`carry/252`).
    Transaction cost = `cost_bps/1e4 * turnover`, where turnover = sum of abs weight changes.
    Returns a Series named `ret` indexed by date.
  - `metrics(returns: pd.Series) -> dict` — keys `total_return`, `ann_return`, `ann_vol`,
    `sharpe`, `max_drawdown`, `calmar` (ann_return / abs(max_drawdown)).

- [ ] **Step 1: Write the failing test**

`tests/test_portfolio.py`:
```python
import numpy as np, pandas as pd
from forex.backtest.portfolio import simulate, metrics

def test_simulate_applies_lagged_weights_and_carry():
    idx = pd.to_datetime(["2020-01-01","2020-01-02","2020-01-03"])
    weights = pd.DataFrame({"A":[1.0,1.0,1.0]}, index=idx)
    spot = pd.DataFrame({"A":[0.0, 0.10, 0.0]}, index=idx)  # +10% on day 2
    carry = pd.DataFrame({"A":[0.0, 0.0, 0.0]}, index=idx)
    ret = simulate(weights, spot, carry, cost_bps=0.0)
    # day 1: no prior weight -> 0 ; day 2: weight from day1 (1.0) * 10% = 0.10
    assert round(ret.loc["2020-01-02"], 4) == 0.10

def test_carry_accrues_daily():
    idx = pd.to_datetime(["2020-01-01","2020-01-02"])
    weights = pd.DataFrame({"A":[1.0,1.0]}, index=idx)
    spot = pd.DataFrame({"A":[0.0,0.0]}, index=idx)
    carry = pd.DataFrame({"A":[0.0, 2.52]}, index=idx)   # 252% annual -> 1%/day
    ret = simulate(weights, spot, carry, cost_bps=0.0)
    assert round(ret.loc["2020-01-02"], 4) == 0.01

def test_metrics_shape():
    r = pd.Series([0.01,-0.02,0.03,0.00],
                  index=pd.to_datetime(["2020-01-01","2020-01-02","2020-01-03","2020-01-04"]))
    m = metrics(r)
    assert {"total_return","ann_return","ann_vol","sharpe","max_drawdown","calmar"} <= set(m)
    assert m["max_drawdown"] <= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.backtest.portfolio'`.

- [ ] **Step 3: Write minimal implementation**

`forex/backtest/__init__.py`: (empty)

`forex/backtest/portfolio.py`:
```python
import numpy as np
import pandas as pd

def simulate(weights: pd.DataFrame, spot_rets: pd.DataFrame,
             carry: pd.DataFrame, cost_bps: float = 1.0) -> pd.Series:
    cols = weights.columns
    idx = weights.index
    spot = spot_rets.reindex(index=idx, columns=cols).fillna(0.0)
    car = carry.reindex(index=idx, columns=cols).fillna(0.0) / 252.0
    held = weights.shift(1).fillna(0.0)                      # act on next day -> no lookahead
    gross = (held * (spot + car)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    cost = (cost_bps / 1e4) * turnover
    ret = (gross - cost).rename("ret")
    ret.index.name = "date"
    return ret

def metrics(returns: pd.Series) -> dict:
    r = returns.dropna()
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1.0)
    ann_return = (1 + r).prod() ** (252 / len(r)) - 1 if len(r) else 0.0
    ann_vol = r.std() * np.sqrt(252)
    mdd = dd.min() if len(dd) else 0.0
    return {
        "total_return": eq.iloc[-1] - 1 if len(eq) else 0.0,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": (ann_return / ann_vol) if ann_vol else 0.0,
        "max_drawdown": mdd,
        "calmar": (ann_return / abs(mdd)) if mdd < 0 else 0.0,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_portfolio.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add forex/backtest/__init__.py forex/backtest/portfolio.py tests/test_portfolio.py
git commit -m "feat: vectorized portfolio simulator (carry accrual, costs) + metrics"
```

---

### Task 8: Validation splits (walk-forward + distant-window)

**Files:**
- Create: `forex/backtest/validation.py`, `tests/test_validation.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `walk_forward(index, train_days, test_days) -> list[tuple[slice, slice]]` — consecutive
    (train, test) date-slice pairs rolling forward over `index`.
  - `distant_window(index, holdout_years=3) -> tuple[slice, slice]` — returns `(recent, distant)`
    where `distant` is the EARLIEST `holdout_years` of data and `recent` is the rest. Used to
    confirm an edge measured on recent data survives on a temporally-distant era.

- [ ] **Step 1: Write the failing test**

`tests/test_validation.py`:
```python
import pandas as pd
from forex.backtest.validation import walk_forward, distant_window

def test_walk_forward_pairs_are_disjoint_and_ordered():
    idx = pd.date_range("2015-01-01", periods=1000, freq="B")
    folds = walk_forward(idx, train_days=250, test_days=125)
    assert len(folds) >= 2
    tr, te = folds[0]
    assert idx[tr].max() < idx[te].min()          # train strictly before test
    assert idx[te].min() < idx[walk_forward(idx,250,125)[1][1]].min()  # test rolls forward

def test_distant_window_takes_earliest_years():
    idx = pd.date_range("2010-01-01", "2020-12-31", freq="B")
    recent, distant = distant_window(idx, holdout_years=3)
    assert idx[distant].min() == idx.min()
    assert idx[distant].max() < idx[recent].min()  # distant is strictly earlier
    assert (idx[distant].max() - idx[distant].min()).days <= 3 * 366
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.backtest.validation'`.

- [ ] **Step 3: Write minimal implementation**

`forex/backtest/validation.py`:
```python
import pandas as pd

def walk_forward(index: pd.DatetimeIndex, train_days: int,
                 test_days: int) -> list[tuple[slice, slice]]:
    idx = pd.DatetimeIndex(index).sort_values()
    folds, start = [], 0
    while start + train_days + test_days <= len(idx):
        tr = slice(start, start + train_days)
        te = slice(start + train_days, start + train_days + test_days)
        folds.append((tr, te))
        start += test_days
    return folds

def distant_window(index: pd.DatetimeIndex,
                   holdout_years: int = 3) -> tuple[slice, slice]:
    idx = pd.DatetimeIndex(index).sort_values()
    cutoff = idx.min() + pd.DateOffset(years=holdout_years)
    n_distant = int((idx < cutoff).sum())
    distant = slice(0, n_distant)
    recent = slice(n_distant, len(idx))
    return recent, distant
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_validation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forex/backtest/validation.py tests/test_validation.py
git commit -m "feat: walk-forward + distant-window validation splits"
```

---

### Task 9: End-to-end bare-carry baseline script

**Files:**
- Create: `forex/research/__init__.py`, `forex/research/carry_baseline.py`, `tests/test_carry_baseline.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `run_baseline(cache_dir, loader=load_series) -> tuple[pd.Series, dict]` — builds the spot
    panel + rates, computes carry signal → weights, simulates, and returns `(daily_returns,
    metrics_dict)`. This is the reusable base the ML overlay (next plan) wraps.
  - A `__main__` block that runs it against the real FRED cache and prints the metrics + the
    distant-window check.

- [ ] **Step 1: Write the failing test**

`tests/test_carry_baseline.py`:
```python
import numpy as np, pandas as pd
from forex.research.carry_baseline import run_baseline

def _synthetic_loader():
    """A tiny deterministic FRED stand-in: 2 currencies, AUD high-yield & rising."""
    dates = pd.date_range("2018-01-01", periods=600, freq="B")
    series = {
        "DEXUSAL": pd.Series(1.0 + np.linspace(0, 0.2, 600), index=dates, name="value"), # AUD up
        "DEXUSEU": pd.Series(1.1 + np.zeros(600), index=dates, name="value"),            # EUR flat
        "IR3TIB01USM156N": pd.Series(0.01, index=dates, name="value"),
        "IR3TIB01AUM156N": pd.Series(0.06, index=dates, name="value"),  # high carry
        "IR3TIB01EZM156N": pd.Series(0.00, index=dates, name="value"),  # low carry
    }
    def loader(series_id, *, cache_dir, client=None):
        return series[series_id]
    return loader

def test_baseline_runs_and_high_carry_rising_currency_makes_money():
    # Restrict universe to AUD (long) vs EUR (short) via n_long=n_short=1.
    rets, m = run_baseline(cache_dir="unused", loader=_synthetic_loader(),
                           codes=["AUD", "EUR"], n_long=1, n_short=1)
    assert isinstance(rets, pd.Series) and len(rets) > 100
    assert set(["sharpe","max_drawdown","calmar"]).issubset(m)
    assert m["total_return"] > 0    # long high-carry rising AUD, short flat EUR -> positive
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_carry_baseline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.research.carry_baseline'`.

- [ ] **Step 3: Write minimal implementation**

`forex/research/__init__.py`: (empty)

`forex/research/carry_baseline.py`:
```python
import pandas as pd
from forex.config import CURRENCIES
from forex.data.fred import load_series
from forex.data.prices import build_spot_panel, spot_returns
from forex.features.carry import carry_signal, basket_weights
from forex.backtest.portfolio import simulate, metrics

def run_baseline(cache_dir, loader=load_series, codes=None,
                 n_long=3, n_short=3, cost_bps=1.0):
    if codes is None:
        codes = [c for c in CURRENCIES if c != "USD"]
    panel = build_spot_panel(cache_dir, loader=loader, codes=codes)
    rets = spot_returns(panel)
    cal = panel.index
    rates = {"USD": loader(CURRENCIES["USD"].rate_fred, cache_dir=cache_dir)}
    for c in codes:
        rates[c] = loader(CURRENCIES[c].rate_fred, cache_dir=cache_dir)
    signal = carry_signal(cal, rates)
    weights = basket_weights(signal[codes], n_long=n_long, n_short=n_short)
    daily = simulate(weights, rets, carry=signal[codes].fillna(0.0), cost_bps=cost_bps)
    return daily, metrics(daily)

if __name__ == "__main__":
    daily, m = run_baseline(cache_dir="data_cache")
    print("Bare G10 carry baseline:")
    for k, v in m.items():
        print(f"  {k:14} {v: .4f}")
    from forex.backtest.validation import distant_window
    recent, distant = distant_window(daily.index, holdout_years=3)
    print("  distant-era total return:", round((1+daily.iloc[distant]).prod()-1, 4))
    print("  recent-era  total return:", round((1+daily.iloc[recent]).prod()-1, 4))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_carry_baseline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forex/research/__init__.py forex/research/carry_baseline.py tests/test_carry_baseline.py
git commit -m "feat: end-to-end bare G10 carry baseline backtest"
```

- [ ] **Step 6: Full suite + live sanity run (manual)**

Run `pytest -v` (all green). Then, with `FRED_API_KEY` set, run
`python -m forex.research.carry_baseline` and eyeball the real output: a bare G10 carry
basket should show a **positive long-run return with negative skew and a visible drawdown in
2008 and around the 2015 CHF de-peg** (the crash character the overlay will target). Record these
numbers — they are the Phase-0 reproduction check and the baseline the ML overlay (next plan)
must beat on risk-adjusted terms. Add a `.gitignore` for `data_cache/` and commit it.

---

## Self-Review

**1. Spec coverage.** Spec §2 environment: FRED data layer (Tasks 3–5), free/offline (all tasks),
new repo (Task 1) ✓. §3 architecture: `data/` (3–5), `features/` (6), `backtest/` (7–8),
`research/` (9); point-in-time (Task 4) ✓. §4 flagship "carry baseline": the bare basket (Tasks
6, 9) ✓ — the ML overlay is explicitly deferred to the next plan (documented in the scope note).
§5 Phase 0 verify ("reproduce a known carry return") = Task 9 Step 6 ✓; validation harness =
Task 8 ✓. §6 point-in-time / distant-window = Tasks 4, 8 ✓; the continuous carry-stress target and
crash model are overlay concerns → next plan (correctly out of scope). Not covered here (by design,
deferred to follow-on plans): IBKR/`ib_async` execution client, the ML crash overlay, cross-sectional
factors, vol sizing, NLP, EM. Each is its own plan.

**2. Placeholder scan.** No TBD/TODO; every code step has complete code; every test step has a real
test. The two "manual" steps (Task 3 Step 6, Task 9 Step 6) are live-data sanity checks that cannot
be unit-tested offline and are clearly labeled as such, not placeholders.

**3. Type consistency.** `load_series(series_id, *, cache_dir, client)` signature is consistent
across Tasks 3, 5, 6, 9. `asof_join(calendar, series, pub_lag_days)` consistent (Tasks 4, 6).
`build_spot_panel(cache_dir, loader, codes)` / `spot_returns` consistent (Tasks 5, 9).
`carry_signal(calendar, rates)` / `basket_weights(signal, n_long, n_short)` consistent (Tasks 6, 9).
`simulate(weights, spot_rets, carry, cost_bps)` / `metrics(returns)` consistent (Tasks 7, 9).
`walk_forward` / `distant_window` consistent (Tasks 8, 9).

---

## What the next plans cover (not this one)
- **Plan 2 — ML crash overlay:** the continuous carry-stress target, the free feature set
  (COT positioning, cross-asset risk, vol), the model + walk-forward CV, and the overlaid backtest
  vs this baseline (the research gate).
- **Plan 3 — IBKR paper execution:** the `ib_async` client, backtest≡live parity, the paper gate.
- **Later:** cross-sectional factors, vol sizing, NLP, EM extension.
