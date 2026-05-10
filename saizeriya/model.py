from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    name: str
    price: int
    score: float


@dataclass(frozen=True)
class Plan:
    items: tuple[MenuItem, ...]
    total_price: int
    total_score: float
