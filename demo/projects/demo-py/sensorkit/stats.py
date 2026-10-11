"""Statistics over sensor values."""
from dataclasses import dataclass

from .readings import Reading


@dataclass(frozen=True)
class Summary:
    count: int
    min: float
    max: float
    mean: float


def summary(values: list[float]) -> Summary:
    """Count, minimum, maximum and mean of the values."""
    mean = sum(values) / len(values)
    return Summary(count=len(values), min=min(values), max=max(values), mean=mean)


def alarms(readings: list[Reading], low: float, high: float) -> list[Reading]:
    """Readings outside the allowed range [low, high]."""
    return [r for r in readings if r.value < low or r.value > high]
