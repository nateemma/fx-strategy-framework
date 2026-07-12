import os
import tomllib
from dataclasses import dataclass

@dataclass
class EnvConfig:
    data_cache_dir: str = "data_cache"
    fred_api_key: str | None = None
    output_dir: str = "runs"
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 1
    ib_account: str | None = None
    dry_run: bool = True

    @classmethod
    def load(cls, path=None, environ=None) -> "EnvConfig":
        environ = os.environ if environ is None else environ
        data = {}
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                data.update(tomllib.load(fh))
        env_map = {
            "data_cache_dir": environ.get("FOREX_DATA_CACHE_DIR"),
            "fred_api_key": environ.get("FRED_API_KEY"),
            "output_dir": environ.get("FOREX_OUTPUT_DIR"),
            "ib_host": environ.get("FOREX_IB_HOST"),
            "ib_port": environ.get("FOREX_IB_PORT"),
            "ib_account": environ.get("FOREX_IB_ACCOUNT"),
        }
        for k, v in env_map.items():
            if v is not None:
                data[k] = v
        known = set(cls.__dataclass_fields__)
        d = {k: v for k, v in data.items() if k in known}
        if "ib_port" in d:
            d["ib_port"] = int(d["ib_port"])
        return cls(**d)
