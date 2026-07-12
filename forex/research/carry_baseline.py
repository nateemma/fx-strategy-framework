from forex.config import CURRENCIES
from forex.data.fred import load_series
from forex.data.prices import build_spot_panel, spot_returns
from forex.features.carry import carry_signal, basket_weights
from forex.backtest.portfolio import simulate, metrics

def run_baseline(cache_dir, loader=load_series, codes=None,
                 n_long=3, n_short=3, cost_bps=1.0):
    from forex.core.dataview import DataView
    from forex.strategies.carry import CarryStrategy
    from forex.run.backtest import backtest
    view = DataView.from_fred(cache_dir, loader=loader, codes=codes)
    r = backtest(CarryStrategy(n_long=n_long, n_short=n_short), view, cost_bps=cost_bps)
    return r.returns, r.metrics

if __name__ == "__main__":
    import pandas as pd
    from forex.config import CURRENCIES
    from forex.data.fred import load_series
    from forex.data.prices import build_spot_panel, spot_returns
    from forex.features.carry import carry_signal, basket_weights
    from forex.backtest.portfolio import simulate, metrics, attribution
    from forex.backtest.validation import distant_window

    CACHE = "data_cache"
    codes = [c for c in CURRENCIES if c != "USD"]
    panel = build_spot_panel(CACHE, loader=load_series, codes=codes)
    rets = spot_returns(panel)
    cal = panel.index
    rates = {"USD": load_series(CURRENCIES["USD"].rate_fred, cache_dir=CACHE) / 100.0}
    for c in codes:
        rates[c] = load_series(CURRENCIES[c].rate_fred, cache_dir=CACHE) / 100.0
    signal = carry_signal(cal, rates)
    weights = basket_weights(signal[codes], n_long=3, n_short=3)
    carry = signal[codes].fillna(0.0)
    daily = simulate(weights, rets, carry=carry, cost_bps=1.0)

    active = weights.abs().sum(axis=1) > 0
    first = active.idxmax()
    print("=" * 64)
    print("BARE G10 CARRY BASELINE  (long top-3 / short bottom-3 carry, daily)")
    print("=" * 64)
    print(f"Data span      : {daily.index[0].date()} -> {daily.index[-1].date()}")
    print(f"Tradeable from : {first.date()}  (needs >=6 currencies with rate data)")
    print("Costs 1.0 bp/turnover; weights act on next day (no lookahead).")
    print("Returns are DECIMAL fractions (0.42 = +42%); Sharpe has NO risk-free subtracted.\n")

    for label, d in [("FULL span", daily), ("TRADEABLE window", daily.loc[first:])]:
        m = metrics(d)
        print(f"{label}  {d.index[0].date()}..{d.index[-1].date()}")
        print(f"  total {m['total_return']*100:+.0f}%  ann {m['ann_return']*100:+.1f}%  "
              f"vol {m['ann_vol']*100:.1f}%  Sharpe {m['sharpe']:.2f}  "
              f"maxDD {m['max_drawdown']*100:.0f}%  Calmar {m['calmar']:.2f}")

    att = attribution(weights, rets, carry).sort_values("total", ascending=False) * 100
    att["days_long"] = (weights > 0).sum()
    att["days_short"] = (weights < 0).sum()
    print("\nPER-CURRENCY ATTRIBUTION (additive % contribution)")
    print(att.to_string(float_format=lambda x: f"{x:8.2f}"))
    print(f"\n  spot {att['spot'].sum():+.1f}%   carry {att['carry'].sum():+.1f}%   "
          f"total {att['total'].sum():+.1f}% (gross, pre-cost)")

    recent, dist = distant_window(daily.index, holdout_years=3)
    print(f"\nDistant-era {daily.index[dist][0].date()}..{daily.index[dist][-1].date()}: "
          f"{((1+daily.iloc[dist]).prod()-1)*100:+.1f}%   "
          f"Recent {((1+daily.iloc[recent]).prod()-1)*100:+.1f}%")
