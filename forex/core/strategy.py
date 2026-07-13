from abc import ABC, abstractmethod
import pandas as pd
from forex.core.dataview import DataView

class Strategy(ABC):
    NAME: str | None = None

    def fit(self, train: DataView) -> None:
        return None

    @abstractmethod
    def target_weights(self, view: DataView) -> pd.DataFrame:
        ...

    def params(self) -> dict:
        return {}

    def search_space(self) -> dict:
        return {}

    @classmethod
    def build(cls, params: dict) -> "Strategy":
        return cls(**params)
