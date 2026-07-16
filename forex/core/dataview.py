from dataclasses import dataclass, field
import pandas as pd

@dataclass
class DataView:
    spot: pd.DataFrame
    rates: dict
    reer: dict = field(default_factory=dict)
    macro: dict = field(default_factory=dict)
    positioning: dict = field(default_factory=dict)   # code -> weekly CFTC net-spec position series

    @property
    def codes(self) -> list:
        return list(self.spot.columns)

    @property
    def calendar(self) -> pd.DatetimeIndex:
        return self.spot.index

    def truncate(self, asof) -> "DataView":
        asof = pd.Timestamp(asof)
        spot = self.spot.loc[:asof]
        rates = {k: v.loc[:asof] for k, v in self.rates.items()}
        reer = {k: v.loc[:asof] for k, v in self.reer.items()}
        macro = {k: v.loc[:asof] for k, v in self.macro.items()}
        positioning = {k: v.loc[:asof] for k, v in self.positioning.items()}
        return DataView(spot=spot, rates=rates, reer=reer, macro=macro, positioning=positioning)

    @classmethod
    def from_fred(cls, cache_dir, loader=None, codes=None) -> "DataView":
        from forex.config import CURRENCIES, MACRO_SERIES, DEFAULT_CODES
        from forex.data.prices import build_spot_panel
        from forex.data.fred import load_series
        if loader is None:
            loader = load_series
        if codes is None:
            codes = DEFAULT_CODES
        spot = build_spot_panel(cache_dir, loader=loader, codes=codes)
        rates = {"USD": loader(CURRENCIES["USD"].rate_fred, cache_dir=cache_dir) / 100.0}
        for c in codes:
            rates[c] = loader(CURRENCIES[c].rate_fred, cache_dir=cache_dir) / 100.0
        reer = {c: loader(CURRENCIES[c].reer_fred, cache_dir=cache_dir) for c in codes}
        macro = {name: loader(sid, cache_dir=cache_dir) for name, sid in MACRO_SERIES.items()}
        return cls(spot=spot, rates=rates, reer=reer, macro=macro)
