"""Reading sensor CSV files: one `timestamp,sensor,value` row per reading, with a header row."""
import csv
from dataclasses import dataclass
from datetime import datetime
from io import StringIO


@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    sensor: str
    value: float


def parse(text: str) -> list[Reading]:
    """Parse CSV text. A value that is not a number raises ValueError with the line number."""
    rows = csv.DictReader(StringIO(text))
    readings = []
    for line, row in enumerate(rows, start=2):
        try:
            value = float(row["value"])
        except ValueError:
            raise ValueError(f"line {line}: value {row['value']!r} is not a number") from None
        readings.append(Reading(datetime.fromisoformat(row["timestamp"]), row["sensor"], value))
    return readings


def by_sensor(readings: list[Reading]) -> dict[str, list[Reading]]:
    """Group readings by sensor name, keeping their order."""
    groups: dict[str, list[Reading]] = {}
    for r in readings:
        groups.setdefault(r.sensor, []).append(r)
    return groups
