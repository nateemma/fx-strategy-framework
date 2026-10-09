# Platform & Broker Decision (2026-08-17)

**Decision: IBKR stays as the execution broker. QuantConnect/LEAN was evaluated for research data and
**declined** — the gate found IBKR's own market-data subscription costs ~$5/month and works with
existing code ([`lean-data-gate.md`](./lean-data-gate.md)). No framework migration.**

Recorded because the reasoning is easy to lose and it bears directly on whether the futures trend
sleeve is worth unblocking.

---

## The question

After the financing findings and the futures market-data blocker, IBKR started to look hostile to
what this program does, and funding at the levels the analysis implies looked unrealistic. Are there
better alternatives — QuantConnect, or another broker?

## The premise was backwards

IBKR is the **cheapest retail margin** by a wide margin. Rates as published:

| Broker | Margin rate |
|---|---|
| **IBKR** | **~4.4–5.1%** (BM+0.75% above $1M, BM+1.5% tier 1) |
| Fidelity | 7.50% above $1M; base 10.575% |
| Schwab | ~10.1% at $250–500k debit |
| E*Trade | ~10.45% at $250–500k debit |

The 218bp of financing that destroyed `carry_cot_mom` would be roughly 600bp+ at Schwab or Fidelity.
Investopedia's 2026 low-cost survey names IBKR best for both low margin rates and low-cost futures.

**Switching retail brokers would make the single most damaging constraint worse.**

## Three problems that got conflated

| Problem | Fixable by changing broker? |
|---|---|
| Financing ~218bp on gross exposure | **No.** IBKR is already the cheapest retail. Only futures (embedded leverage) or an institutional relationship change it. |
| Futures market-data subscription for history | **No — and it is not really a broker problem.** Data is obtainable elsewhere. |
| Contract granularity needing a ~$200k risk base | **No.** That is arithmetic about contract sizes, not broker policy. |

Only the middle one has a tooling answer, and that is the whole of what QuantConnect offers here.

## What QuantConnect/LEAN is, and is not

**It is not a broker.** It is research infrastructure — data, backtesting, algorithm hosting — that
connects *to* a broker, IBKR included. LEAN, the engine, is open-source (Apache 2.0) and runs locally.

**Solves:** futures history without an IBKR market-data subscription; unified cross-asset data; and
possibly the roll-adjusted continuous-futures problem that made commodity carry untestable and is the
acknowledged gap in the A2 trend gate.

**Does not solve:** financing, capital requirements, execution economics, or contract granularity.
Trading through LEAN still means a broker charging the same rates.

**Costs:** migrating a working framework into another project's idioms. The `Strategy` contract, the
structural causality enforcement, the financing cost model, and three paper-validated executors are
real assets that a rewrite would put at risk. Exact QC data coverage and pricing could not be verified
from the docs and must be gated before anything is committed.

## The honest reframe: the constraint is capital, not broker

Every dead end this program has hit traces back to running a **diversified, levered** book at retail
scale:

- FX carry needs ~95bp all-in financing → an institutional relationship → capital.
- The trend sleeve needs a ~$200k risk base for contract granularity → capital.
- VIX carry works at any size, but is equity beta rather than diversification, so it does not help.

And the uncomfortable conclusion: **nothing found so far clears a bar that justifies real money at a
realistically fundable level.** The FX book is dead at retail terms. The trend sleeve is unvalidated
on futures data. VIX carry is not the diversifier the book needs. The ETF sleeves work — but they are
ordinary long-only holdings that do not need any of this machinery.

The strategies that genuinely work at low capital are the **unlevered, long-only** ones, which is
exactly why the ETF sleeves were untouched by the financing finding.

## The decision

1. **IBKR stays** as the execution broker. It is the best available on the constraint that matters
   most, and the three executors are paper-validated.
2. **Evaluate QuantConnect/LEAN for research data**, gated the way every other idea in this program
   has been: prove the data exists, at a cost worth paying, before building anything.
3. **No framework migration is committed.** Staged plan with an explicit stop-decision:
   [`lean-migration-plan.md`](./lean-migration-plan.md).
4. **Do not fund real trading on current evidence.** The paper track costs nothing and the research is
   the asset. Revisit if the trend sleeve validates on real futures data, or if financing terms change
   (the number is 95bp all-in — see [`financing-spread-findings.md`](./financing-spread-findings.md)).

## Addendum 2026-10-09: operational stability — the dimension this doc missed

**The decision above still holds, but it was taken without weighing uptime at all.** It predates the
two Gateway outages, so "is IBKR a good platform" was answered on financing, data and capital while
the thing that has actually cost the most — the Gateway staying logged in — went unexamined.

### What happened

| Date | Event | Cost |
|---|---|---|
| 2026-09-06 | Auto-restart tokens expired at 03:00; Gateway sat logged out | ~13h, cleared same day |
| 2026-09-13 → 10-08 | Same failure, nobody noticed | **25 days.** October's monthly FX rebalance and the quarterly sleeve rebalance both fired on time and placed nothing; `nav.csv` lost 25 days, unrecoverably |
| 2026-12-15 | Gateway 10.45 desupported (error 2172 on every connect) | A forced upgrade on a deadline |

### The mechanism, so it is not rediscovered expensively

IBKR's unattended restart depends on a token file at `~/Jts/<session-id>/autorestart`. The Gateway's
own log states the rule outright:

```
autorestart file found at ~/Jts/<id>/autorestart: authentication will not be required
autorestart file not found: full authentication will be required
```

