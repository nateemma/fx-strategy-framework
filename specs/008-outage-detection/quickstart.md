# Quickstart: Verifying Truthful Outage Detection

How to prove this works **without waiting for an outage**. That matters here: the last two defects were
both found only after they had already cost something, and the one before that (the dropped notification
banner) was found only because someone deliberately tested the channel.

Prerequisites: repo root, `.venv` present. Steps 1–3 need no broker and no network.

Every command below was run on 2026-10-09; the `-k` selectors are the ones that actually
match the test names, not plausible-looking guesses (two of them did not, and were corrected).

---

## 1. The regression that started it (offline, ~1s)

The original defect, as an executable check.

```bash
.venv/bin/python -m pytest tests/test_health.py -q
```

**Expect**: all tests pass, including the new case that a job whose log was touched by a *failure* is
reported failed. Before this feature that case reported `ok`.

The specific assertion to look for — this is SC-001:

> Given `track.log` newer than the last due time but `fx_rebalance_status.csv` stale,
> `paper-rebalance` is reported **failed**.

---

## 2. The false-alarm guard (offline, ~1s)

The most likely way this feature breaks something is flagging a correct no-op as a failure. Every
execution path here reconciles, so an unchanged target legitimately places zero orders.

```bash
.venv/bin/python -m pytest tests/test_health.py -q -k placed_nothing
```

**Expect**: a run that succeeded while placing nothing is reported `ok`. This is SC-004.

---

## 3. The watchdog decision table (offline, ~1s)

```bash
.venv/bin/python -m pytest tests/test_gateway_watchdog.py -q
```

**Expect**: coverage of each row of the decision table in
[contracts/interfaces.md](./contracts/interfaces.md) §B, including:

- one failed probe does **not** alert (the 45s re-login measured on 2026-10-08 must stay silent);
- two consecutive failures **do** alert;
- a continuing outage alerts at most once per hour (SC-005);
- `serving=False, process_alive=False` yields `start`, never `alert` — proving the watchdog distinguishes
  "nothing running" from "running but wedged";
- no input produces an action that kills or restarts anything.

---

## 4. Reachability rendering, both ways (offline, ~1s)

```bash
.venv/bin/python -m pytest tests/test_health.py -q -k "broker or probe or unknown"
```

**Expect**: three distinct renderings — available, unavailable, and unknown — and in particular that
`unknown` does **not** make the report unhealthy, and that a probe which raises degrades to `unknown`
rather than inventing an outage.

---

## 5. End to end against the live Gateway (needs the Gateway; read-only)

```bash
.venv/bin/python scripts/healthcheck.py; echo "exit=$?"
.venv/bin/python scripts/gateway_watchdog.py; echo "exit=$?"
```

**Expect** with the Gateway serving: the healthcheck's status file carries a broker line reading
`available`; the watchdog exits 0, writes `gateway_status.txt`, and alerts nothing.

Neither command places an order or opens a broker API session — the watchdog's probe is a bare TCP
connect, and the healthcheck's is the same.

---

## 6. Prove the alert channel still works (fires a real alert)

```bash
.venv/bin/python scripts/gateway_watchdog.py --self-test
```

**Expect**: a modal alert appears. If it does not, the alert path is broken and must be fixed before this
feature is relied on — the banner channel on this machine was already found to be silently dropped while
`osascript` still exited 0, so "no alert appeared" is a known-possible state that exits successfully.

---

## 7. Simulate the real outage (needs the Gateway; recommended once)

The honest test of the whole feature. Pick a quiet moment with no scheduled job due.

1. Note the current state: `cat gateway_status.txt`.
2. Stop the Gateway **through its own UI** — a clean logout, not a kill. A hard kill leaves the session
   registered server-side and the next login was measured waiting **3h42m** for release.
3. Run the watchdog twice, a few seconds apart.
   **Expect**: first run quiet (inside the debounce), second run alerts and exits 1.
4. Run it a third time. **Expect**: quiet — rate-limited, not re-alerting.
5. Log back in, run it once more. **Expect**: quiet, state reset to available, recovery recorded.
6. Run `scripts/healthcheck.py`. **Expect**: the broker line reads `available` again.

**Do not** test by killing the process, and do not test while a scheduled job is due.

---

## Installing the watchdog

```bash
bash scripts/install_schedules.sh          # installs the new agent alongside the existing six
launchctl list | grep fx-gateway-watchdog  # expect the label present
```

**Verify the timer actually re-fires** — this is the exact defect being fixed, so confirm it rather than
assuming:

```bash
# wait >5 minutes, then:
ls -l gateway_status.txt     # mtime must advance between checks
```

A `gateway_status.txt` whose mtime stops advancing means the watchdog has been starved the same way the
old supervisor was, and is itself the thing to alarm on.
