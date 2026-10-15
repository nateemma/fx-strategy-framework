"""The six simple long/short candidates, as data. Spec 009.

These were ranked in `docs/investable-universe-survey.md` §5 in August 2026 and never gated. The
reason they were never gated is the point: they were ranked by how much they would add to the
existing ETF book, and Constitution 1.1.0 later corrected exactly that habit with the
STANDALONE-FIRST rule. So each is judged here on whether it would be worth running on its own
capital, which is a different question from the one that shelved them.

Register, not registry — this is a plain list the gate scripts iterate so neither hardcodes six
paths. It discovers nothing and nothing imports it to find a `Strategy`; Principle I forbids that.

`shortable_cleanly` is the uncomfortable field. `forex/backtest/financing.py` is keyed by CURRENCY
because it was built to cost multi-currency cash balances for the FX book. A US ETF pair has one
currency and two instrument legs, and stock borrow is absent from this repo entirely — so a short
ETF leg CANNOT be honestly costed here. Where that is the case the verdict is capped at
`inconclusive` rather than quietly assuming free shorting (spec 009 research R2).
"""
from typing import NamedTuple


class Candidate(NamedTuple):
    id: str                   # survey ID, how the backlog refers to it
    name: str
    hypothesis: str           # what edge is claimed, in one sentence
    signal_series: tuple      # free macro series the signal needs; () when there are none
    screen_symbols: tuple     # instruments used to SCREEN it; () until a data gate passes
    deploy_instrument: str    # what it would actually trade — often NOT the screen instrument
    shortable_cleanly: bool   # can its short leg be honestly costed? See the module docstring.
    kill_criterion: str       # the cheap test that ends it, evaluable in hours


REGISTER = [
    Candidate(
        "A3", "Treasury curve 2s10s",
        "The 2s10s slope is a slow, non-price-predictive signal, and a steepener/flattener held in "
        "futures is financing-efficient — the one signal shape with a track record in this repo.",
        ("DGS2", "DGS10"), ("SHY", "IEF", "TLT"), "Treasury futures (ZT/ZF/ZN)",
        False,   # the ETF-PROXY screen needs a short leg; the futures deployment would not
        "No edge in both eras net of cost",
    ),
    Candidate(
        "B4", "Equity-index futures basis",
        "The spread between index futures and spot is harvestable and very capital-efficient.",
        (), ("ES=F", "SPY"), "Index future vs index ETF",
        True,    # the short leg IS the future — the one candidate clean on financing
        "Basis narrower than round-trip commission",
    ),
    Candidate(
        "B5", "TIPS breakeven",
        "Inflation expectations are slow and macro-driven, so a TIP-versus-nominal spread is a "
        "carry-like position rather than a price prediction.",
        ("T10YIE", "DFII10", "DGS10"), ("TIP", "IEF"), "ETF pair, or TIPS/Treasury futures",
        False,
        "No edge in both eras net of cost",
    ),
    Candidate(
        "B6", "Credit spread",
        "The credit risk premium is real and harvestable long credit / short duration.",
        ("BAMLH0A0HYM2",), ("HYG", "LQD", "IEF", "TLT"), "ETF pair",
        False,
        "No edge in both eras net of cost",
    ),
    Candidate(
        "B2", "CEF discount mean-reversion",
        "Closed-end funds trade at persistent, mean-reverting discounts to NAV; long-only, "
        "cash-financed, low turnover.",
        (), (),   # deliberately unset — the data gate decides whether this is testable at all
        "Long-only basket of CEFs",
        True,    # long only, so no borrow question
        "No free historical discount/NAV data",
    ),
    Candidate(
        "B3", "Post-earnings-announcement drift",
        "The most-replicated equity anomaly: prices continue drifting in the direction of an "
        "earnings surprise. Long-only implementable.",
        (), (),   # deliberately unset — see B2
        "Long-only basket of equities",
        True,
        "No free bulk earnings-date and surprise history",
    ),
]

BY_ID = {c.id: c for c in REGISTER}
