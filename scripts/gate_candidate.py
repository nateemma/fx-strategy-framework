"""Run one candidate's standalone gate and print its verdict. Spec 009.

    .venv/bin/python scripts/gate_candidate.py --candidate A3 [--refresh]

Read-only except for the data cache. No broker, no Gateway, no order path (FR-012) — prices come
from the free chart API and macro series from FRED.

A verdict here is "worth a real build later" at its very best. It is never "trade it": going live
is a separate gated decision and the paper track has been stopped since 2026-10-14.
"""
import argparse

import pandas as pd

from forex.backtest.gate import evaluate
from forex.data.fred import load_series
from forex.data.yahoo import load_prices
from strategies.curve_spread import curve_signal, spread_returns
from strategies.macro_spread import pair_returns, spread_signal
from strategies.longshort_candidates import BY_ID

# Effective durations, iShares factsheets 2026. Used only to make the legs duration-neutral; the
# verdict is not sensitive to the second decimal place.
DURATION = {"SHY": 1.9, "IEF": 7.4, "TLT": 15.8, "TIP": 6.7, "HYG": 3.2, "LQD": 8.4}

# A margined USD long is charged the published tier-1 debit spread over benchmark. The SHORT leg's
# borrow cost is NOT included — this repo has no equity-borrow data and inventing a constant would
# be a made-up number driving a verdict (research R2). Hence borrow_excluded below.
USD_DEBIT_SPREAD = 0.015
ETF_COST_BPS = 2.0            # round-trip on a liquid ETF at retail
CACHE = "data_cache"


def _cash_benchmark(index) -> pd.Series:
    """Holding cash. For a market-neutral spread this is the honest comparator: the trade is
    self-financing in dollar terms, so beating zero is the minimum bar (FR-002)."""
    return pd.Series(0.0, index=index, dtype="float64")


def gate_a3(refresh: bool) -> tuple:
    """A3 — the 2s10s curve trade, screened with ETF proxies."""
    two = load_series("DGS2", cache_dir=CACHE, force=refresh).astype("float64")
    ten = load_series("DGS10", cache_dir=CACHE, force=refresh).astype("float64")
    slope = (ten - two).dropna()

    short_end = load_prices("SHY", force=refresh)
    long_end = load_prices("IEF", force=refresh)

    common = slope.index.intersection(short_end.index).intersection(long_end.index)
    slope, short_end, long_end = slope.loc[common], short_end.loc[common], long_end.loc[common]
    print(f"  aligned history: {len(common)} days, {common.min().date()} -> {common.max().date()}")

    sig = curve_signal(slope)
    d_s, d_l = DURATION["SHY"], DURATION["IEF"]
    rets = spread_returns(sig, short_end, long_end, d_s, d_l)

    # Gross exposure per unit of signal, and the turnover the position actually generates.
    gross_per_unit = 1.0 + d_s / d_l
    pos = sig.shift(1).reindex(rets.index).fillna(0.0)
    turnover = pos.diff().abs().fillna(0.0) * gross_per_unit

    # holdout_years picked as ~the midpoint of the aligned history, NOT the function's default of 3
    # (research R3). Recorded here because the split is part of what makes the verdict reproducible.
    span_years = (common.max() - common.min()).days / 365.25
    holdout = int(round(span_years / 2))
    print(f"  era split: holdout_years={holdout} (history spans {span_years:.1f} years)")

    verdict = evaluate(
        rets, _cash_benchmark(rets.index), holdout_years=holdout, cost_bps=ETF_COST_BPS,
        financing_annual=USD_DEBIT_SPREAD, turnover=turnover, borrow_excluded=True,
        candidate_id="A3", benchmark_name="cash")
    return verdict, holdout


