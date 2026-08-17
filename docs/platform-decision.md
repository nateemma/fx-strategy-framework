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

## What would change this

- **The trend sleeve validating on real futures data** would give the first strategy that both works
  and is deployable at a plausible size. That is the immediate reason to pursue LEAN data.
- **Access to institutional financing** would revive the FX book, which is otherwise finished.
- **A materially larger capital base** would relax granularity and make more of the universe reachable.
- **QC data proving inadequate or expensive** would close the tooling question and leave the existing
  framework as it is — which is a perfectly acceptable outcome.
