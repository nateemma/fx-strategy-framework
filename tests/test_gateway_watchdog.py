"""The watchdog's decision logic — the part that must not cry wolf.

Two measured durations bound the debounce (spec 008 research R2): an automatic re-login took ~45s on
2026-10-08, and a cold start after a hard kill took 2m06s. At a 300s probe interval, requiring two
consecutive failures puts the alert floor above both. Tests here assert both directions, because this
feature can fail by alarming too much as easily as by alarming too little — SC-004 treats a false
alarm as a defect of the same severity as a missed one.
"""
from datetime import datetime, timedelta, timezone

from forex.run.gateway_watchdog import (ALERT_AFTER, RATE_LIMIT, WatchdogState, decide)

NOW = datetime(2026, 10, 9, 3, 2, tzinfo=timezone.utc)
AVAILABLE = WatchdogState()


def failing(n, since_minutes=10, alerted_minutes_ago=None):
    """State representing `n` consecutive failures, optionally already alerted."""
    return WatchdogState(
        consecutive_failures=n,
        first_failure_at=NOW - timedelta(minutes=since_minutes),
        last_alert_at=None if alerted_minutes_ago is None
        else NOW - timedelta(minutes=alerted_minutes_ago),
        last_state="unavailable",
    )


# ----------------------------------------------------------------- the decision table

def test_serving_is_quiet_and_resets_the_counters():
    d = decide(serving=True, process_alive=True, state=failing(5), now=NOW)
    assert d.action == "quiet"
    assert d.state.consecutive_failures == 0
    assert d.state.first_failure_at is None
    assert d.state.last_state == "available"


def test_recovery_is_recorded_but_is_not_itself_an_alert():
    """Coming back up is good news; good news must not use the alert channel."""
    d = decide(serving=True, process_alive=True, state=failing(9, alerted_minutes_ago=30), now=NOW)
    assert d.action == "quiet"
    assert d.message, "recovery should still say something for the log"


def test_nothing_running_at_all_is_the_cold_start_case_not_an_alert():
    """The existing local.ibc-gateway agent owns cold start. The watchdog must be able to tell that
    case apart from a wedged Gateway, and must stay silent about it."""
    d = decide(serving=False, process_alive=False, state=failing(ALERT_AFTER + 3), now=NOW)
    assert d.action == "start"
    assert d.action != "alert"


# ----------------------------------------------------------------- debounce (false-alarm guard)

def test_a_single_failed_probe_does_not_alert():
    """A 45-second automatic re-login must pass unremarked, or this alarms ~30 times a month."""
    d = decide(serving=False, process_alive=True, state=AVAILABLE, now=NOW)
    assert d.action == "quiet"
    assert d.state.consecutive_failures == 1
    assert d.state.first_failure_at is not None, "the outage clock must start on the first miss"


def test_two_consecutive_failures_alert():
    d = decide(serving=False, process_alive=True, state=failing(ALERT_AFTER - 1), now=NOW)
    assert d.action == "alert"
    assert d.state.last_alert_at == NOW


def test_the_alert_message_names_the_outage_duration():
    """An alert has to be actionable without opening a log."""
    d = decide(serving=False, process_alive=True,
               state=failing(ALERT_AFTER - 1, since_minutes=37), now=NOW)
    assert d.action == "alert"
    assert "37" in d.message or "0:37" in d.message


# ----------------------------------------------------------------- rate limit

def test_a_continuing_outage_does_not_re_alert_immediately():
    """25 days at one probe per 5 minutes is ~7200 probes. It must not be ~7200 alerts."""
    d = decide(serving=False, process_alive=True,
               state=failing(50, alerted_minutes_ago=5), now=NOW)
    assert d.action == "quiet"
    assert d.state.last_alert_at == failing(50, alerted_minutes_ago=5).last_alert_at


def test_a_continuing_outage_re_alerts_once_the_rate_limit_expires():
    d = decide(serving=False, process_alive=True,
               state=failing(50, alerted_minutes_ago=RATE_LIMIT // 60 + 1), now=NOW)
    assert d.action == "alert"
    assert d.state.last_alert_at == NOW


# ----------------------------------------------------------------- safety invariants

def test_no_input_ever_produces_a_kill_or_restart_action():
    """Operator decision, 2026-10-09: alert-only. The watchdog never kills a live Gateway, never
    restarts one, and never attempts a login — a second instance would trigger a duplicate login
    that silently cuts market data to the API for every symbol, and a hard kill left the session
    registered server-side for a measured 3h42m."""
    seen = set()
    for serving in (True, False):
        for alive in (True, False):
            for n in (0, 1, ALERT_AFTER, 99):
                for alerted in (None, 0, 5, 10_000):
                    seen.add(decide(serving, alive, failing(n, alerted_minutes_ago=alerted), NOW).action)
    assert seen <= {"quiet", "alert", "start"}, f"unexpected action: {seen}"


def test_decide_is_pure():
    state = failing(ALERT_AFTER)
    first = decide(False, True, state, NOW)
    second = decide(False, True, state, NOW)
    assert first == second
    assert state.consecutive_failures == ALERT_AFTER, "input state must not be mutated"


def test_a_fresh_state_is_assumed_when_none_is_known():
    """A missing or corrupt state file must not crash the watchdog or suppress alerting."""
    d = decide(serving=False, process_alive=True, state=WatchdogState(), now=NOW)
    assert d.action == "quiet"
    assert d.state.consecutive_failures == 1
