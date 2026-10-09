---
name: gateway-sunday-reauth
description: IBKR forces a full Gateway re-authentication weekly on Sundays; the soft autorestart token cannot satisfy it and IBC sits on the dialog forever unless ColdRestartTime is set
metadata:
  node_type: memory
  type: project
---

Both Gateway outages began on a **Sunday** — 2026-09-06 (~13h) and 2026-09-13 (**25 days**). That is
the tell: IBKR requires a full shutdown and fresh logon once a week, and nothing in the configuration
satisfied it.

**The mechanism**, stated outright by the Gateway's own log:

```
autorestart file found at ~/Jts/<session-id>/autorestart: authentication will not be required
autorestart file not found: full authentication will be required
```

One day's log showed 14 token-based restarts against 2 full-auth demands. `AutoRestartTime=03:00`
performs only the *soft* token-based restart. When the token is gone IBKR demands credentials —
*"The security tokens associated with your login credentials have expired (routinely) in accordance
with our security protocols"* — and **IBC 3.24.1 sits on that dialog indefinitely**, even with
`IbLoginId`/`IbPassword` stored. It sat for 25 days.

**The fix**: `ColdRestartTime` in `~/ibc/config.ini`, which was **blank**. IBC's own config file
documents it as the handler for IBKR's Sunday full-shutdown requirement — it closes the Gateway and
initiates a full logon from stored credentials. Set to `04:30` on 2026-10-09 (04:30 PT = 07:30 ET
year-round, since PT is always ET−3; clear of `AutoRestartTime=03:00` and all scheduled jobs). Backup
at `~/ibc/config.ini.bak-20261009`.

**Not yet verified** — it is exercised only on a Sunday. The plausible remaining failure is 2FA:
`SecondFactorDevice` is blank and `--on2fatimeout=exit` is on IBC's command line. Counter-evidence
that it may be fine: on 2026-10-08 21:53 IBC auto-handled a "Re-login is required" dialog through to
"Login has completed" in ~45s with no human.

**Why:** two supervisor fixes (2026-08-27, then spec `008`) both addressed *detecting* or *restarting
after* this failure without ever addressing its cause, because the cause looked like random
instability. It is a scheduled, documented, weekly IBKR policy. The Sunday correlation was visible in
the dates the whole time.

**How to apply:** `~/ibc/config.ini` is outside the repo and unversioned, so config state like this
has to be recorded here or it is lost. When the Gateway misbehaves, check the day of week before
assuming instability. See [[launchd-schedule-state]] and [[paper-track-live-state]].
