"""Is each scheduled job still running? Detected from whether its output post-dates the last time
the job was due to fire.

On 2026-08-01 the monthly rebalance did not fire — the repo had moved and the launchd plists pointed
at the old path — and nobody noticed for two weeks. Every signal was passive: launchd.err is written
only on failure and is git-ignored, `launchctl list` reported exit 0 throughout, and a missing
track.log entry looks exactly like a quiet month.

So detection here does not read logs or ask launchd. It asks whether the job's OUTPUT is newer than
the last scheduled fire time — the one signal that survives a job that never ran at all.

Age alone is not enough, and that distinction is the whole design. A monthly artifact is legitimately
up to 31 days old, so an age threshold cannot flag a missed run until an entire extra cycle has
elapsed — three weeks of silence for a job that failed on day one. Comparing against the *schedule*
catches it within the grace period instead.

Grace is sized against real noise — a sleeping machine, a holiday, the gap between the job's schedule
and this check's — because a false alarm teaches the operator to ignore the channel, which recreates
the failure this exists to prevent.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

DAILY, MONTHLY, QUARTERLY = "daily", "monthly", "quarterly"
QUARTER_MONTHS = (1, 4, 7, 10)


class Job(NamedTuple):
    name: str
    artifact: str        # repo-relative path the job writes
    kind: str            # DAILY | MONTHLY | QUARTERLY
    hour: int            # local time the job is scheduled for
    minute: int
    grace_days: float    # allowance after the due time before calling it overdue
    description: str


WATCHED = [
    Job("nav-snapshot", "nav.csv", DAILY, 21, 0, 1.5,
        "daily NAV snapshot (21:00) — needs the Gateway, so it fails first when anything is wrong"),
    Job("paper-rebalance", "track.log", MONTHLY, 9, 0, 3.0,
        "monthly FX rebalance (1st, 09:00)"),
    Job("basket-rebalance", "basket_positions.csv", QUARTERLY, 9, 30, 5.0,
        "quarterly ETF basket rebalance (1st Jan/Apr/Jul/Oct, 09:30)"),
]


class JobResult(NamedTuple):
    job: Job
    due: datetime            # the last time this job was scheduled to run
    written: datetime | None # when its artifact was last written; None if never
    ok: bool

    @property
    def age_days(self):
        return None if self.written is None else (self.due - self.written).total_seconds() / 86400.0


class HealthReport(NamedTuple):
    results: list
    healthy: bool
    overdue: list            # the Jobs that are overdue


def last_due(job, now) -> datetime:
    """The most recent moment `job` was scheduled to fire, at or before `now`."""
    at = {"hour": job.hour, "minute": job.minute, "second": 0, "microsecond": 0}
    if job.kind == DAILY:
        today = now.replace(**at)
        return today if today <= now else today - timedelta(days=1)
    if job.kind == MONTHLY:
        this = now.replace(day=1, **at)
        if this <= now:
            return this
        prev = this - timedelta(days=1)
        return prev.replace(day=1, **at)
    if job.kind == QUARTERLY:
        candidate = now.replace(day=1, **at)
        for _ in range(13):
            if candidate.month in QUARTER_MONTHS and candidate <= now:
                return candidate
            candidate = (candidate.replace(day=1) - timedelta(days=1)).replace(day=1, **at)
    raise ValueError(f"unknown schedule kind {job.kind!r} for {job.name}")


def check_health(now, root=Path(".")) -> HealthReport:
    """Check every watched artifact against its schedule. Read-only; `now` is injected so this is
    testable without waiting for real time to pass."""
    root = Path(root)
    results = []
    for job in WATCHED:
        # The most recent fire time that is ALSO older than grace. Comparing against the very latest
        # fire time would mean a job dead for weeks looks fine whenever the check happens to run
        # shortly after one — grace would reset on every cycle.
        deadline = now - timedelta(days=job.grace_days)
        due = last_due(job, deadline)
        path = root / job.artifact
        written = (datetime.fromtimestamp(path.stat().st_mtime, tz=now.tzinfo)
                   if path.exists() else None)
        results.append(JobResult(job, due, written, written is not None and written >= due))
    overdue = [r.job for r in results if not r.ok]
    return HealthReport(results=results, healthy=not overdue, overdue=overdue)


def format_report(report) -> str:
    """One line per job, worst first — the text the notification and status file share."""
    lines = []
    for r in sorted(report.results, key=lambda r: (r.ok, r.job.name)):
        when = "never written" if r.written is None else r.written.strftime("%Y-%m-%d %H:%M")
        lines.append(f"  {'ok ' if r.ok else 'OVERDUE':7s} {r.job.name:18s} "
                     f"last output {when:>16s}   due {r.due.strftime('%Y-%m-%d %H:%M')}   "
                     f"{r.job.artifact}")
    return "\n".join(lines)


def overdue_summary(report) -> str:
    """Short text naming what is wrong — for a notification, which has little room."""
    if report.healthy:
        return "all scheduled jobs are current"
    parts = []
    for r in report.results:
        if not r.ok:
            late = "never run" if r.written is None else f"{r.age_days:.0f}d late"
            parts.append(f"{r.job.name} ({late})")
    return "overdue: " + ", ".join(parts)


def notification_command(title, message):
    """The `osascript` argv for a Notification Centre banner.

    AppleScript string literals must be DOUBLE quoted — single quotes are a syntax error, so building
    this with Python's repr() silently produces a command that never fires. json.dumps gives correctly
    double-quoted, escaped literals.

    NOTE: a banner is delivered under Script Editor's notification permission. If that is not granted
    the banner is dropped while osascript still exits 0 — verified on this machine 2026-08-16, where
    nothing appeared. Treat banners as a bonus, never as the alert. Use `alert_command`.
    """
    return ["osascript", "-e",
            f"display notification {json.dumps(str(message))} with title {json.dumps(str(title))}"]


def alert_command(title, message, timeout_seconds=120):
    """The `osascript` argv for a MODAL alert — the channel that actually gets through.

    Unlike a banner this is an app window, so Notification Centre permissions cannot suppress it.
    `giving up after` bounds it so an unattended machine dismisses it instead of blocking the
    scheduled job forever.
    """
    return ["osascript", "-e",
            f"display alert {json.dumps(str(title))} message {json.dumps(str(message))} "
            f"giving up after {int(timeout_seconds)}"]
