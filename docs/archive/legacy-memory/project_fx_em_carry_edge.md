---
name: project_fx_em_carry_edge
description: "Broad EM carry is the program's first REAL edge — persistent, cost-robust; overlays don't help; plain 5-EM carry is the deployable"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

**Broad EM carry is the first real, deployable-quality edge in the entire FX (and crypto) program.**
Established 2026-07-14 after G10 carry was found dead post-2010 ([[project_fx_data_rebaseline_2026_07_14]]).

**The book:** plain cross-sectional carry (rank by rate, long top / short bottom) on **5 liquid EM —
MXN, ZAR, KRW, BRL, INR — long2/short2**, monthly. Universe opt-in via `--universe MXN,ZAR,BRL,INR,KRW`
(in `CURRENCIES`, NOT in DEFAULT_CODES). Cost-modeled at 15bp (vs 1bp G10).

**Era-split (net 15bp), the in-regime evidence:**
| era | Sharpe | Calmar | maxDD |
|---|---|---|---|
| 2000–2009 | 0.89 | 0.59 | −21% |
| 2010–2017 | **+0.27** | 0.10 | −23% |
| 2018–2023 | **0.85** | 0.65 | −13% |

- **Positive in EVERY era including both modern sub-eras** — the ONLY strategy in the program to clear the
  within-modern-era persistence bar ([[feedback_evaluate_in_deployment_regime]]). G10 was ~0; crypto edges
  died at the liquidity wall.
- **Cost-robust: 15bp ≈ 1bp** — the "edge lives where you can't cheaply trade" wall does NOT bite these
  liquid EM. First edge in the program to survive it.
- **Broadening 3→5 was the key move.** The 3-EM (MXN/ZAR/KRW, 1×1) crashed −52% / −0.43 Sharpe in
  2010–17; de-concentrating to 5 (2×2) turned it +0.27 / −23%. The −52% was a concentration artifact, not
  a death (unlike G10).

**Overlays DON'T help (4th "always-on beats timed" — [[project_fx_always_on_beats_timed]]):**
- vol-target HURTS both modern eras (de-risks at wrong times).
- trend is a real crash hedge (2000–09 DD −21%→−7%, Sharpe→1.10) but CRUSHES modern return
  (2018–23 0.85→0.21) — over-hedges when there's no crash; loses on Calmar in-regime too.
- **Plain broad carry is the deployable.** Reduce crash risk via MORE diversification, not overlays.

**TRADEABILITY (VERIFIED first-hand via IBKR API `qualifyContracts` on paper acct DUQ218063, 2026-07-15)
— the edge SURVIVES the wall.** IBKR IDEALPRO spot: **MXN, ZAR, KRW tradeable (valid conIds); BRL, INR
NOT (Error 200 "no security definition").** (KRW IS tradeable — corrects the earlier NDF-only guess.) But
**adding KRW is a mild DRAG** (low-yielder, competes with JPY/CHF shorts + Korea noise, no extra carry):
G10+MXN+ZAR+KRW 2018–26 Sharpe 0.60 < G10+MXN+ZAR 0.68. **Deployable book = G10 + MXN + ZAR** (no NDF,
current to 2026): **2018–2026 Sharpe 0.68 vs G10-only 0.27** (2.5×); 2018–23 0.54 vs full-5EM 0.69; 2010–17
weak (0.13, ~ G10-only 0.18); maxDD −19%; cost 3bp. **First fully-tradeable deployable edge in the
program.** The EM that would help (BRL high-yield, INR) are the untradeable ones — so ~0.68 recent is the
honest ceiling of the tradeable G10-spot+EM carry book.

Side finding: **bare G10 carry is ~0.18–0.27 modern (weak, not dead)** — the ~0 seen earlier was the
*overlaid* carry_trend_voltarget; the vol-target/trend overlays were making G10 WORSE
([[project_fx_always_on_beats_timed]]).

