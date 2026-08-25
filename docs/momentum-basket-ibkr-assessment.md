# Gate — `MomentumRegimeBasket15mFast` on IBKR (stocks or crypto), 2026-08-25

Question: the freqtrade crypto strategy performs strongly over a long period. **Would an equivalent
approach be profitable at IBKR, on individual stocks or on crypto?**

**Verdict: no, on both branches.** Restricted to what IBKR can actually trade, the crypto version equals
buy-and-hold BTC. On a de-biased equity universe, every variant loses to simply equal-weighting the same
stocks. The edge is a property of the *universe*, not the mechanism — and IBKR cannot supply that universe.

---

## The strategy

`MomentumRegimeBasket15mFast` is a one-line subclass of `MomentumRegimeBasket15m`: `MOM_LOOKBACK_DAYS`
90 → 14. Mechanics are otherwise identical — cross-sectional top-3 momentum, BTC>SMA100 regime gate,
per-coin SMA50 trend filter, rank-9 exit hysteresis, equal weight, cash when fewer than 3 qualify.

**Its own docstring already disputes the "long period" claim for lb=14.** The cross-regime sweep records
lb=14 ranking **5th of 6** in P1 (2021-05..2022-12); only lb=21 is strong in all three windows
(1st/1st/2nd). The author notes the earlier "persistence validated" result came from splitting
2024-05..2026-08 in half — one regime, both halves inside it. That is exactly the era-split failure this
repo's filter 2 exists to catch, and it is worth crediting: the file diagnoses itself correctly.

## Crypto branch — killed by IBKR's universe

IBKR/PAXOS offers **11 coins** (probed live): BTC, ETH, LTC, BCH, PAXG, LINK, UNI, AAVE, MATIC, SOL,
SHIB. Nine have data in the freqtrade cache. Same engine, same 20bp/turn, same eras — the only change is
which coins you are allowed to hold.

| lb | full universe (75) P1 / P2 / P3 | ann | Sharpe | | IBKR-tradable (9) P1 / P2 / P3 | ann | Sharpe |
|---|---|---|---|---|---|---|---|
| 7 | −18.3 / +22.8 / +49.0 | 12.6% | 0.49 | | −9.0 / +120.0 / **−16.3** | 8.7% | 0.41 |
| **14** | +17.5 / +14.2 / **+1094.3** | 47.2% | 0.89 | | −2.2 / +125.6 / **−9.2** | **12.7%** | **0.49** |
| 21 | +10.2 / +81.0 / +695.3 | 46.4% | 0.88 | | +12.9 / +153.3 / +30.4 | 22.0% | 0.67 |
| 30 | +54.2 / +50.1 / +477.6 | 44.6% | 0.86 | | +17.2 / +28.7 / −12.1 | 7.5% | 0.38 |
| 90 | +36.3 / +19.4 / +341.6 | 35.5% | 0.80 | | +32.1 / +24.3 / −20.2 | 6.7% | 0.36 |
| *BTC buy & hold* | −71.4 / +256.9 / +30.7 | **12.6%** | **0.49** | | *(same)* | 12.6% | 0.49 |

**At the author's chosen lb=14, the IBKR version returns 12.7% at Sharpe 0.49 — indistinguishable from
holding BTC and doing nothing** (12.6%, 0.49), with 43× annual turnover to get there. The full universe's
+1094% in P3 becomes **−9.2%** when restricted to IBKR's coins. The entire P3 explosion came from coins
IBKR does not offer.

Best IBKR case is lb=21 at Sharpe 0.67 with a **−54.5% drawdown** — a worse risk profile than anything
this program has been willing to deploy.

This confirms the base class's own diagnosis: *"the crypto winner leaned on survivorship + illiquid-alt
concentration + extreme dispersion."* IBKR's 11 coins are the large-cap head of the distribution. The
tail is the strategy.

## Equity branch — killed by the survivorship control

Universe: 98 liquid US large caps, daily adjusted closes, 2010-2026, cash at ^IRX, SPY as the regime
reference. **The universe is deliberately survivorship-biased** — it contains today's winners (NVDA,
TSLA, PLTR, MSTR, COIN, SNOW). Every number is therefore an upper bound; the test is whether it fails
*even with the bias helping*.

