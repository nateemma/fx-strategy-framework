"""Are the scheduled jobs still running? Read-only; no broker, no network.

Checks each job's output against the last time it was due to fire, prints a table, raises a desktop
notification when something is overdue, and always writes a durable status file so the result
outlives the notification. Exits non-zero when anything is overdue.

    .venv/bin/python scripts/healthcheck.py

Runs daily from launchd (com.fx.healthcheck) — see scripts/install_schedules.sh.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from forex.run.health import (check_health, format_report, notification_command,
                              overdue_summary)

STATUS_FILE = Path("health_status.txt")


def notify(title, message):
    """Best-effort desktop notification. Never allowed to break the run: a headless or restricted
    context must still get the status file and the exit code (FR-008)."""
    try:
        subprocess.run(notification_command(title, message),
                       check=True, capture_output=True, timeout=10)
        return True
    except Exception as exc:                      # noqa: BLE001 - notification is never fatal
        print(f"  (notification unavailable: {type(exc).__name__})", file=sys.stderr)
        return False


now = datetime.now().astimezone()
report = check_health(now)

stamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
verdict = "HEALTHY" if report.healthy else "OVERDUE"
body = f"scheduled-job healthcheck — {verdict}  ({stamp})\n{format_report(report)}"
print(body)

# Durable first: this must survive whatever the notifier does.
STATUS_FILE.write_text(body + "\n")

if not report.healthy:
    notify("FX track: scheduled job overdue", overdue_summary(report))
    print(f"\n{overdue_summary(report)}", file=sys.stderr)
    sys.exit(1)
