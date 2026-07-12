from dataclasses import dataclass
import pandas as pd

@dataclass
class Result:
    returns: pd.Series
    weights: pd.DataFrame
    metrics: dict
