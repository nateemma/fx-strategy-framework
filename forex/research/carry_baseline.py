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
    # FRED IR3TIB rates are quoted in percent -> convert to annualized decimal
    rates = {"USD": loader(CURRENCIES["USD"].rate_fred, cache_dir=cache_dir) / 100.0}
    for c in codes:
        rates[c] = loader(CURRENCIES[c].rate_fred, cache_dir=cache_dir) / 100.0
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
