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
    n_samples: int = 200
    seed: int = 0
    objective: str = "sharpe"
    tune: list | None = None
    preview: bool = False
    broker: str = "sim"
    ib_port: int = 4002
    jobs: int = 1

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

    def to_toml_str(self) -> str:
        def fmt(v):
            if isinstance(v, bool):
                return str(v).lower()
            if isinstance(v, str):
                return f'"{v}"'
            if isinstance(v, list):
                return "[" + ", ".join(fmt(x) for x in v) + "]"
            return str(v)
        lines = [f"strategy = {fmt(self.strategy)}", f"cost_bps = {fmt(self.cost_bps)}"]
        if self.universe is not None:
            lines.append(f"universe = {fmt(self.universe)}")
        if self.strategy_params:
            lines.append("[strategy_params]")
            for k, v in self.strategy_params.items():
                lines.append(f"{k} = {fmt(v)}")
        return "\n".join(lines) + "\n"
