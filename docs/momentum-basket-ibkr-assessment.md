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


## Follow-ups (2026-08-25) — the regime gate, and small caps

Two questions raised on review. Both change the *explanation*; neither changes the verdict.

### Is the BTC regime gate actually applied — and does it matter?

Applied, and it is doing nearly all of the work. `BTC > SMA100` is risk-on only **47.4%** of days
(`SPY > SMA100`: 77.4%). Ablating it:

| case | gate ON | gate OFF |
|---|---|---|
| crypto full-75, lb=14 | 47.2% / 0.89 | **3.7% / 0.47** |
| crypto IBKR-9, lb=14 | 12.7% / 0.49 | **0.8% / 0.27** |
| crypto IBKR-9, lb=21 | 22.0% / 0.67 | 6.2% / 0.38 |
| equity 98, lb=14 | 24.0% / 0.84 | 16.2% / 0.60 |
| equity 98, lb=90 | 37.5% / 1.14 | **39.4% / 1.11** |

**In crypto this is a BTC trend-timing overlay with a cross-sectional garnish, not a momentum basket.**
Remove the gate and the full-universe result falls from 47.2%/yr to 3.7%. On equities at the slow
lookbacks the gate contributes nothing at all (37.5 vs 39.4). Anyone porting "the momentum basket" is
mostly porting `BTC > SMA100`, and its equity analogue is the most-decayed timing rule in the literature.

### Do small caps supply the missing dispersion?

**Yes — and it still fails, which is the more useful result.** 103 US small/mid caps, 2010-2026.

Median cross-sectional sd of 14-day returns: **small-cap 8.3%**, large-cap 5.8%, IBKR crypto 7.7%,
crypto-75 11.8%. So small caps genuinely carry more dispersion than IBKR's crypto universe.

| | full ann | Sharpe | maxDD |
|---|---|---|---|
| IWM (actual small-cap index) | 11.2% | 0.59 | −41.1% |
| **EW buy & hold, this universe** | 19.4% | **0.86** | −48.4% |
| momentum lb=126 @ 15bp | 13.1% | 0.50 | −47.7% |
| momentum lb=90 @ 15bp | 10.9% | 0.45 | −62.8% |
| momentum lb=14 @ 15bp | 7.3% | 0.37 | −67.9% |
| momentum lb=14 @ 30bp | **−9.5%** | −0.05 | **−90.8%** |
| momentum lb=21 @ 30bp | −9.5% | −0.09 | −94.2% |

**Dispersion is necessary but not sufficient — what matters is dispersion per unit of cost.** Dispersion
rose ~43% (5.8% → 8.3%) while small-cap spreads are 3–6× large-cap and the strategy turns over 100–113×
per year. The cost term scales faster than the signal. Crypto clears this bar because 11.8% dispersion
comes at roughly 20bp all-in; small caps offer less dispersion at similar or worse cost.

**The survivorship control is worse here than for large caps.** Equal-weighting this hand-assembled
universe returns 19.4%/yr against IWM's actual 11.2% — an ~8pp/year bias baked into the ticker list. The
momentum rows above are therefore upper bounds *and* they still lose to the equal-weight null by a wide
margin.

Concentration is the other half of it: holding 3 names out of 100 produces −48% to −95% drawdowns
against the universe's own −48%. The cross-section is dominated by market beta, so top-3 momentum names
are mostly just high-beta names — concentration risk without a diversification payoff.

**Closing note on method.** The equal-weight buy-and-hold of the *same universe* is the null that killed
this idea in all three asset classes, and it was absent from the original study. Any future
cross-sectional proposal here should be scored against it before anything else.


## Follow-ups (2026-08-25, part 2) — is there a better universe, and is BTC the right gate?

### Dispersion per unit of cost, across everything IBKR can trade liquidly

| universe | n | median cross-sec sd (14d) | assumed cost/turn | **disp/cost** |
|---|---|---|---|---|
| US sector ETFs | 9 | 2.4% | 2bp | 157 |
| **industry / thematic ETFs** | **48** | **4.1%** | **3bp** | **137** |
| US large caps | 98 | 5.8% | 5bp | 116 |
| country ETFs | 35 | 3.2% | 5bp | 64 |
| crypto — all 75 | 75 | 11.8% | 20bp | 59 |
| US small caps | 103 | 8.3% | 15bp | 55 |
| crypto — IBKR/PAXOS 9 | 9 | 7.7% | 20bp | 39 |

**Crypto ranks near the bottom on this measure.** Industry/thematic ETFs (SMH, XBI, GDX, XOP, URA, TAN,
KRE …) look like the ideal hunting ground: 2.3× crypto's ratio with a genuine 48-name cross-section, at
ETF spreads. Sector ETFs rank top but 9 names with top-3 is not a cross-section.

### Industry/thematic ETFs — the best candidate on paper, and it still fails

n=48, 2012-2026, 3bp/turn:

| | 2012–2016 | 2017–2021 | 2022–2026 | full ann | Sharpe | maxDD |
|---|---|---|---|---|---|---|
| SPY | 14.2 / 1.11 | 18.4 / 0.99 | 12.4 / 0.75 | 15.0% | **0.93** | −33.7% |
| **EW buy & hold, this universe** | 8.6 / 0.61 | 16.6 / 0.83 | 12.9 / 0.73 | 12.6% | **0.73** | −39.6% |
| momentum lb=21, SPY gate (103×/yr) | 1.5 / 0.18 | 16.7 / 0.76 | 25.6 / 1.04 | 13.9% | 0.66 | −30.6% |
| momentum lb=90, SPY gate | 7.2 / 0.42 | 11.6 / 0.59 | 14.2 / 0.67 | 10.9% | 0.56 | −31.1% |
| momentum lb=126, SPY gate | 13.0 / 0.64 | 4.7 / 0.31 | 13.0 / 0.62 | 10.1% | 0.52 | −43.0% |