One day's log showed **14 token-based restarts against 2 full-auth demands**. When the token is
present the Gateway restarts silently; when it is absent IBKR demands credentials and the error is
explicit: *"The security tokens associated with your login credentials have expired (routinely) in
accordance with our security protocols. Please manually enter your username and password."* That is
IBKR policy, not a bug, and it is the Sep 13 failure.

So the cadence is structural: **a full authentication is demanded periodically and IBC 3.24.1 did not
recover from it**, even though credentials are stored in `config.ini`. Notably IBC *did* auto-recover
a different dialog — "Re-login is required" on 2026-10-08 21:53, logged through to "Login has
completed" in ~45 seconds — so stored-credential logins work in general. The token-expiry dialog is
the one it sits on.

### The honest split of blame

| Symptom | Cause | Status |
|---|---|---|
| Forced full login every week or two | **IBKR policy.** Not fixable by us | Open — mitigation attempted 2026-10-09, see below |
| 25 days of *silence* about it | **Ours.** The healthcheck asserted on file mtime, which a failure traceback refreshed | **Fixed** 2026-10-09, spec `008` |
| No Gateway supervisor at all until 2026-08-27 | Ours | Fixed, then found insufficient (its timer was starved) — also spec `008` |
| A missed rebalance rather than a late one | Ours. `connect_with_retry` gives up after ~1 minute, which is far too impatient for a monthly job | **Open** — Backlog #23 |

Worth being precise about this, because the two are easy to conflate: IBKR costs a login every week
or two. It cost *five weeks of data* because our own monitoring reported green through the outage.

### Does this change the decision? No — but for a narrower reason than before

The alternatives were re-surveyed on 2026-10-09 against the new evidence:

| Platform | Fixes the uptime problem? | What it costs |
|---|---|---|
| Alpaca | Yes — REST, no gateway, stable unattended | **No FX, no futures.** Deletes the FX book and the trend sleeve outright |
| OANDA / IG | Yes, clean REST, good FX data | Financing and spreads worse than IBKR — kills carry harder than IBKR does |
| tastytrade | Partly — futures, but no multi-currency FX | Financing worse |
| Tradier | Yes | US equities/options only |
| QuantConnect/LEAN | Not a broker; connects *to* one | Already gated and declined above |

**No retail broker combines IBKR's financing, multi-currency FX, futures, and an API.** Every option
with better uptime is strictly narrower, and the narrowing removes the strategies this program exists
to test. The margin table at the top of this doc remains decisive: the 218bp that took `carry_cot_mom`
from Sharpe 1.15 to 0.17 would be 600bp+ at a broker with a nicer API.

So the conclusion is unchanged but the reasoning is now explicitly three-sided: IBKR is the cheapest
retail financing, its data gap is a *vendor* purchase rather than a broker problem, and its
operational fragility is real but costs a periodic manual login rather than a strategy.

**A switch would make sense only if the strategy changed first** — dropping FX carry and futures for
US equities and options only. That is a strategy decision, with the platform following from it, not
the other way round.

### The fix attempted 2026-10-09: `ColdRestartTime`

**Both outages began on a Sunday** — 2026-09-06 and 2026-09-13 are both Sundays. That is not a
coincidence: IBKR requires a full shutdown and fresh logon once a week, and IBC documents the handler
for it in its own `config.ini`:

> *"To assist in complying with the requirement to fully shut down TWS on Sundays, IBC can be
> configured with a Cold Restart Time... IBC tidily closes TWS, and the script then reloads IBC thus
> starting a new instance and initiating the usual full logon. There is thus no need to make any other
> arrangements for closing and restarting at the weekend."*

And, pointedly: *"where this information mentions 'manual authentication', closing down and restarting
IBC will do the job."*

**`ColdRestartTime` was blank.** Only `AutoRestartTime=03:00` was set, which performs the *soft*,
token-based restart — the one that works until the token expires and then demands a human. So the
configuration had a daily restart that could not survive the weekly re-authentication, and no weekly
cold restart to satisfy it.

Set to `ColdRestartTime=04:30` (local). 04:30 PT is 07:30 US/Eastern year-round — PT is always ET−3 —
which satisfies IBC's "after 01:00 US/Eastern" requirement without a DST edge case, and is clear of
both `AutoRestartTime=03:00` and every scheduled job. Previous config backed up to
`~/ibc/config.ini.bak-20261009`.

**This is a hypothesis with good evidence, not a verified fix.** What supports it: the Sunday
correlation, IBC's own documentation naming this the remedy for exactly this symptom, and the
2026-10-08 21:53 event where IBC *did* complete an unattended credentialed re-login in ~45 seconds,
which shows stored-credential logon works in general. What is unproven: whether a full cold logon
completes unattended, or whether it stops for 2FA — `SecondFactorDevice` is blank and
`--on2fatimeout=exit` is on IBC's command line, so a 2FA prompt is the plausible failure mode.

It will be exercised on the next Sunday cold restart, with the `com.fx.gateway-watchdog` agent (spec
`008`) as the net — the first time this class of failure has had a detector in place while it
happened. Expect at most one watchdog alert if the cold logon runs longer than ~5 minutes; a quiet
Sunday morning means it worked.

## What would change this

- **The trend sleeve validating on real futures data** would give the first strategy that both works
  and is deployable at a plausible size. That is the immediate reason to pursue LEAN data.
- **Access to institutional financing** would revive the FX book, which is otherwise finished.
- **A materially larger capital base** would relax granularity and make more of the universe reachable.
- **QC data proving inadequate or expensive** would close the tooling question and leave the existing
  framework as it is — which is a perfectly acceptable outcome.
