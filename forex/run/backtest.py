from forex.core.result import Result
from forex.data.prices import spot_returns
from forex.features.carry import carry_signal
from forex.backtest.portfolio import simulate, metrics

def returns_of(weights, view, cost_bps: float = 1.0):
    rets = spot_returns(view.spot)
    carry = carry_signal(view.calendar, view.rates)[list(weights.columns)].fillna(0.0)
    return simulate(weights, rets, carry=carry, cost_bps=cost_bps)

def backtest(strategy, view, cost_bps: float = 1.0) -> Result:
    weights = strategy.target_weights(view)
    daily = returns_of(weights, view, cost_bps)
    return Result(returns=daily, weights=weights, metrics=metrics(daily))