**IBKR live execution:** Phase 0 (connectivity) + Phase 1 (order PREVIEW) DONE 2026-07-15, reviewed
(opus) + pushed. `LiveExecution` (forex/run/execution.py, `ib_async`) is preview-only: `readonly=True`,
prices from historical MIDPOINT (competing-session-proof; watch Error 10197 = another login), maps carry
weights → IDEALPRO orders (sign from spot_invert), places NOTHING (triple-guarded; non-preview raises).
Run: `forex dryrun --strategy carry --universe ... --broker ib --preview` (paper Gateway :4002, acct
DUQ218063). Validated: correct signs (long high-yield MXN/ZAR/NOK, short low-yield JPY/CHF/SEK), $1M NAV.
**Phase 2 GATE — VALIDATED 2026-07-15 (paper, tiny reversible order).** Placed 20k EUR.USD BUY then SELL
on paper (acct DUQ218063): both FILLED, account left FLAT, no dangling orders. **FX positions DO report
as conId-matched `Position` objects** (EUR.USD conId 12087792, qty 20000) — so `LiveExecution.cur_by_conid`
reconciliation is CORRECT. Gotcha learned: **market orders need an EXPLICIT TIF** (Error 10349 "TIF set
to DAY based on order preset" otherwise — orders still fill but noisy). To place, Read-Only API must be
OFF in Gateway + connect `readonly=False`. **Phase 2 (paper order PLACEMENT) BUILT + reviewed (opus) + PAPER-VALIDATED 2026-07-15.** `LiveExecution`
placement path: 5 guards before any placeOrder — (1) `confirm=True` (CLI `--confirm`, never from TOML);
(2) account must be `DU`-prefixed (paper) else `allow_live`; (3) per-order ≤ `max_order_frac` (0.25) AND
gross `sum|w|` ≤ `max_gross` (2.5) — reject whole rebalance; (4) skip < `min_order_units` (20k); (5)
explicit TIF="DAY". Finite-input validation (NaN fails caps OPEN). Paper acceptance: guard blocked a tight
cap live; placed the full G10+MXN+ZAR carry book (`--confirm --max-order-frac 0.4` for 33% legs), all 6
filled with CORRECT signs (long MXN/NOK/ZAR, short JPY/CHF/SEK), flattened clean. Run:
`forex dryrun --strategy carry --universe <G10>,MXN,ZAR --broker ib --confirm --max-order-frac 0.4`.
**Known polish (not blocking):** (A) fill-REPORT under-counts (await-fills reads orderStatus.filled too
early on some legs — trades correct, report incomplete; fix via trade.fills/reqExecutions). (B) any
FLATTEN/close logic must set `exchange='IDEALPRO'` on positions() contracts (they lack it — "Warning 321
Missing order exchange"); LiveExecution unaffected (uses Forex(pair)). **Phase 3 (rollback + partial-fill) BUILT + reviewed (opus) + paper-validated 2026-07-15.** Auto-unwind:
on mid-loop `placeOrder` failure, best-effort cancel-unfilled + flatten-filled from the batch (reuses the
Forex(pair) qualified contract — exchange set), logs each failure ("POSITION MAY BE OPEN; verify"), NEVER
raises (can't mask the original error), then re-raises "placement failed ... (VERIFY POSITIONS)". Partial
fill → `RebalanceReport.complete=False` + CLI "⚠ INCOMPLETE" (flag, NO retry — user choice). Polish A
(fill report) fixed + confirmed on real fills (all 6 legs now reported). Unit tests cover unwind-runs +
never-raises + no-unwind-on-success + flatten-direction + partial-flag. **The paper placement path is
now trusted** (guards + placement + reconcile + rollback all validated).

**Failure-injection drill DONE (2026-07-16):** injected an order-2 placeOrder failure on the real paper
account (preview=False) → order 1 placed+filled, unwind FLATTENED it, account FLAT, "placement failed...
VERIFY POSITIONS" raised. Auto-unwind validated end-to-end on the broker. **CLI reconciliation validated:**
cycle 1 established the 6-leg carry book, cycle 2 (fresh CLI process, same target) = turnover 0.0 / 0
orders — reconciles correctly, no over-trade (the reqPositions-settle fix works across fresh connects).
**Scheduled forward track BUILT:** `scripts/monthly_paper_rebalance.sh` + `docs/scheduled-paper-track.md`
— monthly carry rebalance on IB paper via the validated CLI; REQUIRES IB Gateway always-on (NOT TWS —
TWS auto-restarts daily + needs re-login; we hit this) + FRED_API_KEY. **Trap learned: LiveExecution
defaults preview=True — direct scripts need preview=False to place; the CLI (`--confirm`) handles it. Use
the CLI, not ad-hoc loops.**

**Remaining before LIVE (deliberately gated):** the LIVE gate itself — `allow_live=True` + live account
(`U…`) + live port — a separate, explicit, deliberate decision. (Optional: flatten-fails-visibility +
disconnect-cancels drills.) Paper NAV drifted ~$5k from many place/flatten cycles today (harmless, fake).

**BROADENED BOOK IS THE NEW DEPLOYABLE (2026-07-16, DONE + committed `feat/tradeable-carry-book`).**
Added the 4 IBKR-deliverable CE-Europe EM (PLN/HUF/CZK/ILS — FRED has IR3TIB01 rates, NOT USD spot →
spot from IBKR) to G10+MXN+ZAR. On IBKR spot + FRED rates, carry 3/3: **`TRADEABLE_CARRY` (15 ccy) Sharpe
0.81 (2020-26) / 0.69 (full 2015-26) vs G10+MXN+ZAR 0.60/0.58** — positive both eras, ~same DD (−18%),
**cost-robust: 0.79/0.67 even at 15bp** (carry is monthly, low-turnover). Unlike the EM-ONLY broadening
(which diluted recent-era — CE legs always held in a 2×2), here 3/3 over a WIDER universe = better
cross-sectional leg selection, so it LIFTS the recent era too. Formalized: `config.TRADEABLE_CARRY` +
`forex.data.ibkr.build_carry_view`/`fetch_daily` (spot_fred=None for the 4; `build_spot_panel` now rejects
spot_fred=None loudly). Cache: `data_cache/ibkr_daily/`. Caveat: 0.81 is the favorable recent window;
IBKR spot caps history at ~2015 (2 eras); survivorship. IBKR-spot deployable numbers run ~0.58-0.60 for the
old book vs the memory-recorded 0.68 (FRED spot, 2018+) — data-source diff, not a regression.

**LIVE-CLI INTEGRATION DONE (2026-07-16, commit fb706ac).** `cli._build_view` now routes any universe
containing an IBKR-only ccy (spot_fred=None) to `build_carry_view` (IBKR daily spot + FRED rates) instead
of `from_fred`; G10/FRED universes unchanged. Verified end-to-end: `dryrun --broker sim --preview
--universe <TRADEABLE_CARRY> --param n_long=3 --param n_short=3` selects longs ZAR/MXN/HUF, shorts JPY/CHF/
SEK (new HUF participates) — the 4 IBKR-only ccy trade through the CLI. So paper-trading the broadened book
is now `dryrun --broker ib --confirm --universe EUR,JPY,...,MXN,ZAR,PLN,HUF,CZK,ILS --param n_long=3
--param n_short=3` (needs `data_cache/ibkr_daily/` populated via `fetch_daily`; NOT yet paper-fill-validated
on the 4 new legs — only the sim/preview path is confirmed). 226 tests pass.

**PAPER-FILL VALIDATED (2026-07-16, acct DUQ218063, TWS :7497).** All 4 CE-Europe legs qualify + fill +
flatten clean: USD.PLN (conId 34831481), USD.HUF (34831484), USD.CZK (34838409), USD.ILS (44495102) — tiny
reversible BUY+SELL each Filled, residual FLAT. FINDING: these EM pairs have a **USD 25,000 IdealPro
minimum**; a 20k order trips Warning 399 and routes as an ODD LOT (still fills). LiveExecution's
min_order_units=20k → small-NAV tests of these legs go odd-lot; non-issue at real NAV (~$167k/leg at $1M/6),
but bump the min to 25k if odd-lot routing matters. Work on branch `feat/tradeable-carry-book` (pushed to
origin, NOT merged — direct-to-main push was blocked; needs merge/PR decision).

**Next / open (research):** (1) Register a named strategy
(currently `carry --universe`). (3) BRL/INR recent-rate hunt only matters for research (untradeable anyway).
(4) Survivorship caveat remains.
