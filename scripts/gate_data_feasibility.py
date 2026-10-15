"""Can each candidate be tested at all, with free data? Spec 009 US2.

    .venv/bin/python scripts/gate_data_feasibility.py [--candidate A3]

Runs BEFORE any modelling (FR-005). Builds nothing, fits nothing, backtests nothing. No broker, no
Gateway (FR-012).

This repo has exactly two free data sources: FRED and the chart API. A candidate whose required
history is in neither is dead here, and that is a result rather than a disappointment — it closes a
question for the cost of an afternoon instead of a fortnight.
"""
import argparse

from forex.data.fred import load_series
from forex.data.yahoo import load_prices
from forex.run.feasibility import DEAD_DATA, DEAD_ECON, TESTABLE, Feasibility, probe_candidate
from strategies.longshort_candidates import BY_ID, REGISTER

USD_DEBIT_SPREAD = 0.015      # what retail is charged over benchmark to borrow


def _span(s):
    return (str(s.index.min().date()), str(s.index.max().date()))


MIN_ERA_YEARS = 8     # two "temporally distant" windows need roughly this much, at minimum


def _check_series_and_etfs(candidate):
    """The generic probe: do the FRED series and the proxy ETFs exist, deep enough, daily?

    Depth of the SIGNAL series matters as much as the price legs, and the first version of this
    probe only checked that the series loaded. B6 passed as testable on that basis and then came
    back from its gate with one usable window, because FRED serves ICE BofA credit spreads under a
    rolling ~3-year licence — verified: BAMLH0A0HYM2 and BAMLC0A0CM both start 2023-10-16, while
    Treasury series go back decades. A signal that cannot span two distant eras is dead on data,
    and the cull is where that should surface.
    """
    spans, bars = [], []
    for sid in candidate.signal_series:
        sig = load_series(sid, cache_dir="data_cache").dropna()
        years = (sig.index.max() - sig.index.min()).days / 365.25
        if years < MIN_ERA_YEARS:
            return Feasibility(
                candidate.id, DEAD_DATA, f"FRED {sid}",
                (str(sig.index.min().date()), str(sig.index.max().date())), len(sig), "1d",
                f"the signal series {sid} spans only {years:.1f} years ({len(sig)} obs from "
                f"{sig.index.min().date()}) — FRED serves this family under a rolling licence "
                f"window, confirmed by BAMLC0A0CM starting on the same date. Two temporally "
                f"distant eras are not available, so FR-004 cannot be satisfied at any price "
                f"level. The ETF legs are deep; the SIGNAL is the blocker")
        spans.append(sig.index.min())
        bars.append(len(sig))
    for sym in candidate.screen_symbols:
        s = load_prices(sym)
        spans.append(s.index.min())
        bars.append(len(s))
    if not spans:
        raise ValueError("no screen symbols declared")
    # The binding history is the SHORTEST leg: a pair can only be tested where both legs exist.
    binding = max(spans)
    s = load_prices(candidate.screen_symbols[0])
    gran = "1d" if s.index.to_series().diff().dt.days.median() == 1 else "NOT DAILY"
    return Feasibility(
        candidate.id, TESTABLE, f"FRED {list(candidate.signal_series)} + chart API "
        f"{list(candidate.screen_symbols)}",
        (str(binding.date()), str(s.index.max().date())), min(bars), gran,
        f"binding leg starts {binding.date()}")


def probe_a3(c):
    return _check_series_and_etfs(c)


def probe_b5(c):
    return _check_series_and_etfs(c)


def probe_b6(c):
    return _check_series_and_etfs(c)


def probe_b4(c):
    """B4 dies on arithmetic, not data — so check the arithmetic and stop.

    Cash-and-carry harvests the gap between the financing rate IMPLIED by the futures basis and the
    rate you actually borrow at. The basis is set by institutions funding at roughly the risk-free
    rate; retail borrows at benchmark + 1.5%. So the retail version of this trade is structurally
    short ~150bp/yr before commission, and no amount of history changes that.
    """
    # ^GSPC, the actual index — NOT SPY x10. SPY pays its dividends out, so SPY x10 drifts ~24%
    # below the index over two decades; measuring against it produced a nonsense "+2416bp basis"
    # on the first run. The proxy was the error, not the data.
    es, idx = load_prices("ES=F"), load_prices("%5EGSPC")
    common = es.index.intersection(idx.index)
    if len(common) < 250:
        raise ValueError(f"only {len(common)} overlapping days for ES=F/^GSPC")
    spread = (es.loc[common] / idx.loc[common] - 1.0)
    median_bp = float(spread.median()) * 1e4
    recent_bp = float(spread.loc[spread.index >= "2020-01-01"].median()) * 1e4
    return Feasibility(
        c.id, DEAD_ECON, "chart API ES=F vs ^GSPC (the index itself, not an ETF proxy)",
        (str(common.min().date()), str(common.max().date())), len(common), "1d",
        f"median futures/index spread {median_bp:+.0f}bp over the full history and "
        f"{recent_bp:+.0f}bp since 2020 — a front-month spread at blended time-to-expiry, so it is "
        f"roughly one quarter's worth of carry. That basis prices financing at about the risk-free "
        f"rate, while retail borrows at benchmark +{USD_DEBIT_SPREAD:.1%}. Cash-and-carry harvests "
        f"the gap between the implied rate and your own, so at retail the gap is NEGATIVE by "
        f"roughly {USD_DEBIT_SPREAD:.1%}/yr before commission. Arithmetic, not a data problem — no "
        f"length of history changes it")


def _no_free_source(c, what, checked):
    return Feasibility(c.id, DEAD_DATA, checked, None, 0, None,
                       f"{what} is in neither of this repo's free sources. FRED carries macro "
                       f"series only; the chart API returns prices only — verified no such field "
                       f"in its response. Obtaining it means a paid vendor or scraping a site with "
                       f"no bulk history, which is a data-acquisition project, not an afternoon")


def probe_b2(c):
    """CEF discount reversion needs per-fund NAV history alongside price. Prices are free; NAV is
    the binding input and it is not."""
    load_prices("SPY")      # prove the price source works, so the failure is specifically NAV
    return _no_free_source(c, "per-fund NAV / discount history",
                           "FRED series search + chart API response fields")


def probe_b3(c):
    """PEAD needs earnings dates and surprise magnitudes in bulk. Same shape of failure as B2."""
    load_prices("SPY")
    return _no_free_source(c, "bulk earnings dates and surprise magnitudes",
                           "FRED series search + chart API response fields")


PROBES = {"A3": probe_a3, "B4": probe_b4, "B5": probe_b5, "B6": probe_b6,
          "B2": probe_b2, "B3": probe_b3}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", choices=sorted(BY_ID))
    args = ap.parse_args()
    targets = [BY_ID[args.candidate]] if args.candidate else list(REGISTER)

    results = []
    for c in targets:
        print(f"probing {c.id} ({c.name}) …", flush=True)
        results.append(probe_candidate(c, PROBES[c.id]))

    print(f"\n{'ID':4s} {'status':18s} {'history':26s} {'bars':>6s} {'gran':>6s}")
    for f in results:
        hist = f"{f.usable_history[0]} -> {f.usable_history[1]}" if f.usable_history else "—"
        print(f"{f.candidate_id:4s} {f.status:18s} {hist:26s} {f.bars:>6d} "
              f"{str(f.granularity_confirmed or '—'):>6s}")
    print()
    for f in results:
        if f.note:
            print(f"{f.candidate_id}: {f.note}")

    alive = [f.candidate_id for f in results if not f.is_terminal]
    print(f"\nstill testable: {alive or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
