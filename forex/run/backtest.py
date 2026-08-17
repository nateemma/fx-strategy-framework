from forex.core.result import Result
from forex.data.prices import spot_returns
from forex.features.carry import carry_signal
from forex.backtest.portfolio import simulate, metrics
from forex.backtest.financing import financing_spreads

def returns_of(weights, view, cost_bps: float = 1.0, financing: bool = False):
    rets = spot_returns(view.spot)
    codes = list(weights.columns)
    carry = carry_signal(view.calendar, view.rates)[codes].fillna(0.0)
    fin = financing_spreads(view.calendar, view.rates, codes) if financing else None
    return simulate(weights, rets, carry=carry, cost_bps=cost_bps, financing=fin)

def backtest(strategy, view, cost_bps: float = 1.0, financing: bool = False) -> Result:
    weights = strategy.target_weights(view)
    daily = returns_of(weights, view, cost_bps, financing)
    return Result(returns=daily, weights=weights, metrics=metrics(daily))