At 5bp/turn the biased run looks excellent — lb=90 gives 37.5% at Sharpe 1.14 vs SPY's 0.86. **But the
raw test omits the control that matters: what does the universe itself return?**

| | 2010–2015 | 2016–2020 | 2021–2026 | full ann | Sharpe | maxDD |
|---|---|---|---|---|---|---|
| SPY | 12.6% / 0.83 | 15.1% / 0.84 | 15.1% / 0.92 | 14.2% | 0.86 | −33.7% |
| **EW buy & hold, biased universe** | 17.8 / 1.22 | 23.1 / 1.19 | 16.0 / 0.91 | 18.7% | **1.09** | −32.2% |
| **EW buy & hold, legacy universe** | 19.1 / 1.17 | 19.7 / 1.00 | 14.7 / 0.96 | 17.7% | **1.04** | −34.3% |
| momentum lb=14, biased | 16.7 / 0.80 | 35.1 / 1.12 | 22.6 / 0.72 | 24.0% | 0.84 | −39.3% |
| momentum lb=90, biased | 21.6 / 0.94 | 55.7 / 1.53 | 40.3 / 1.04 | 37.5% | 1.14 | −50.8% |
| **momentum lb=14, legacy(79)** | 2.1 / 0.21 | 11.0 / 0.54 | 18.1 / 0.75 | **10.0%** | **0.51** | −39.7% |
| **momentum lb=90, legacy(79)** | 10.8 / 0.58 | 12.6 / 0.65 | 26.7 / 0.94 | **16.5%** | **0.74** | −36.4% |
| **momentum lb=126, legacy(79)** | 9.6 / 0.55 | 18.1 / 0.82 | 21.7 / 0.82 | 16.1% | 0.73 | −34.1% |

"Legacy" restricts to the 79 names already established large caps in 2010, removing the post-hoc winners.

**Two findings, and both are fatal:**

1. **Even on the biased universe, momentum barely beats equal-weight buy-and-hold** of the same names —
   Sharpe 1.14 vs 1.09 at lb=90, and *below* it (0.84) at the fast lb=14 the "Fast" variant is about.
   55×/yr turnover against zero, for five basis points of Sharpe.
2. **On the de-biased universe every variant loses outright.** lb=14 gives Sharpe 0.51 against SPY's 0.86
   and EW's 1.04. lb=90 gives 0.74. **Momentum rotation subtracts value from the universe it selects
   from.** The apparent edge was the universe, and the universe was chosen with hindsight.

Note also the inversion versus crypto: on equities the *fast* lookbacks are the worst and the slow ones
(90–252d, i.e. classic 12-1 momentum) are the best — consistent with this repo's recorded finding that
*"frequent rebalancing hurts on liquid ETFs (weekly Sharpe 0.54 < monthly 0.61 — whipsaw)"*. The "Fast"
variant is optimising in precisely the wrong direction for liquid instruments.

## Risk profile, separately disqualifying

Drawdowns run −39% to −68% on equities and −54% on IBKR crypto. The deployed book runs −8% to −21%. Even
had the returns survived, this is a different risk class, and the program's stated bar is portfolio
Sharpe with a Calmar constraint — not raw return.

## What would change this

- **A point-in-time universe** (CRSP, Sharadar, Norgate) would replace the legacy proxy with a real test.
  The legacy split is a mitigation, not a fix — it still conditions on surviving to 2026.
- **A small/mid-cap universe**, where cross-sectional dispersion is genuinely higher, is the one honest
  analogue of the crypto alt tail. It is also where costs, borrow and liquidity bite hardest, which is
  the trade this repo has lost every previous time.
- Neither is worth funding on the evidence above: the mechanism failed against a *free* null (equal
  weight) in both asset classes.

## Reproduction

`scratchpad/mom_engine.py` (shared mechanics), `crypto_test.py`, `stock_test.py`, `stock_control.py`.
Data: freqtrade `binanceus` daily feathers; Yahoo chart API for equities; IBKR live probe for the PAXOS
universe. All free.
