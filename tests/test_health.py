import os
from datetime import datetime, timedelta, timezone

import pytest

from forex.run.health import (DAILY, MONTHLY, QUARTERLY, WATCHED, check_health,
                              alert_command, last_due, notification_command,
                              overdue_summary)


def artifact(root, name, age_days, now):
    """Create `name` under root with a modification time `age_days` before `now`."""
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")
    stamp = (now - timedelta(days=age_days)).timestamp()
    os.utime(p, (stamp, stamp))
    return p


def fresh_repo(root, now, ages=None):
    """Every watched artifact present and comfortably within its cadence."""
    ages = ages or {}
    for job in WATCHED:
        artifact(root, job.artifact, ages.get(job.name, 0.0), now)
    return root


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- Phase 2: the table

def test_every_scheduled_job_is_watched():
    names = {j.name for j in WATCHED}
    assert {"paper-rebalance", "basket-rebalance", "nav-snapshot"} <= names


def test_every_watched_job_has_a_schedule_and_a_grace():
    for job in WATCHED:
        assert job.kind in (DAILY, MONTHLY, QUARTERLY), f"{job.name} has no known schedule"
        assert job.grace_days > 0, f"{job.name} has no grace"
        assert job.artifact, f"{job.name} has no artifact"
        assert 0 <= job.hour < 24 and 0 <= job.minute < 60


def test_grace_never_swallows_a_whole_cycle_where_one_miss_matters():
    """For monthly and quarterly jobs a single missed run is the failure, so grace must be well
    inside one cycle. The daily snapshot is deliberately more tolerant — the docs record that one
    missed day just leaves a harmless gap in the curve, so its alert means two consecutive misses,
    which is what a dead Gateway looks like."""
    shortest = {MONTHLY: 28.0, QUARTERLY: 90.0}
    for job in WATCHED:
        if job.kind in shortest:
            assert job.grace_days < shortest[job.kind] / 4, f"{job.name} grace is too generous"
    daily = [j for j in WATCHED if j.kind == DAILY]
    assert all(1.0 < j.grace_days < 3.0 for j in daily), "daily grace should tolerate one miss, not three"


# ---------------------------------------------------------------- Phase 3 (US1): detection

def test_a_fresh_repo_is_healthy(tmp_path):
    report = check_health(NOW, fresh_repo(tmp_path, NOW))
    assert report.healthy
    assert report.overdue == []


def test_an_artifact_older_than_the_last_due_time_is_overdue(tmp_path):
    fresh_repo(tmp_path, NOW)
    artifact(tmp_path, "nav.csv", 5.0, NOW)
    report = check_health(NOW, tmp_path)
    assert not report.healthy
    assert [j.name for j in report.overdue] == ["nav-snapshot"]


def test_a_job_still_inside_its_grace_window_is_not_flagged(tmp_path):
    """Scheduled hours ago and not yet run is normal, not a failure."""
    fresh_repo(tmp_path, NOW)
    nav = next(j for j in WATCHED if j.name == "nav-snapshot")
    due = last_due(nav, NOW)
    just_after = due + timedelta(hours=1)
    artifact(tmp_path, "nav.csv", 2.0, just_after)     # predates the due time...
    assert check_health(just_after, tmp_path).healthy  # ...but grace has not elapsed


def test_a_missing_artifact_is_overdue_not_skipped(tmp_path):
    fresh_repo(tmp_path, NOW)
    (tmp_path / next(j for j in WATCHED if j.name == "nav-snapshot").artifact).unlink()
    report = check_health(NOW, tmp_path)
    assert not report.healthy
    assert any(j.name == "nav-snapshot" for j in report.overdue)


def test_a_never_written_artifact_reports_no_write_time(tmp_path):
    fresh_repo(tmp_path, NOW)
    (tmp_path / "nav.csv").unlink()
    result = next(r for r in check_health(NOW, tmp_path).results if r.job.name == "nav-snapshot")
    assert result.written is None
    assert result.age_days is None
    assert not result.ok


def test_all_overdue_jobs_are_reported_together(tmp_path):
    for job in WATCHED:
        artifact(tmp_path, job.artifact, 400.0, NOW)
    report = check_health(NOW, tmp_path)
    assert len(report.overdue) == sum(1 for j in WATCHED if j.enabled)


def test_the_report_states_how_late_each_job_is(tmp_path):
    fresh_repo(tmp_path, NOW)
    artifact(tmp_path, "nav.csv", 10.0, NOW)
    result = next(r for r in check_health(NOW, tmp_path).results if r.job.name == "nav-snapshot")
    assert result.age_days > 8.0     # written well before the last due time


def test_a_monthly_job_that_ran_on_schedule_is_not_flagged(tmp_path):
    """Mid-month, 14 days after a successful 1st-of-month run: normal."""
    fresh_repo(tmp_path, NOW)
    artifact(tmp_path, "track.log", 14.0, NOW)     # NOW is the 15th, so this is the 1st
    assert check_health(NOW, tmp_path).healthy


