import random
from dataclasses import dataclass

@dataclass
class Float:
    low: float
    high: float
    def sample(self, rng: random.Random) -> float:
        return rng.uniform(self.low, self.high)

@dataclass
class Int:
    low: int
    high: int
    def sample(self, rng: random.Random) -> int:
        return rng.randint(self.low, self.high)

@dataclass
class Categorical:
    choices: list
    def sample(self, rng: random.Random):
        return rng.choice(self.choices)
