# Income Enhancements — Securities Lending + Cash/T-Ladder (spec)

**Status:** go-live readiness plan. These are **real-money** features — the paper account (DUQ218063) earns
no real lending income and its cash interest is simulated, so this executes when/if real capital is deployed
(ties into the deferred live-money gate). SGOV *can* be tested on paper; securities lending cannot.

**Bottom line (honest sizing):** IBKR already auto-pays ~4% on idle USD cash, so the big piece is already
captured. These two levers add only a modest increment:
- **Cash buffer → SGOV: a small, clean win** (~4.3%, state-tax-exempt, auto-rolling, liquid). Do it.
- **Securities lending (SYEP): marginal-to-net-negative for THIS book** (general-collateral dividend ETFs in
  a taxable account). Defer unless the account is tax-advantaged or holds hard-to-borrow single stocks.

---

## 1. Cash buffer — hold it in SGOV (not idle cash, not a manual ladder)

The income design carries a large cash/T-bill sleeve (~$576k in the Balanced allocation) assumed at ~4%.
Options to realize that, best-first:

| Option | Yield (mid-2026) | Effort | Notes |
|---|---|---|---|
| **SGOV** (iShares 0-3mo T-bill ETF) | ~4.2-4.3% | trivial | auto-rolling, fully liquid, ~0.09% fee, **state-tax-exempt** (Treasury income) |
| Leave as IBKR cash | ~3.8-4.3% | none | auto-paid on balances >$10k; **fully state-taxable**; 0% on first $10k |
| Manual T-bill ladder (1/3/6/12mo) | ~4.3% | real | locks rates (good only if you expect cuts), state-tax-exempt, less liquid than SGOV |

**Recommendation: SGOV.** It captures the T-bill yield, is state-tax-exempt (a real edge over IBKR cash
interest in a taxable account), auto-rolls, and stays liquid for rebalancing. A **manual ladder** earns
~the same and adds work — justified *only* if you specifically want to lock today's rate against expected
Fed cuts (then a short 1/3/6/12-month T-bill ladder, ~$115k/rung, rolled at each maturity). The gain over
leaving cash at IBKR is small (~0.2-0.4% + the state-tax exemption) — this is *tax/rate optimization*, not
new return.

**Implement:** `scripts/cash_sleeve.py` parks a target dollar amount in SGOV, reusing `BasketExecution`
(a single symbol gets weight 1.0, so the same DU-account/cap/min-order/reconcile/rollback guards apply).
Default is PREVIEW; `--confirm` arms placement:
```
python scripts/cash_sleeve.py --allocation 500000            # preview
python scripts/cash_sleeve.py --allocation 500000 --confirm  # place (paper: places SGOV, income simulated)
```
Testable on paper today (it just holds the ETF); real yield accrues only on a real account. If a manual
ladder is chosen instead, it's a periodic manual bond-desk purchase — not worth automating for a few rungs.

## 2. Securities lending — Stock Yield Enhancement Program (SYEP)

**Mechanics:** enroll via Account Settings → SYEP. IBKR lends your fully-paid shares to borrowers (short
sellers), posts collateral, and pays you **50%** of the lending fee. Eligibility (verify at enroll time):
generally margin/IBKR-Pro accounts, or cash accounts with ≥$50k equity.

**Why it's marginal for THIS book (the honest part):**
- **The holdings are general-collateral.** SPY/TLT/IEF/GLD/DBC (and JEPI) are deeply liquid and easy to
  borrow, so their lending fee is tiny — realistically **~0.1-0.5%/yr**, often less. SYEP pays real money
  only on **hard-to-borrow** securities (specific single stocks in short demand), which this book doesn't hold.
- **Tax drag can exceed the fee in a taxable account.** While shares are on loan, dividends you receive
  become **payments-in-lieu (PIL)**, taxed as **ordinary income** — you lose qualified-dividend treatment.
  For dividend-paying ETFs (TLT/IEF ~4%, SPY, JEPI ~9%), that tax conversion can **cost more than the ~0.1-0.5%
  lending fee earns.** So on this book, in a taxable account, SYEP is plausibly **net-negative**.
- **Minor risks:** lent shares aren't SIPC-covered while on loan (you hold collateral at IBKR instead); you
  lose voting rights on lent shares; small counterparty/collateral risk. Low but non-zero.

**Recommendation: defer SYEP for this book.** Enroll it **only if** (a) the account is tax-advantaged (IRA —
no PIL/qualified-dividend issue), or (b) you later add hard-to-borrow single-stock positions where the fee is
material. For a taxable ETF/income book, the juice isn't worth the squeeze.

## Tracking & integration
- **SGOV** shows as a normal ETF position; whole-account NAV (snapshot_nav.py) already captures it. Its
  distributions are the cash-buffer income. No new tracking needed.
- **SYEP** income (if ever enrolled) appears on IBKR statements as "stock loan fee" — no code; read from
  statements.
- Neither touches the strategy framework or the deployed sleeves.

## Net effect on the income book
Realizing these turns the income design's ~4% cash assumption into an actual ~4.3% state-tax-exempt yield
(SGOV) — a real but small improvement — and adds ~0 from SYEP on this book. They do **not** move the ~8%
total-income target materially; they're the tax/rate-efficient way to hold the cash sleeve, not a new source
of return. The material income still comes from the JEPI + basket + realized FX return, per the sizing spec.
