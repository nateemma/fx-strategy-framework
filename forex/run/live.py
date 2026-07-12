def rebalance_now(strategy, view, execution):
    """Compute the strategy's target weights as of the latest available date and reconcile them
    against the executor. The one 'compute-target-and-reconcile' seam shared by dry-run and live."""
    weights = strategy.target_weights(view.truncate(view.calendar[-1]))
    target = weights.iloc[-1]
    prices = view.spot.iloc[-1]
    return execution.rebalance(target, prices)
