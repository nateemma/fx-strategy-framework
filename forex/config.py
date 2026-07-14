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
}
