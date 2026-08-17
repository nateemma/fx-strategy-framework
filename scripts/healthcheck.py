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

from forex.run.health import (alert_command, check_health, format_report,
                              notification_command, overdue_summary)

STATUS_FILE = Path("health_status.txt")


def notify(title, message):
    """Alert the operator. Best-effort: a headless or restricted context must still get the status
    file and the exit code (FR-008).

    The modal alert is the channel that works. Notification Centre banners are delivered under Script
    Editor's permission and were silently dropped on this machine, so the banner is fired only as a
    bonus and its failure is ignored.
    """
    try:
        subprocess.run(notification_command(title, message), capture_output=True, timeout=10)
    except Exception:                             # noqa: BLE001 - the banner is never the alert
        pass
    try:
        subprocess.run(alert_command(title, message), check=True,
                       capture_output=True, timeout=180)
        return True
    except Exception as exc:                      # noqa: BLE001 - alerting is never fatal
        print(f"  (alert unavailable: {type(exc).__name__})", file=sys.stderr)
        return False


if "--self-test" in sys.argv:
    # Prove the alert channel still works without waiting for a real failure. Worth having: the
    # banner channel was found broken only because it was tested deliberately.
    ok = notify("FX track: healthcheck self-test", "Alerting works. Safe to dismiss.")
    print("alert delivered" if ok else "ALERT CHANNEL BROKEN — fix before relying on it")
    sys.exit(0 if ok else 1)

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
