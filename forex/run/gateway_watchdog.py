"""Is the broker API actually serving? The decision half — pure, so the rules can be tested.

WHY THIS EXISTS. On 2026-09-13 IBKR expired the Gateway's auto-restart tokens. IBC's token-based
"Re-starting session" path cannot answer that — it needs a fresh credentialed login — so the Gateway
sat on the login dialog for 25 days. Every scheduled job that needed the broker failed, and nothing
said so.

The supervisor that was supposed to catch it could not, for a reason worth writing down: it
port-checks and then `exec`s IBC, so once IBC is up the launchd job never exits, the StartInterval
timer never re-fires, and the check never runs again. It had not run in 40 days. **Liveness of IBC is
not liveness of port 4002.** That is the whole failure, in one sentence.

So this watchdog does one thing and exits, every time, and its timer therefore cannot be starved.

WHAT IT DELIBERATELY DOES NOT DO (operator decision, 2026-10-09): it never kills a live Gateway,
never restarts one, and never attempts a login. Both automated remedies are known-harmful here — a
second instance triggers a duplicate login that silently cuts market data to the API for EVERY symbol
and looks exactly like a missing subscription, and a hard kill leaves the session registered
server-side, after which the next login was measured waiting 3h42m for release. The root cause needs
a human either way, so the job is to alert fast, not to be clever. Cold-starting IBC when nothing is
running at all remains the existing `local.ibc-gateway` agent's job; that agent's starvation only
occurs while IBC is alive, so it still handles that case correctly and is left untouched.

The debounce is the hard part, and it can be wrong in both directions. Alerting on the first miss
would fire on every nightly restart — and restarts are not even confined to 03:00: an automatic
re-login was observed at 21:52 on 2026-10-08, taking ~45s end to end. A cold start after a hard kill
was measured at 2m06s. Requiring two consecutive misses at a 300s interval puts the alert floor above
both, bounds detection at ~10 minutes, and keeps the channel quiet enough to be believed.
"""
import socket
from datetime import datetime, timedelta
from typing import NamedTuple

ALERT_AFTER = 2        # consecutive failed probes before alerting; >= 5 min of outage at 300s
RATE_LIMIT = 3600      # seconds before re-alerting about the SAME continuing outage
PROBE_TIMEOUT = 2.0    # a local port answers at once or is not serving
PROBE_INTERVAL = 300   # documented here, enforced by the launchd plist's StartInterval

AVAILABLE, UNAVAILABLE = "available", "unavailable"


def port_is_serving(port: int = 4002, timeout: float = PROBE_TIMEOUT) -> bool:
    """The module's ONLY I/O, kept here so the watchdog and the daily healthcheck share one probe
    rather than growing two that can disagree. Never called by the test suite — every test injects a
    stub instead, which is what keeps the suite offline (Constitution III).

    One TCP connect, closed immediately, with NO API handshake. That distinction matters: error 10197
    ("competing live session") silently cuts market data to the API for every symbol and has already
    caused one wrong diagnosis in this project. 10197 comes from a duplicate IBKR *account* login —
    Client Portal, the mobile app, TWS elsewhere — not from attaching to a local port, and a
    connect-and-close is strictly weaker than the API clients the sleeves already open routinely.
    """
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


class WatchdogState(NamedTuple):
    """What the previous run saw. Everything needed to decide is in here, which is what lets the
    debounce and the rate limit be tested without a clock or a sleep."""
    consecutive_failures: int = 0
    first_failure_at: datetime | None = None
    last_alert_at: datetime | None = None
    last_state: str = AVAILABLE


class WatchdogDecision(NamedTuple):
    action: str              # "quiet" | "alert" | "start"
    state: WatchdogState     # to persist
    message: str             # operator-facing; "" only when there is genuinely nothing to say


def _outage_text(first_failure_at, now) -> str:
    if first_failure_at is None:
        return "just now"
    mins = int((now - first_failure_at).total_seconds() // 60)
    if mins < 60:
        return f"{mins} min"
    return f"{mins // 60}h{mins % 60:02d}m"


def decide(serving: bool, process_alive: bool, state: WatchdogState,
           now: datetime) -> WatchdogDecision:
    """Given what the probe saw, decide what to do. Pure: no I/O, no mutation of `state`.

    `process_alive` separates the two failure modes that look identical from the port alone:
    nothing running (cold start — somebody else's job) from running but not serving (the wedged
    login that cost 25 days, and the only case worth waking the operator for).
    """
    if serving:
        recovered = state.last_state == UNAVAILABLE
        msg = (f"broker API recovered after {_outage_text(state.first_failure_at, now)}"
               if recovered else "broker API serving")
        return WatchdogDecision("quiet", WatchdogState(0, None, None, AVAILABLE), msg)

    failures = state.consecutive_failures + 1
    began = state.first_failure_at or now
    pending = state._replace(consecutive_failures=failures, first_failure_at=began,
                             last_state=UNAVAILABLE)

    if not process_alive:
        # Nothing to supervise and nothing wedged. The existing agent will bring it up; alerting here
        # would cry wolf on an ordinary cold start, so this stays deliberately silent.
        return WatchdogDecision("start", pending,
                                "broker not running — leaving cold start to local.ibc-gateway")

    if failures < ALERT_AFTER:
        # Inside the restart window. The 45s re-login and the 2m06s cold start both land here.
        return WatchdogDecision("quiet", pending,
                                f"broker API not serving ({failures}/{ALERT_AFTER} before alerting)")

    throttled = (state.last_alert_at is not None
                 and now - state.last_alert_at < timedelta(seconds=RATE_LIMIT))
    if throttled:
        return WatchdogDecision("quiet", pending,
                                f"broker API still down ({_outage_text(began, now)}); alert throttled")

    return WatchdogDecision(
        "alert", pending._replace(last_alert_at=now),
        f"IB Gateway is running but its API port is not serving — down {_outage_text(began, now)}. "
        f"Log in to the Gateway; scheduled jobs are failing until you do.")