def _gate_pair(cid, spread: pd.Series, risk_sym: str, hedge_sym: str, refresh: bool,
               benchmark_name="cash") -> tuple:
    """B5 and B6: a FRED spread drives a long-risk / short-hedge ETF pair.

    borrow_excluded=True for both — the short leg cannot be costed here, so the result is an upper
    bound and the verdict is capped at inconclusive (research R2).
    """
    risk = load_prices(risk_sym, force=refresh)
    hedge = load_prices(hedge_sym, force=refresh)
    common = spread.index.intersection(risk.index).intersection(hedge.index)
    spread, risk, hedge = spread.loc[common], risk.loc[common], hedge.loc[common]
    print(f"  aligned history: {len(common)} days, {common.min().date()} -> {common.max().date()}")
    print(f"  legs: long {risk_sym} / short {hedge_sym}")

    sig = spread_signal(spread)
    rets = pair_returns(sig, risk, hedge)
    pos = sig.shift(1).reindex(rets.index).fillna(0.0)
    turnover = pos.diff().abs().fillna(0.0) * 2.0      # two legs, equal dollars

    span_years = (common.max() - common.min()).days / 365.25
    holdout = int(round(span_years / 2))
    print(f"  era split: holdout_years={holdout} (history spans {span_years:.1f} years)")

    verdict = evaluate(rets, _cash_benchmark(rets.index), holdout_years=holdout,
                       cost_bps=ETF_COST_BPS, financing_annual=USD_DEBIT_SPREAD,
                       turnover=turnover, borrow_excluded=True, candidate_id=cid,
                       benchmark_name=benchmark_name)
    return verdict, holdout


def gate_b5(refresh: bool) -> tuple:
    """B5 — the 10-year TIPS breakeven, traded as TIP against nominal duration."""
    be = load_series("T10YIE", cache_dir=CACHE, force=refresh).astype("float64").dropna()
    return _gate_pair("B5", be, "TIP", "IEF", refresh)


def gate_b6(refresh: bool) -> tuple:
    """B6 — the high-yield option-adjusted spread, traded as HYG against Treasury duration.

    Its ORIGINAL gate in the survey asked "does it add anything the basket does not already have?"
    That is the portfolio-contribution question spec 009 exists to replace, so this is the first
    time it has been asked to stand on its own.
    """
    oas = load_series("BAMLH0A0HYM2", cache_dir=CACHE, force=refresh).astype("float64").dropna()
    return _gate_pair("B6", oas, "HYG", "IEF", refresh)


GATES = {"A3": gate_a3, "B5": gate_b5, "B6": gate_b6}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", required=True, choices=sorted(BY_ID))
    ap.add_argument("--refresh", action="store_true", help="refetch rather than use the cache")
    args = ap.parse_args()

    cand = BY_ID[args.candidate]
    print(f"=== {cand.id}: {cand.name} ===")
    print(f"  hypothesis: {cand.hypothesis}")
    print(f"  kill criterion: {cand.kill_criterion}")
    print(f"  deploys as: {cand.deploy_instrument}")
    print(f"  short leg costable: {cand.shortable_cleanly}")

    if cand.id not in GATES:
        print(f"\n  no gate implemented for {cand.id} — run scripts/gate_data_feasibility.py first")
        return 2

    verdict, holdout = GATES[cand.id](args.refresh)

    print(f"\n  cost basis: {verdict.cost_basis}")
    print(f"  benchmark:  {verdict.benchmark}")
    print(f"\n  {'era':8s} {'from':11s} {'to':11s} {'days':>6s} {'sharpe':>8s} "
          f"{'ann ret':>9s} {'maxDD':>8s} {'bench':>7s} {'beats?':>7s}")
    for w in verdict.per_window:
        print(f"  {w.label:8s} {str(w.start.date()):11s} {str(w.end.date()):11s} {w.n_days:>6d} "
              f"{w.sharpe_net:>8.2f} {w.return_net:>8.2%} {w.max_dd:>8.2%} "
              f"{w.benchmark_sharpe:>7.2f} {str(w.beats_benchmark):>7s}")

    print(f"\n  VERDICT: {verdict.verdict.upper()}")
    print(f"  {verdict.reasoning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
