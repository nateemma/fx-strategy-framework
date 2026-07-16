from dataclasses import dataclass


@dataclass(frozen=True)
class Currency:
    code: str
    spot_fred: str | None   # FRED series for USD spot; None for the USD base
    spot_invert: bool       # True if series is FX-per-USD (invert to USD-per-FX)
    rate_fred: str          # FRED short-rate series (3-month interbank, OECD)
    pub_lag_days: int       # release lag in days (0 for daily market data)
    reer_fred: str | None   # BIS Real Broad REER (RB<CC>BIS); None for USD


# Spot: FRED H.10. Rates: OECD 3-month interbank (IR3TIB01<CC>M156N), monthly, ffill.
# REER: BIS Real Broad (RB<CC>BIS), monthly index level — do NOT divide by 100.
# spot_invert=True where the H.10 series is quoted FX-per-USD.
#
# NOTE: FRED series IDs occasionally get revised/discontinued. Before the first live fetch
# (Task 3, Step 6), spot-check each ID at https://fred.stlouisfed.org/series/<ID>; if one is
# dead, substitute the nearest 3-month rate for that country and update this dict. Same caveat
# applies to the reer_fred IDs. Tests use fixtures and do not depend on the IDs being live.
# Global (market-wide) risk-off series for the cross-asset ML vol overlay (FRED, daily).
MACRO_SERIES = {"vix": "VIXCLS", "credit": "BAA10Y", "term": "T10Y2Y"}

CURRENCIES: dict[str, Currency] = {
    "USD": Currency("USD", None,       False, "IR3TIB01USM156N", 0, None),
    "EUR": Currency("EUR", "DEXUSEU",  False, "IR3TIB01EZM156N", 0, "RBXMBIS"),
    "JPY": Currency("JPY", "DEXJPUS",  True,  "IR3TIB01JPM156N", 0, "RBJPBIS"),
    "GBP": Currency("GBP", "DEXUSUK",  False, "IR3TIB01GBM156N", 0, "RBGBBIS"),
    "CHF": Currency("CHF", "DEXSZUS",  True,  "IR3TIB01CHM156N", 0, "RBCHBIS"),
    "AUD": Currency("AUD", "DEXUSAL",  False, "IR3TIB01AUM156N", 0, "RBAUBIS"),
    "NZD": Currency("NZD", "DEXUSNZ",  False, "IR3TIB01NZM156N", 0, "RBNZBIS"),
    "CAD": Currency("CAD", "DEXCAUS",  True,  "IR3TIB01CAM156N", 0, "RBCABIS"),
    "NOK": Currency("NOK", "DEXNOUS",  True,  "IR3TIB01NOM156N", 0, "RBNOBIS"),
    "SEK": Currency("SEK", "DEXSDUS",  True,  "IR3TIB01SEM156N", 0, "RBSEBIS"),
    # Emerging markets — liquid, FRED-available USD spot (DEX__US, FX-per-USD → invert=True).
    # Rate IDs are best-guess OECD IR3TIB01 (MX/KR are OECD; ZA/BR/IN are OECD key-partners —
    # validate at download and substitute a policy/interbank proxy if dead). NOT in DEFAULT_CODES
    # (the default universe stays G10); EM is opt-in via --universe. Tested only post-2010, cost-aware.
    # MXN/ZAR/KRW: OECD 3-month interbank (IR3TIB01), current to 2026.
    # BRL/INR: OECD central-bank rate (IRSTCB01) — interbank unavailable; NOTE these series are
    #   discontinued end-2023, so a BRL/INR-inclusive basket is only clean through ~2023.
    # Rate-type mix is acceptable for cross-sectional ranking (yield dispersion 3–12% >> the
    #   interbank-vs-policy spread). CNY excluded (managed float + capital controls: not tradeable carry).
    "MXN": Currency("MXN", "DEXMXUS",  True,  "IR3TIB01MXM156N", 0, "RBMXBIS"),
    "ZAR": Currency("ZAR", "DEXSFUS",  True,  "IR3TIB01ZAM156N", 0, "RBZABIS"),
    "BRL": Currency("BRL", "DEXBZUS",  True,  "IRSTCB01BRM156N", 0, "RBBRBIS"),
    "INR": Currency("INR", "DEXINUS",  True,  "IRSTCB01INM156N", 0, "RBINBIS"),
    "KRW": Currency("KRW", "DEXKOUS",  True,  "IR3TIB01KRM156N", 0, "RBKRBIS"),
    # IBKR-deliverable CE-Europe EM. FRED has the OECD 3-month interbank rate (IR3TIB01) but NOT a
    # USD spot series for these — so spot_fred is None and spot comes from IBKR (forex.data.ibkr
    # build_carry_view); they must NOT be routed through the FRED spot panel. spot_invert reflects
    # the IBKR quote (USD.xxx -> FX-per-USD -> invert). Adding these to G10+MXN+ZAR lifts the carry
    # book (2020-26 Sharpe 0.60->0.81, cost-robust to 15bp). reer best-guess BIS (unused by carry).
    "PLN": Currency("PLN", None,       True,  "IR3TIB01PLM156N", 0, "RBPLBIS"),
    "HUF": Currency("HUF", None,       True,  "IR3TIB01HUM156N", 0, "RBHUBIS"),
    "CZK": Currency("CZK", None,       True,  "IR3TIB01CZM156N", 0, "RBCZBIS"),
    "ILS": Currency("ILS", None,       True,  "IR3TIB01ILM156N", 0, "RBILBIS"),
}

# The default trading universe (G10). EM is available in CURRENCIES but opt-in via --universe.
G10 = ["EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK"]
EM = ["MXN", "ZAR", "BRL", "INR", "KRW"]
DEFAULT_CODES = G10
# The deployable carry book: G10 + the six IBKR-deliverable EM. All spot from IBKR (one source),
# rates from FRED. Load via forex.data.ibkr.build_carry_view, NOT DataView.from_fred.
TRADEABLE_CARRY = G10 + ["MXN", "ZAR", "PLN", "HUF", "CZK", "ILS"]
