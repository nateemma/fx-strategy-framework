# QuantConnect / LEAN Migration Plan (2026-08-17)

Companion to [`platform-decision.md`](./platform-decision.md): IBKR stays for execution, LEAN is
evaluated for research data.

**Headline recommendation: plan for stages 0–2 and expect to stop there.** A full migration is
probably the wrong shape, and the plan is deliberately built so that stopping early is a success
rather than an abandonment.

---

## Why a full migration is probably wrong

The framework is not the problem. What is missing is *futures price history* — one input. Rewriting
453 tests' worth of working, paper-validated machinery to obtain one input would put real assets at
risk for no gain:

- **The financing cost model** (`forex/backtest/financing.py`) encodes IBKR's published per-currency
  credit and debit schedule with the zero-floor behaviour. This is the most consequential finding the
  program has produced, and LEAN almost certainly does not model it — generic backtesters charge a
  flat borrow rate, which is exactly the assumption that hid the problem for months.
- **Structural causality** (`DataView.truncate`, `assert_causal`) is enforced by construction rather
  than by convention. Re-establishing that in another engine is work, and getting it subtly wrong is
  the failure mode this program is most exposed to.
- **Three paper-validated executors** encode guards learned the hard way: the basket's per-order cap
  had to become an atomic pre-pass, the cash sleeve's cap made placement impossible until it was
  fixed, the unwind must never raise. LEAN's brokerage layer is good and generic; swapping to it
  means re-learning those lessons on a live account.
- **The documented negatives** — every rejected factor, with evidence — live in this repo's docs and
  its `Strategy` implementations. They are the accumulated value.

So the plan below extracts the *data* and leaves the framework alone, unless a later stage produces a
reason to go further.

---

## Stage 0 — Data feasibility gate ⟵ *start here*

**Size: S. This is the whole decision.** Gate it exactly as every prior idea was gated: prove the data
exists at a price worth paying, before building anything.

Questions to answer, in order:

1. Does QC/LEAN carry **daily history for the eight trend markets** (M2K, MES, ZT, ZF, M6E, M6A, MCL,
   ZC) back to ~2007?
2. Is it **roll-adjusted**, or are individual contracts available so a continuous series can be built
   honestly? *This is the crux* — Yahoo's unadjusted continuous series is what made commodity carry
   untestable, and an unadjusted series would leave the trend gate no better validated than it is now.
3. What does it **cost**? The docs did not make coverage or pricing legible; assume nothing.
4. Can `lean data download` deliver it **locally**, without a cloud subscription?

**Exit criteria:** a written answer to all four, in the same form as every other gate in this repo.
If (1) or (2) fails, the migration question closes and the framework stands as it is — a perfectly
good outcome that costs an afternoon.

---

## Stage 1 — Data extraction only

**Size: M. No framework changes.** Pull futures history into the form the existing framework already
reads, and nothing else.

- `forex/data/lean.py` — a loader mirroring `forex/data/fred.py`: fetch, cache to
  `data_cache/*.parquet`, offline thereafter.
- The LEAN CLI runs in Docker and writes its own on-disk format; this stage is a translation layer,
  not a dependency inversion. The framework must not learn about LEAN.
- Tests are offline against fixtures, as with every other loader.

**Why this is the right first build:** it is reversible, it touches nothing that works, and it
unblocks the one thing actually blocked.

---

## Stage 2 — Re-run the A2 gate on real futures data

**Size: M. This is the point of the whole exercise.**

The trend gate's evidence is ETF proxies; the recommended implementation is futures. That gap is
recorded honestly in [`cross-asset-trend-findings.md`](./cross-asset-trend-findings.md) and this
closes it.

Re-run the gate construction unchanged on futures data and compare against the ETF-proxy result
(full-sample Sharpe 0.78, feasible-8 0.83, correlation to the basket +0.06):

- **If it broadly reproduces** — the trend sleeve is validated and spec `005` phase 6 becomes worth
  funding. That is the good outcome, and it is the first strategy in the program that both works and
  is deployable at a plausible size.
- **If it does not** — that is the most valuable single result available right now, because it would
  have been discovered with real money otherwise. Several proxies are loose by construction (ZC/DBA
  is corn against a broad agriculture basket; M6A/UUP is one currency against a dollar index).

Also worth re-running once the data exists: **commodity carry** (Tier C1), which has been blocked on
roll-adjusted data since July and would become testable for free.

---

## Stage 3 — Decision point

**No work. Stop and choose.** Given stages 0–2:

| If | Then |
|---|---|
| Data is good and trend validates | **Stop migrating.** Fund the market-data subscription or keep using LEAN data, run spec `005` phase 6, deploy the sleeve. The framework stays. |
| Data is good, trend does *not* validate | **Stop migrating.** Record the negative, do not deploy, and reconsider what the account is for. |
| Data is good and you want new asset classes | Consider stage 4 for **options and prediction markets only** — the two things the framework cannot express at all. |
| Data is inadequate or costly | **Stop.** Close the question; the framework stands. |

The expected outcome is one of the two "stop migrating" rows.

---

## Stage 4 — *Conditional.* Parallel research in LEAN

**Size: L. Only if new asset classes are wanted.** Options and prediction-market strategies cannot be
expressed in a framework whose atom is "point-in-time data → target currency weights". That is a real
limitation and the only strong argument for adopting LEAN more deeply.

If pursued, the discipline is **reconciliation, not replacement**: port one already-understood
strategy (`carry_cot_mom` or the trend book), run it in both engines over the same window, and
compare. If they disagree, one is wrong and it matters enormously which. Do not port anything else
until they agree.

Keep the framework as the system of record for everything already deployed.

---

## Stage 5 — *Not recommended.* Execution via LEAN

Replacing the three executors with LEAN's IBKR integration would discard guards that were earned by
finding real bugs on a real account, in exchange for no benefit — LEAN trades through the same broker
at the same rates.

Recorded here so the option is visibly considered and visibly declined, rather than being rediscovered
later as an apparently good idea.

---

## What this plan deliberately does not do

- **It does not change brokers.** IBKR is the cheapest retail margin available and the constraint that
  matters most is financing.
- **It does not commit to a rewrite.** Every stage past 1 is conditional on evidence from the one
  before.
- **It does not fund real trading.** That decision waits on stage 2 and is governed by
  [`platform-decision.md`](./platform-decision.md).
