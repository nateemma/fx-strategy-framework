from dataclasses import dataclass, field, asdict
import tomllib

@dataclass
class RunConfig:
    strategy: str = "carry"
    strategy_params: dict = field(default_factory=dict)
    universe: list | None = None
    timerange: list | None = None
    cost_bps: float = 1.0
    train_days: int = 1000
    test_days: int = 500

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def from_toml(cls, path) -> "RunConfig":
        with open(path, "rb") as fh:
            return cls.from_dict(tomllib.load(fh))

    def merge(self, overrides: dict) -> "RunConfig":
        d = asdict(self)
        for k, v in overrides.items():
            if v is None:
                continue
            if k == "strategy_params":
                d["strategy_params"] = {**d["strategy_params"], **v}
            else:
                d[k] = v
        return RunConfig.from_dict(d)
