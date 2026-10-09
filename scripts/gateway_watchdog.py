"""Is the IB Gateway API actually serving? The I/O half; the rules live in forex/run/gateway_watchdog.

    .venv/bin/python scripts/gateway_watchdog.py
    .venv/bin/python scripts/gateway_watchdog.py --self-test

Runs every 300s from launchd (local.fx-gateway-watchdog). Read-only with respect to the broker: it
opens a TCP connection and closes it without sending an API handshake, so it cannot register a
session. That matters — error 10197 ("competing live session") silently cuts market data to the API
for every symbol and has already caused one wrong diagnosis in this project. 10197 comes from a
duplicate IBKR *account* login, not from attaching to a local port, and a connect-and-close is
strictly weaker than the API clients the sleeves already open routinely.

It never kills, restarts, or logs into anything — see the module docstring in
forex/run/gateway_watchdog.py for why that is a decision rather than an omission.

Exit codes: 0 when serving or deliberately quiet, 1 when it alerted or crashed. A broker that is
down but still inside the debounce window exits 0, so launchd's error log stays meaningful.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from forex.run.gateway_watchdog import (WatchdogState, decide, port_is_serving)
from forex.run.health import alert_command, notification_command

STATUS_FILE = Path("gateway_status.txt")
STATE_FILE = Path("gateway_watchdog_state.json")
PORT = int(os.environ.get("IB_PORT", "4002"))
# The Gateway's own java process runs ibcalpha.ibc.IbcGateway; this matches it without matching the
# IBC shell wrapper, which can outlive a logged-out Gateway.
PROCESS_PATTERN = "ibcalpha.ibc"


def gateway_process_alive(pattern=PROCESS_PATTERN) -> bool:
    try:
        return subprocess.run(["pgrep", "-f", pattern],
                              capture_output=True, timeout=10).returncode == 0
    except Exception:                     # noqa: BLE001 - an unknown process table means "assume
        return True                       # alive", which is the branch that CAN alert rather than
                                          # the silent one. Never fail safe into silence.


def load_state(path=STATE_FILE) -> WatchdogState:
    """A missing or corrupt state file is a fresh start, never an error. A watchdog that crashes on
    its own state file would be silent for exactly as long as the outage it exists to report."""
    try:
        raw = json.loads(path.read_text())
        parse = lambda k: datetime.fromisoformat(raw[k]) if raw.get(k) else None   # noqa: E731
        return WatchdogState(int(raw.get("consecutive_failures", 0)),
                             parse("first_failure_at"), parse("last_alert_at"),
                             raw.get("last_state", "available"))
    except Exception:                     # noqa: BLE001 - see docstring
        return WatchdogState()


def save_state(state, path=STATE_FILE):
    path.write_text(json.dumps({
        "consecutive_failures": state.consecutive_failures,
        "first_failure_at": state.first_failure_at.isoformat() if state.first_failure_at else None,
        "last_alert_at": state.last_alert_at.isoformat() if state.last_alert_at else None,
        "last_state": state.last_state,
    }, indent=2) + "\n")


def notify(title, message):
    """Modal alert is the channel that works here; the banner is a bonus whose failure is ignored.
    On this machine banners were silently dropped while osascript still exited 0."""
    try:
        subprocess.run(notification_command(title, message), capture_output=True, timeout=10)
    except Exception:                     # noqa: BLE001 - the banner is never the alert
        pass
    try:
        subprocess.run(alert_command(title, message), check=True, capture_output=True, timeout=180)
        return True
    except Exception as exc:              # noqa: BLE001 - alerting is never fatal
        print(f"  (alert unavailable: {type(exc).__name__})", file=sys.stderr)
        return False


def main() -> int:
    now = datetime.now().astimezone()

    if "--self-test" in sys.argv:
        ok = notify("FX track: gateway watchdog self-test", "Alerting works. Safe to dismiss.")
        print("alert delivered" if ok else "ALERT CHANNEL BROKEN — fix before relying on it")
        return 0 if ok else 1

    serving = port_is_serving(PORT)
    # Only asked when the port is down: pgrep on every healthy tick would be pure noise.
    alive = True if serving else gateway_process_alive()
    decision = decide(serving, alive, load_state(), now)
    save_state(decision.state)

    stamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    verdict = "SERVING" if serving else "NOT SERVING"
    # Written on EVERY run, so this file's own mtime proves the watchdog is still being scheduled —
    # a watchdog starved the way the old supervisor was would otherwise look identical to a healthy
    # one. See quickstart.md step 7.
    STATUS_FILE.write_text(f"IB Gateway API port {PORT} — {verdict}  ({stamp})\n"
                           f"{decision.message}\n")
    print(f"port {PORT} {verdict} — {decision.message}")

    if decision.action == "alert":
        notify("FX track: IB Gateway not serving", decision.message)
        print(decision.message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:              # noqa: BLE001 - a crashing watchdog must not be silent
        try:
            STATUS_FILE.write_text(f"gateway watchdog CRASHED: {type(exc).__name__}: {exc}\n")
        except Exception:                 # noqa: BLE001
            pass
        print(f"gateway watchdog crashed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
