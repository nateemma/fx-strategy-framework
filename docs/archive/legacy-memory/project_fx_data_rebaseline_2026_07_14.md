---
name: project_fx_data_rebaseline_2026_07_14
description: "FX book real OOS baseline is ~0.17/0.30 Sharpe, NOT the 0.52 in old docs — 0.52 was a stale-cache artifact"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

**The FX book's recorded performance (~Sharpe 0.52 for `carry_trend_voltarget`) was WRONG — a
stale-data-cache artifact. The honest OOS baseline on FRED-correct data is ~0.17 (carry+trend) / ~0.30
(carry+trend+value).** Established 2026-07-14 by full reconciliation:

- Walk-forward (1997+, 2520/504) on current data: carry 0.10, trend −0.08 (loses standalone), value 0.11,
  momentum −0.55; **carry_trend 0.17, carry_trend_voltarget 0.15 (0.17 best re-tuned),
  carry_trend_value 0.29, carry_trend_value_voltarget 0.30 (Calmar 0.12).**
- The old **0.52** (docs/architecture-review.md, factor stack carry 0.32→+trend 0.50→voltarget 0.52) does
  NOT reproduce. Proven it's the DATA, not code/params: bare carry's entire path (carry_signal,
  basket_weights, target_weights, simulate, metrics) is byte-identical to the 0.52 commit (git show), yet
  dropped 0.32→0.10; the tuned defaults (target_vol=0.062/cap=1.20) landed AFTER 0.52 and re-hyperopt on
  current data only moves 0.154→0.167 (optimal cap≈1.0 = vol-target adds nothing now).
- **Root cause = the fresh `forex download` (2026-07-14) re-fetched all spot/rates, overwriting the cache
  the 0.52 was measured on.** Current data VALIDATED correct: FRED IR3TIB01AUM156N May-2026 = 4.43000
  matches the cache to the digit; series live, sane history. So the current data is authoritative and 0.52
  was on a stale/incomplete earlier cache (unrecoverable — cache is gitignored, no backup).

**THE HEADLINE (era-split, 2026-07-14): the G10 edge is a PRE-2010 ARTIFACT.** Backtest by era,
`carry_trend_voltarget` Sharpe = **0.82 (1997–09) → 0.07 (2010–17) → 0.006 (2018–26)**. G10 carry died
with ZIRP-era rate-differential compression; **no meaningful modern edge** — live deployment on G10 spot
is NOT justified. The pooled 1997+ Sharpe (~0.15) is carried entirely by 1997–2009.

**Consequences:**
1. Deployable stays **`carry_trend_voltarget`** (NOT the value version). The pooled-WF "value doubles
   Sharpe (0.30)" was an ARTIFACT — value's edge is concentrated in the 2008 crisis (inside the WF OOS
   window); an **era-split REJECTS value** (no-value wins every era; value negative −0.23 since 2018). So
   the old "[[project_fx_carry_value_blend]] value dilutes / adds no Sharpe" claim was directionally
   RIGHT after all (right call, wrong-data reasoning). Lesson reaffirmed: pooled walk-forward can hide a
   regime artifact; always era-split before trusting a factor lift.
2. Modern edge ≈ 0, far below the ~0.8 bar ([[project_fx_return_bar]]). The whole G10 spot factor book
   may be structurally dead post-ZIRP.
3. **Reproducibility gap:** the data cache is unversioned, so a routine re-download silently invalidated
   every recorded figure. Pin a data snapshot / hash the cache into results before trusting numbers.
4. Docs re-baselined 2026-07-14 (README Results table, architecture-review.md correction note, backlog
   #3/#11) to the honest numbers + decay. "Always-on beats timed" ([[project_fx_always_on_beats_timed]])
   still holds qualitatively.
5. **NEXT: test EM carry (#12)** — MXN/ZAR/PLN etc., where rate differentials still exist post-ZIRP —
   as the candidate to revive an edge G10 spot no longer has. Then non-price data (CFTC #7 / regime #5).