Best variant is 0.66 against the universe's own equal-weight null at 0.73 — and against simply holding
**SPY at 0.93**. The universe itself is a worse thing to own than the index; rotating within it is worse
again. **Dispersion per unit of cost is necessary but not sufficient.**

### Is BTC the right gate outside crypto? The question dissolves — no gate helps outside crypto

Tested three regime references (market index, the universe's *own* equal-weight index, and none). The
original small-cap run used SPY where IWM or the universe's own aggregate is arguably correct; fixing
that changes nothing.

| small caps, 15bp | SPY gate | IWM gate | own-EW gate |
|---|---|---|---|
| lb=21 | **0.33** | 0.18 | 0.15 |
| lb=126 | 0.50 | **0.52** | 0.51 |

| industry ETFs, 3bp | SPY gate | own-EW gate | **no gate** |
|---|---|---|---|
| lb=21 | **0.66** | 0.64 | 0.65 |
| lb=90 | 0.56 | 0.52 | 0.58 |
| lb=126 | 0.52 | 0.44 | **0.60** |

All within noise, and on industry ETFs **no gate at all scores as well as any gate**. Contrast crypto,
where the gate is worth ~43 percentage points of annual return. There is no equity-side equivalent
because no equity index trends the way BTC did — and SPY>SMA-type rules are the most-decayed timing
signal in the literature.

### Why crypto works and nothing else does

The gate and the cross-section are **complements**, not substitutes:

| | ann | Sharpe | maxDD |
|---|---|---|---|
| BTC buy & hold | 12.6% | 0.49 | −76.6% |
| BTC trend only (>SMA100, else cash, 20bp) | **9.3%** | **0.45** | −39.1% |
| basket IBKR-9 lb=21 (gate + cross-section) | 22.0% | 0.67 | −54.5% |
| basket full-75 lb=14 (gate + cross-section) | 47.2% | 0.89 | −73.6% |
| basket full-75 lb=14, **gate ablated** | 3.7% | 0.47 | — |

Remove the gate → 3.7%. Remove the cross-section → 9.3%. Keep both → 47.2%. The strategy needs a
**strongly-trending dominant factor** *and* a **high-dispersion tail of assets levered to it**. Crypto
2021-2026 supplied both. No IBKR-reachable universe supplies either at sufficient strength — which is a
more precise and more portable statement than "survivorship bias."

**This closes the search.** Seven universes were measured; the two most promising on first principles
(small caps for dispersion, industry ETFs for dispersion-per-cost) were each run to a verdict, and both
lost to a zero-turnover equal-weight null.


## Follow-up (2026-08-25, part 3) — "beats SPY" is a moving bar. Does momentum earn its keep when the index doesn't?

A fair objection to every comparison above: **SPY's 0.93 Sharpe is not a property of equities, it is a
property of 2010-2026.** By era:

| era | ann | Sharpe | maxDD |
|---|---|---|---|
| 1993–1999 | 21.0% | **1.32** | −19.0% |
| **2000–2009** | **−1.0%** | **0.07** | **−55.2%** |
| 2010–2019 | 13.5% | 0.93 | −19.3% |
| 2020–2026 | 15.6% | 0.82 | −33.7% |
| full 1993–2026 | 10.8% | 0.65 | −55.2% |

So the null used above is itself flattered by the window, and "an index return" is a realised path, not an
expected value you can bank. The honest test is therefore: **in the decade the index delivered nothing,
does the rotation earn its keep?**

2000–2009, 67 names with full history (still survivorship-biased in momentum's favour), 10bp/turn:

| | ann | Sharpe | maxDD |
|---|---|---|---|
| SPY | −1.0% | 0.07 | −55.2% |
| **EW buy & hold, these names** | **+11.0%** | **0.57** | −46.3% |
| cash (T-bills) | +2.7% | — | 0.0% |
| momentum lb=21 (SPY gate) | **−7.2%** | −0.11 | **−79.2%** |
| momentum lb=90 (SPY gate) | −6.0% | −0.07 | −81.3% |
| momentum lb=126 (SPY gate) | +2.1% | 0.21 | −68.2% |
| momentum lb=252 (SPY gate) | +3.8% | 0.28 | −73.9% |
| momentum lb=90 (no gate) | −7.7% | −0.03 | −87.0% |

**It fails worse, not better.** In the exact regime where a rotation strategy should prove its value, it
lost money with 68–87% drawdowns while equal-weighting the same names returned 11%/yr and cash returned
2.7% with no drawdown. The objection was reasonable and the test refutes it — this *strengthens* the
rejection rather than weakening it.

The residual lesson is about the null, not the strategy: **equal-weight buy-and-hold beat SPY by 12pp/yr
in the lost decade** (+11.0% vs −1.0%). Cap-weighting, not equity itself, is what delivered nothing in
the 2000s. That is a point about index construction and belongs to the basket sleeve's design question,
not to momentum.

## Reproduction

`scratchpad/mom_engine.py` (shared mechanics), `crypto_test.py`, `stock_test.py`, `stock_control.py`,
`gate_ablation.py`, `fetch_small.py`, `small_test.py`, `fetch_etfs.py`, `dispersion_survey.py`,
`gate_and_industry.py`, `btc_trend_only.py`, `lost_decade.py`.
Data: freqtrade `binanceus` daily feathers; Yahoo chart API for equities; IBKR live probe for the PAXOS
universe. All free.
