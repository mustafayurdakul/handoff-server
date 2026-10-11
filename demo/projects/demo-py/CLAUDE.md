# demo-py (sensorkit)

A small Python library and command line tool for machine sensor readings. Python 3.11+, standard library only.

## Structure

- `sensorkit/readings.py`: `Reading`, `parse()` for CSV text (`timestamp,sensor,value` with a header row), `by_sensor()`.
- `sensorkit/stats.py`: `Summary`, `summary()` over a list of values, `alarms()` for readings outside a range.
- `sensorkit/__main__.py`: `python -m sensorkit FILE.csv` prints a summary per sensor.
- Tests: `tests/test_<module>.py`, one file per module.

## Conventions

- Standard library only at runtime. Do not add dependencies: in the pipeline, setup runs before coding.
- Type hints on public functions, a one-line docstring on each public function.
- Errors that a user can fix raise `ValueError` with a message that says what is wrong and where.

## Tests

- pytest, plain `assert`, `pytest.raises` for errors.
- Commands: `.venv/bin/ruff check .` and `.venv/bin/pytest -q`.