def test_a_quarterly_job_that_ran_last_quarter_is_not_flagged(tmp_path):
    """2026-09-15: the last quarterly fire was 2026-07-01, so a July artifact is current."""
    fresh_repo(tmp_path, NOW)
    artifact(tmp_path, "basket_positions.csv", 70.0, NOW)
    assert check_health(NOW, tmp_path).healthy


def test_a_quarterly_job_that_missed_its_fire_is_flagged(tmp_path):
    fresh_repo(tmp_path, NOW)
    artifact(tmp_path, "basket_positions.csv", 170.0, NOW)   # predates 2026-07-01
    assert not check_health(NOW, tmp_path).healthy


def test_the_august_failure_would_have_been_caught(tmp_path):
    """The real event: 2026-08-01 rebalance missed, track.log last written 2026-07-17.

    Age-based detection would not flag this for three more weeks, because 19 days is a normal age
    for a monthly artifact. Schedule-based detection flags it once grace elapses.
    """
    aug5 = datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc)
    fresh_repo(tmp_path, aug5)
    artifact(tmp_path, "track.log", 19.0, aug5)      # 2026-07-17, predating the 2026-08-01 fire
    report = check_health(aug5, tmp_path)
    assert not report.healthy
    assert any(j.name == "paper-rebalance" for j in report.overdue)


def test_that_same_failure_is_not_flagged_before_grace_elapses(tmp_path):
    """On the 1st itself, hours after the job was due, grace has not run out yet."""
    aug1 = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    fresh_repo(tmp_path, aug1)
    artifact(tmp_path, "track.log", 15.0, aug1)
    assert check_health(aug1, tmp_path).healthy


def test_the_check_does_not_modify_what_it_inspects(tmp_path):
    fresh_repo(tmp_path, NOW)
    before = {p.name: (p.stat().st_mtime, p.read_bytes())
              for p in tmp_path.iterdir() if p.is_file()}
    check_health(NOW, tmp_path)
    after = {p.name: (p.stat().st_mtime, p.read_bytes())
             for p in tmp_path.iterdir() if p.is_file()}
    assert before == after


# ---------------------------------------------------------------- Phase 4 (US2): notification

def test_notification_uses_applescript_double_quotes():
    """AppleScript rejects single-quoted strings, so a repr()-built command never fires."""
    script = notification_command("FX track", "overdue: nav-snapshot")[-1]
    assert '"overdue: nav-snapshot"' in script
    assert '"FX track"' in script
    assert "'" not in script


def test_notification_escapes_quotes_in_the_message():
    script = notification_command('a "quoted" title', 'say "hello"')[-1]
    assert '\\"hello\\"' in script or '\\"quoted\\"' in script


def test_notification_is_actually_runnable(tmp_path):
    """Build it and let osascript parse it — the bug this guards was a syntax error, not a typo."""
    import shutil
    import subprocess
    if not shutil.which("osascript"):
        pytest.skip("osascript unavailable")
    cmd = notification_command("healthcheck test", "self-test, safe to ignore")
    assert subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0


def test_summary_names_every_overdue_job(tmp_path):
    for job in WATCHED:
        artifact(tmp_path, job.artifact, 400.0, NOW)
    text = overdue_summary(check_health(NOW, tmp_path))
    for job in WATCHED:
        if job.enabled:
            assert job.name in text


def test_summary_of_a_healthy_report_says_so(tmp_path):
    assert "current" in overdue_summary(check_health(NOW, fresh_repo(tmp_path, NOW)))


def test_alert_command_uses_double_quotes_and_a_timeout():
    """The modal is the channel that actually reaches the operator, so its quoting matters most."""
    script = alert_command("FX track", "overdue: nav-snapshot", 90)[-1]
    assert '"overdue: nav-snapshot"' in script
    assert '"FX track"' in script
    assert "giving up after 90" in script
    assert "'" not in script


def test_alert_command_always_bounds_itself():
    """Without a timeout an unattended machine would block the scheduled job indefinitely."""
    assert "giving up after" in alert_command("t", "m")[-1]


# ---------------------------------------------------------------- dormant jobs must not alarm

def test_a_disabled_job_is_never_reported_overdue(tmp_path):
    """A sleeve that is built but not yet deployed has no artifact and never will until it runs.
    Alarming on it nightly would train the operator to ignore the channel."""
    fresh_repo(tmp_path, NOW)
    dormant = [j for j in WATCHED if not j.enabled]
    assert dormant, "expected at least one registered-but-dormant job"
    for job in dormant:
        (tmp_path / job.artifact).unlink(missing_ok=True)
    report = check_health(NOW, tmp_path)
    assert report.healthy
    assert not any(j.name in {d.name for d in dormant} for j in report.overdue)


def test_disabled_jobs_do_not_appear_in_the_report_at_all(tmp_path):
    fresh_repo(tmp_path, NOW)
    names = {r.job.name for r in check_health(NOW, tmp_path).results}
    for job in WATCHED:
        if not job.enabled:
            assert job.name not in names


def test_enabled_jobs_are_still_checked(tmp_path):
    """The dormancy escape hatch must not accidentally silence everything."""
    fresh_repo(tmp_path, NOW)
    artifact(tmp_path, "nav.csv", 10.0, NOW)
    assert not check_health(NOW, tmp_path).healthy
