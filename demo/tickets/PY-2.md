---
project: demo-py
expect: done
---

# Bug: the summary crashes when a sensor has no readings

## Description

`sensorkit.stats.summary([])` raises `ZeroDivisionError`. This happens for a sensor that was offline
for the whole export, and it stops the nightly report for all other sensors too.

## Acceptance criteria

- `summary([])` returns a `Summary` with `count == 0` and `None` for `min`, `max` and `mean`.
- The type hints of `Summary` show that these fields can be `None`.
- The command line prints `count=0` and `n/a` for the other values of such a sensor.
- A test reproduces the bug: it fails before the fix and passes after it.
