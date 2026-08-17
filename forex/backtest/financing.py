"""Broker financing cost: what it costs to *hold* a currency position, as opposed to trade it.

The simulator credits every position with the full interbank differential and charges only per-trade
cost. Real brokers pay `benchmark - credit_spread` on a long balance (floored at zero) and charge
`benchmark + debit_spread` on a borrowed one, so a dollar-neutral book pays the spread on both legs.
Measured on the deployed book that is -2.18% of gross per year — see
`docs/financing-spread-findings.md`.

For a held weight w in currency C, funded in USD:

    w > 0:  realised differential = (r_C - r_USD) - long_spread_C
    w < 0:  realised differential = (r_C - r_USD) + short_spread_C

Contribution is `w x differential` either way, so the penalty collapses to `|w| x spread` — always a
cost, on both sides, proportional to size.

    long_spread_C  = min(r_C,   credit_spread_C)   + debit_spread_USD
    short_spread_C = debit_spread_C                + min(r_USD, credit_spread_USD)

The `min(rate, spread)` is the broker's zero floor on credit, and it is exact rather than an
approximation: NZD's published 2.5% credit spread against a ~2.1% benchmark floors to earning
nothing, which is what the account actually accrues, and ILS (0% on all balances) is the same
expression with an unbounded credit spread.

KNOWN APPROXIMATIONS — these push in BOTH directions, so the result is not a bound either way:

- UNDERSTATES: the zero-interest tranche on the first slice of each balance (USD 10k, ZAR 150k,
  HUF 3.5M, ...) is not modelled — it needs account size, which this framework has no concept of.
  It bites hardest on small books.
- UNDERSTATES: tier-1 debit spreads are used; larger accounts get better tiers.
- OVERSTATES: rate levels come from FRED (monthly interbank), not IBKR's own benchmark, and FRED
  currently runs higher for several currencies (NZD 2.68% vs 2.10%, NOK 4.57% vs 4.06%). A higher
  rate raises the floored credit shortfall, so floored currencies are charged more than they would be.
- One published schedule is applied across all history. Spreads were certainly different pre-2010.
  This answers "what would this book cost to hold under today's terms", not "what it cost then".

Calibration: on the deployed book this model charges -2.75% of gross per year against -2.18%
independently measured from the live account (docs/financing-spread-findings.md). Same direction,
same order of magnitude, ~26% apart — close enough to trust the conclusion, not close enough to
quote to two decimals.
"""
import pandas as pd

from forex.config import CURRENCIES
from forex.data.store import asof_join

SCHEDULE_SOURCE = (
    "Interactive Brokers published rates, fetched 2026-08-16: "
    "interactivebrokers.com/en/accounts/fees/pricing-interest-rates.php (credit) and "
    "interactivebrokers.com/en/trading/margin-rates.php (debit, tier 1). IBKR Pro."
)

# How far below the benchmark the broker pays on a long balance. Credit is floored at zero, so a
# spread at or above the benchmark means the balance earns nothing (NZD today; ILS always).
CREDIT_SPREAD = {
    "USD": 0.005, "EUR": 0.005, "JPY": 0.0025, "GBP": 0.005, "CHF": 0.0025,
    "AUD": 0.005, "NZD": 0.025, "CAD": 0.005, "NOK": 0.02, "SEK": 0.005,
    "MXN": 0.04, "ZAR": 0.01, "PLN": 0.02, "HUF": 0.03, "CZK": 0.02,
    "ILS": float("inf"),   # published 0% on ALL balances — earns nothing at any rate
}

# How far above the benchmark the broker charges on a borrowed balance (tier 1).
DEBIT_SPREAD = {
    "USD": 0.015, "EUR": 0.015, "JPY": 0.015, "GBP": 0.015, "CHF": 0.015,
    "AUD": 0.015, "NZD": 0.015, "CAD": 0.015, "NOK": 0.015, "SEK": 0.015,
    "MXN": 0.03, "ZAR": 0.015, "PLN": 0.03, "HUF": 0.05, "CZK": 0.03,
    "ILS": 0.05,
}


def financing_spreads(calendar, rates, codes, base="USD", credit_spread=None, debit_spread=None):
    """Annualised long and short financing spreads per currency, as (long_df, short_df).

    `rates` maps currency -> rate level (the same series the carry signal uses) and must include
    `base`. Rate levels are joined with `asof_join` under each currency's publication lag, exactly as
    `carry_signal` does — so financing can see nothing the carry signal could not, and causality
    stays structural rather than conventional (Constitution II).

    Pass credit_spread/debit_spread to override the published schedule. Raises KeyError for a
    currency absent from the schedule: charging zero there would understate cost exactly where an
    unfamiliar currency is most likely to be expensive.
    """
    credit = CREDIT_SPREAD if credit_spread is None else credit_spread
    debit = DEBIT_SPREAD if debit_spread is None else debit_spread

    missing = [c for c in list(codes) + [base] if c not in credit or c not in debit]
    if missing:
        raise KeyError(f"no financing schedule for {sorted(missing)} — refusing to assume zero cost")

    cal = pd.DatetimeIndex(calendar)

    def pit(code):
        """Point-in-time rate level, under the same publication lag the carry signal uses."""
        lag = CURRENCIES[code].pub_lag_days if code in CURRENCIES else 0
        return asof_join(cal, rates[code], lag).fillna(0.0)

    # What the base leg costs: borrowing it to fund a long, or the credit forgone when short.
    base_debit = debit[base]
    base_credit_shortfall = pit(base).clip(upper=credit[base])

    lon, sho = {}, {}
    for code in codes:
        lon[code] = pit(code).clip(upper=credit[code]) + base_debit  # credit forgone + USD borrow
        sho[code] = base_credit_shortfall + debit[code]              # USD credit forgone + borrow
    return pd.DataFrame(lon, index=cal), pd.DataFrame(sho, index=cal)
