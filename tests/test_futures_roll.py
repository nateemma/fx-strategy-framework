from datetime import date

import pytest

from forex.run.futures_roll import front_expiry, needs_roll, reconcile_market

# A typical quarterly cycle as IBKR would report it
Q = [date(2026, 3, 20), date(2026, 6, 19), date(2026, 9, 18), date(2026, 12, 18)]


# ---------------------------------------------------------------- which contract to hold

def test_front_is_the_nearest_expiry_far_enough_away():
    assert front_expiry(Q, date(2026, 1, 15)) == date(2026, 3, 20)


def test_front_rolls_forward_once_the_near_contract_is_inside_the_roll_window():
    """A week before expiry the March contract is no longer the one to hold."""
    assert front_expiry(Q, date(2026, 3, 16), roll_days=7) == date(2026, 6, 19)


def test_the_roll_window_is_configurable():
    assert front_expiry(Q, date(2026, 3, 16), roll_days=2) == date(2026, 3, 20)
    assert front_expiry(Q, date(2026, 3, 16), roll_days=10) == date(2026, 6, 19)


def test_front_is_none_when_every_contract_is_too_near():
    assert front_expiry([date(2026, 3, 20)], date(2026, 3, 19)) is None


def test_expiries_need_not_be_sorted():
    assert front_expiry(list(reversed(Q)), date(2026, 1, 15)) == date(2026, 3, 20)


def test_no_expiries_at_all_is_no_front_contract():
    assert front_expiry([], date(2026, 1, 15)) is None


# ---------------------------------------------------------------- when to roll

def test_a_held_contract_needs_rolling_inside_the_window():
    assert needs_roll(date(2026, 3, 20), date(2026, 3, 16), roll_days=7) is True


def test_a_held_contract_far_from_expiry_does_not():
    assert needs_roll(date(2026, 6, 19), date(2026, 3, 16), roll_days=7) is False


def test_holding_nothing_never_needs_a_roll():
    assert needs_roll(None, date(2026, 3, 16)) is False


def test_the_roll_boundary_is_inclusive():
    """Exactly at the boundary, roll — do not leave it to the last session."""
    assert needs_roll(date(2026, 3, 20), date(2026, 3, 13), roll_days=7) is True


# ---------------------------------------------------------------- reconciliation per MARKET

def test_an_unchanged_target_places_nothing():
    orders = reconcile_market(target=3, held={date(2026, 6, 19): 3}, front=date(2026, 6, 19))
    assert orders == {}


def test_a_roll_closes_the_old_and_opens_the_new_preserving_exposure():
    """The signal has not changed — only the contract has. Net market exposure must be unchanged."""
    orders = reconcile_market(target=3, held={date(2026, 3, 20): 3}, front=date(2026, 6, 19))
    assert orders == {date(2026, 3, 20): -3, date(2026, 6, 19): 3}
    assert sum(orders.values()) == 0, "a pure roll must not change net exposure"


def test_a_signal_change_without_a_roll_is_a_single_order():
    orders = reconcile_market(target=5, held={date(2026, 6, 19): 3}, front=date(2026, 6, 19))
    assert orders == {date(2026, 6, 19): 2}


def test_a_signal_flip_without_a_roll_crosses_through_zero_in_one_order():
    orders = reconcile_market(target=-2, held={date(2026, 6, 19): 3}, front=date(2026, 6, 19))
    assert orders == {date(2026, 6, 19): -5}


def test_a_roll_and_a_signal_change_together():
    orders = reconcile_market(target=5, held={date(2026, 3, 20): 3}, front=date(2026, 6, 19))
    assert orders == {date(2026, 3, 20): -3, date(2026, 6, 19): 5}


def test_opening_a_first_position():
    assert reconcile_market(target=4, held={}, front=date(2026, 6, 19)) == {date(2026, 6, 19): 4}


def test_going_flat_closes_everything():
    orders = reconcile_market(target=0, held={date(2026, 6, 19): 3}, front=date(2026, 6, 19))
    assert orders == {date(2026, 6, 19): -3}


def test_a_stale_contract_is_closed_even_when_the_target_is_zero():
    """A position left in an expiring contract must not be forgotten just because the signal is flat."""
    orders = reconcile_market(target=0, held={date(2026, 3, 20): 2}, front=date(2026, 6, 19))
    assert orders == {date(2026, 3, 20): -2}


def test_positions_scattered_across_several_contracts_are_consolidated():
    orders = reconcile_market(target=4, held={date(2026, 3, 20): 2, date(2026, 6, 19): 1},
                              front=date(2026, 9, 18))
    assert orders == {date(2026, 3, 20): -2, date(2026, 6, 19): -1, date(2026, 9, 18): 4}


def test_no_front_contract_means_close_out_and_open_nothing():
    orders = reconcile_market(target=3, held={date(2026, 3, 20): 2}, front=None)
    assert orders == {date(2026, 3, 20): -2}


def test_a_roll_is_distinguishable_from_a_round_trip():
    """Exposure-neutral rolls must be identifiable so they are not mistaken for signal churn."""
    roll = reconcile_market(target=3, held={date(2026, 3, 20): 3}, front=date(2026, 6, 19))
    churn = reconcile_market(target=0, held={date(2026, 6, 19): 3}, front=date(2026, 6, 19))
    assert sum(roll.values()) == 0
    assert sum(churn.values()) == -3


@pytest.mark.parametrize("target", [-3, 0, 3])
def test_reconciling_an_already_correct_book_is_always_a_no_op(target):
    held = {date(2026, 6, 19): target} if target else {}
    assert reconcile_market(target, held, date(2026, 6, 19)) == {}
