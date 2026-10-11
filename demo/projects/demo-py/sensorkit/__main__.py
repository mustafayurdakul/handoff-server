"""Command line: python -m sensorkit FILE.csv prints a summary per sensor."""
import sys
from pathlib import Path

from .readings import by_sensor, parse
from .stats import summary


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m sensorkit FILE.csv", file=sys.stderr)
        return 2
    for sensor, readings in by_sensor(parse(Path(argv[0]).read_text())).items():
        s = summary([r.value for r in readings])
        print(f"{sensor}: count={s.count} min={s.min:.2f} max={s.max:.2f} mean={s.mean:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
