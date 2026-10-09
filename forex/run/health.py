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

THE WATCHED ARTIFACT MUST BE A FILE THAT ONLY A SUCCESSFUL RUN WRITES. This is the rule that was
missing, and it cost 25 days. `paper-rebalance` used to watch `track.log` — the monthly runner's
catch-all log, written as `{ ... } >> track.log 2>&1`, which captures tracebacks as readily as
output. So on 2026-10-01 the rebalance fired, could not reach the Gateway, placed nothing, and its
own traceback refreshed the mtime that was serving as its proof of life. It was reported `ok`.

The other six jobs were safe only by accident: `nav.csv` and the `*_positions.csv` files happen to
be appended after a successful broker round-trip. Accident is not a guarantee, so every Job now
carries `success_evidence` — a sentence naming the mechanism that makes its artifact success-only.
A boolean flag would have documented nothing; the point is that the honest sentence for `track.log`
cannot be written without noticing the bug.

Reachability is reported ALONGSIDE the per-job verdicts and never overrides them: a reachable broker
does not excuse a stale job, and an unreachable one does not by itself mark any job failed — it
explains them. "unknown" is a distinct, non-failing outcome, so that a missing or broken probe
cannot manufacture an outage.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

DAILY, MONTHLY, QUARTERLY = "daily", "monthly", "quarterly"
QUARTER_MONTHS = (1, 4, 7, 10)


class Job(NamedTuple):
    name: str
    artifact: str        # repo-relative path the job writes ON SUCCESS ONLY — see success_evidence
    kind: str            # DAILY | MONTHLY | QUARTERLY
    hour: int            # local time the job is scheduled for
    minute: int
    grace_days: float    # allowance after the due time before calling it overdue
    description: str
    success_evidence: str  # why a FAILING run cannot write `artifact`. Required, asserted by a test.
    enabled: bool = True  # a job that cannot run yet must not alarm — see WATCHED


WATCHED = [
    Job("nav-snapshot", "nav.csv", DAILY, 21, 0, 1.5,
        "daily NAV snapshot (21:00) — needs the Gateway, so it fails first when anything is wrong",
        "snapshot_nav.py appends the row only after the account round-trip returns; a refused "
        "connection raises before the write"),
    # NOT track.log: that is the runner's catch-all log and a traceback refreshes it. See the
    # module docstring — this exact swap is the fix for the 2026-10-01 false `ok`.
    Job("paper-rebalance", "fx_rebalance_status.csv", MONTHLY, 9, 0, 3.0,
        "monthly FX rebalance (1st, 09:00)",
        "monthly_paper_rebalance.sh appends the marker after its `set -euo pipefail` block closes, "
        "so a failed `forex dryrun --confirm` aborts the script before it is reached"),
    # All four ETF sleeves run from one quarterly job, but each writes its own CSV — so a single
    # sleeve failing mid-run is visible, rather than being masked by the others succeeding.
    Job("basket-rebalance", "basket_positions.csv", QUARTERLY, 9, 30, 5.0,
        "quarterly ETF basket sleeve (1st Jan/Apr/Jul/Oct, 09:30)",
        "basket_rebalance.py writes the position snapshot only after BasketExecution returns a "
        "completed reconcile; a connect failure raises first"),
    Job("ladder-rebalance", "bond_ladder_positions.csv", QUARTERLY, 9, 30, 5.0,
        "quarterly Treasury ladder sleeve",
        "bond_ladder.py writes the snapshot only after a completed reconcile"),
    Job("income-rebalance", "income_sleeve_positions.csv", QUARTERLY, 9, 30, 5.0,
        "quarterly BDC/covered-call income sleeve",
        "income_sleeve.py writes the snapshot only after a completed reconcile"),
    Job("cash-rebalance", "cash_positions.csv", QUARTERLY, 9, 30, 5.0,
        "quarterly SGOV cash sleeve",
        "cash_sleeve.py writes the snapshot only after a completed reconcile"),
    # Registered but DORMANT: the sleeve is built and tested but cannot run until a CME/CBOT/NYMEX
    # market-data subscription exists (docs/lean-data-gate.md). Watching it now would fire a nightly
    # alarm for something that is correctly not running — and a false alarm teaches the operator to
    # ignore the channel, which is the exact failure this whole feature exists to prevent.
    # Flip to enabled=True when the sleeve is first deployed.
    Job("vix-carry", "vix_carry_positions.csv", DAILY, 8, 30, 2.5,
        "daily VIX carry satellite (SVXY, contango-gated)",
        "vix_carry_sleeve.py writes the snapshot only after a completed reconcile; the refused "
        "connections of 2026-09-13..10-08 left it untouched, which is why this job reported OVERDUE "
        "correctly while paper-rebalance did not"),
    Job("trend-sleeve", "trend_positions.csv", MONTHLY, 10, 0, 3.0,
        "monthly cross-asset trend sleeve (futures) — not yet deployed",
        "the runner will write the snapshot only after a completed reconcile", enabled=False),
]


class JobResult(NamedTuple):
    job: Job
    due: datetime            # the last time this job was scheduled to run
    written: datetime | None # when its artifact was last written; None if never
    ok: bool

    @property
    def age_days(self):
        return None if self.written is None else (self.due - self.written).total_seconds() / 86400.0


AVAILABLE, UNAVAILABLE, UNKNOWN = "available", "unavailable", "unknown"


class HealthReport(NamedTuple):
    results: list
    healthy: bool
    overdue: list            # the Jobs that are overdue
    reachability: str = UNKNOWN   # available | unavailable | unknown — see the module docstring


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


def check_health(now, root=Path("."), probe=None) -> HealthReport:
    """Check every watched artifact against its schedule. Read-only; `now` is injected so this is
    testable without waiting for real time to pass.

    `probe` is an optional zero-argument callable returning True when the broker API is serving. It
    is injected rather than called directly so the suite stays offline (Constitution III). Omitting
    it — or a probe that raises — yields UNKNOWN, which is deliberately NOT a failure: a monitoring
    channel that invents outages when its own probe is broken is worse than one that admits it did
    not look. Reachability never affects any job verdict; it only explains them.
    """
    root = Path(root)
    reachability = UNKNOWN
    if probe is not None:
        try:
            reachability = AVAILABLE if probe() else UNAVAILABLE
        except Exception:        # noqa: BLE001 - a probe bug must not manufacture an outage
            reachability = UNKNOWN
    results = []
    for job in WATCHED:
        if not job.enabled:      # registered but not yet deployed: never alarm
            continue
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
    return HealthReport(results=results, healthy=not overdue, overdue=overdue,
                        reachability=reachability)


BROKER_LINE = {
    AVAILABLE: "broker API: available",
    UNAVAILABLE: ("broker API: UNAVAILABLE — every job that needs the Gateway will fail until it is "
                  "logged in"),
    UNKNOWN: "broker API: not checked",
}


def format_report(report) -> str:
    """One line per job, worst first — the text the notification and status file share.

    The broker line goes FIRST because during an outage it is the cause and every job line below it
    is a symptom. The per-job format is deliberately unchanged: the operator reads this file at a
    glance and already knows that shape.
    """
    lines = [BROKER_LINE[report.reachability]]
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
