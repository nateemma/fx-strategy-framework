from typing import NamedTuple


class FxBook(NamedTuple):
    legs: int             # open non-base currency legs
    net_base: float       # net value of those legs incl. accrued interest, in base currency
    gross_base: float     # gross (sum of absolute) cash exposure, in base currency
    accrued_base: float   # the accrued-interest part of net_base — the carry leg of the P&L


def fx_book(account_values, base_currency: str = "USD", min_base: float = 1.0) -> FxBook:
    """Summarise the FX book from ib.accountValues().

    IBKR reports *settled* FX spot as a per-currency CashBalance and never in positions() —
    positions() carries an FX trade only between execution and settlement. So the open legs and
    the book's value have to be read from cash.

    net_base includes AccruedCash deliberately: for a carry book the interest differential *is*
    the return, and CashBalance alone omits it until it settles.

    net_base is the quantity to track over time. ETF trades move only base-currency cash, so they
    leave it untouched, and its change between two snapshots is the FX book's P&L — plus that day's
    net flow, on a day the book was rebalanced.

    account_values holds objects with .tag / .currency / .value (ib_async AccountValue). Legs worth
    less than min_base are treated as closed: settled interest leaves dust in currencies the book
    is flat in.
    """
    rates, cash, accrued = {}, {}, {}
    for v in account_values:
        if v.currency in ("", "BASE", base_currency):
            continue
        if v.tag == "ExchangeRate":
            rates[v.currency] = float(v.value)
        elif v.tag == "CashBalance":
            cash[v.currency] = float(v.value)
        elif v.tag == "AccruedCash":
            accrued[v.currency] = float(v.value)

    missing = sorted((set(cash) | set(accrued)) - set(rates))
    if missing:
        raise ValueError(f"no ExchangeRate for {missing} — cannot value the FX book")

    legs = gross = net = accr = 0
    for ccy in cash.keys() | accrued.keys():
        rate = rates[ccy]
        cash_base = cash.get(ccy, 0.0) * rate
        accr_base = accrued.get(ccy, 0.0) * rate
        if abs(cash_base) < min_base:
            continue
        legs += 1
        gross += abs(cash_base)
        net += cash_base + accr_base
        accr += accr_base
    return FxBook(legs, net, gross, accr)
