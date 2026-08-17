"""Which futures contract to hold, and how to reconcile a book across a roll.

Rolling wrong silently doubles or zeroes a position, so this is a separate, pure module: "what should
I hold today" is a calendar question that can be settled without a broker, and it is settled before
anything places an order.

The expiry dates come from the broker at runtime rather than from encoded exchange calendars — every
exchange has its own rules and they change, whereas a list of live expiries is always current.

The reconciler works **per market, not per contract**. That distinction matters: a roll is
`close 3 of March, open 3 of June`, which in contract terms looks exactly like a full round-trip.
Netting per market keeps a roll identifiable — a pure roll sums to zero exposure change — so it is
never mistaken for the signal churning.
"""
from datetime import timedelta

ROLL_DAYS = 7      # start rolling a week out; avoids expiry-week liquidity and delivery mechanics


def front_expiry(expiries, asof, roll_days: int = ROLL_DAYS):
    """The expiry to hold on `asof`: the nearest one still outside the roll window.

    Returns None when every available contract is inside the window — the caller should close out
    rather than open a position it would immediately have to roll.
    """
    cutoff = asof + timedelta(days=roll_days)
    eligible = sorted(e for e in expiries if e > cutoff)
    return eligible[0] if eligible else None


def needs_roll(held_expiry, asof, roll_days: int = ROLL_DAYS) -> bool:
    """Is the held contract inside its roll window? Holding nothing never needs a roll."""
    if held_expiry is None:
        return False
    return asof >= held_expiry - timedelta(days=roll_days)


def reconcile_market(target: int, held: dict, front):
    """Orders per expiry to move one market from `held` to `target` contracts of `front`.

    `held` maps expiry -> signed contracts currently held in this market. Anything not in the front
    contract is closed, and the target is expressed entirely in the front contract, so a roll comes
    out as a matched pair that nets to zero exposure change.

    `front=None` means no contract is far enough from expiry to hold: close out, open nothing.
    """
    orders = {}
    for expiry, qty in held.items():
        if expiry != front and qty:
            orders[expiry] = -qty                     # stale or rolling-off contract: close it
    if front is not None:
        delta = target - held.get(front, 0)
        if delta:
            orders[front] = delta
    return orders
