from types import SimpleNamespace

import pytest

from forex.run.fxbook import fx_book


def av(tag, currency, value):
    """Stand in for ib_async's AccountValue (value arrives as a string)."""
    return SimpleNamespace(tag=tag, currency=currency, value=str(value))


def test_reads_legs_from_cash_not_positions():
    """Settled FX spot is a CashBalance; two non-base balances are two open legs."""
    vals = [
        av("CashBalance", "EUR", 100.0), av("ExchangeRate", "EUR", 1.10),
        av("CashBalance", "JPY", -20000.0), av("ExchangeRate", "JPY", 0.0065),
    ]
    assert fx_book(vals).legs == 2


def test_excludes_base_currency_and_the_base_pseudo_row():
    """USD (the base) funds the book and IBKR's synthetic BASE row is the total — neither is a leg."""
    vals = [
        av("CashBalance", "BASE", 95_000.0), av("ExchangeRate", "BASE", 1.0),
        av("CashBalance", "USD", 94_000.0), av("ExchangeRate", "USD", 1.0),
        av("CashBalance", "EUR", 100.0), av("ExchangeRate", "EUR", 1.10),
    ]
    book = fx_book(vals)
    assert book.legs == 1
    assert book.net_base == pytest.approx(110.0)


def test_nets_longs_against_shorts_but_grosses_absolutes():
    vals = [
        av("CashBalance", "EUR", 100.0), av("ExchangeRate", "EUR", 1.10),
        av("CashBalance", "CHF", -100.0), av("ExchangeRate", "CHF", 1.20),
    ]
    book = fx_book(vals)
    assert book.net_base == pytest.approx(110.0 - 120.0)
    assert book.gross_base == pytest.approx(110.0 + 120.0)


def test_accrued_interest_counts_toward_net_because_it_is_the_carry():
    """CashBalance omits accrued interest, which for a carry book IS the return."""
    vals = [
        av("CashBalance", "EUR", 100.0), av("AccruedCash", "EUR", 10.0),
        av("ExchangeRate", "EUR", 1.10),
    ]
    book = fx_book(vals)
    assert book.net_base == pytest.approx(121.0)     # (100 + 10) * 1.10
    assert book.accrued_base == pytest.approx(11.0)
    assert book.gross_base == pytest.approx(110.0)   # exposure is cash only


def test_a_short_leg_accrues_negative_carry():
    vals = [
        av("CashBalance", "MXN", -2_181_551.05), av("AccruedCash", "MXN", -7_459.29),
        av("ExchangeRate", "MXN", 0.0587404),
    ]
    book = fx_book(vals)
    assert book.accrued_base == pytest.approx(-438.14, abs=0.1)
    assert book.net_base < book.gross_base * -1 + 1e-6   # more negative than cash alone


def test_dust_below_threshold_is_a_closed_leg():
    """Settled interest leaves sub-dollar residue in a currency the book is flat in."""
    vals = [
        av("CashBalance", "EUR", 100.0), av("ExchangeRate", "EUR", 1.10),
        av("CashBalance", "HUF", 50.0), av("ExchangeRate", "HUF", 0.0031865),  # ~$0.16
    ]
    book = fx_book(vals)
    assert book.legs == 1
    assert book.gross_base == pytest.approx(110.0)


def test_zero_balance_is_not_a_leg():
    vals = [
        av("CashBalance", "CZK", 0.0), av("ExchangeRate", "CZK", 0.045),
        av("CashBalance", "EUR", 100.0), av("ExchangeRate", "EUR", 1.10),
    ]
    assert fx_book(vals).legs == 1


def test_missing_exchange_rate_raises_rather_than_undervaluing_the_book():
    """Silently valuing an unrated currency at zero would understate the book."""
    vals = [av("CashBalance", "ZAR", 594_607.0)]
    with pytest.raises(ValueError, match="ZAR"):
        fx_book(vals)


def test_net_base_is_unmoved_by_base_currency_cash():
    """ETF trades move only USD cash, so they must leave net_base alone."""
    legs = [
        av("CashBalance", "EUR", 100.0), av("ExchangeRate", "EUR", 1.10),
        av("ExchangeRate", "USD", 1.0),
    ]
    before = fx_book(legs + [av("CashBalance", "USD", 96_000.0)])
    after = fx_book(legs + [av("CashBalance", "USD", 46_000.0)])  # bought $50k of ETFs
    assert before.net_base == after.net_base


# The 2026-08-16 DUQ218063 account, captured from ib.accountValues().
LIVE = {  # ccy: (CashBalance, AccruedCash, ExchangeRate)
    "AUD": (-1594.78, -3.06, 0.7084021), "CAD": (119243.49, 32.84, 0.7207142),
    "CHF": (-80184.90, -31.59, 1.2295211), "EUR": (94343.70, 7.86, 1.1570004),
    "GBP": (54649.94, 54.48, 1.35359), "HUF": (20662653.11, 14972.86, 0.0031865),
    "ILS": (-264772.15, -769.99, 0.3384594), "JPY": (-4898985.43, 508.00, 0.0062766),
    "MXN": (-2181551.05, -7459.29, 0.0587404), "NOK": (956100.98, 628.14, 0.1058961),
    "NZD": (43914.22, 0.00, 0.5891625), "PLN": (-305062.66, -915.20, 0.268613),
    "SEK": (-643976.52, -730.65, 0.1049873), "ZAR": (594607.54, -42.03, 0.0617543),
    "CZK": (0.0, 0.0, 0.0456),
}
LIVE_BASE_CASH, LIVE_USD_CASH = 96303.4537, 95558.70


def live_values():
    vals = [av("CashBalance", "BASE", LIVE_BASE_CASH), av("ExchangeRate", "BASE", 1.0),
            av("CashBalance", "USD", LIVE_USD_CASH), av("ExchangeRate", "USD", 1.0)]
    for ccy, (cash, accrued, rate) in LIVE.items():
        vals += [av("CashBalance", ccy, cash), av("AccruedCash", ccy, accrued),
                 av("ExchangeRate", ccy, rate)]
    return vals


def test_live_account_legs_and_gross():
    book = fx_book(live_values())
    assert book.legs == 14                     # 15-currency universe, CZK flat
    assert book.gross_base > 900_000           # gross ~1x NAV


def test_live_account_is_dollar_neutral():
    """The book is a dollar-neutral basket: net is a rounding error against gross."""
    book = fx_book(live_values())
    assert abs(book.net_base) < 0.005 * book.gross_base


def test_live_account_reconciles_with_ibkrs_own_base_cash_row():
    """Our cash total should track IBKR's BASE-minus-USD figure.

    It does not match to the cent: IBKR aggregates BASE on its own rate snapshot, which drifts
    from the ExchangeRate rows by a small fraction of a ~900k gross book (~225 base, 0.025%,
    when this fixture was captured). Assert the tolerance we actually observe, not equality.
    """
    book = fx_book(live_values())
    cash_only = book.net_base - book.accrued_base
    assert cash_only == pytest.approx(LIVE_BASE_CASH - LIVE_USD_CASH,
                                      abs=0.0005 * book.gross_base)


def test_live_account_carry_is_currently_negative():
    """Paper-account rate spreads are charged on both legs, so the book net-pays accrued."""
    assert fx_book(live_values()).accrued_base < 0
