---
project: demo-py
expect: done
---

# Moving average for sensor values

## Description

Single readings are noisy. For the trend charts we need a moving average over the last N values.

## Acceptance criteria

- `sensorkit.stats.moving_average(values, window)` returns one average per full window, in order:
  `moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]`.
- When there are fewer values than `window`, the result is an empty list.
- A `window` smaller than 1 raises `ValueError` with a clear message.
- The behavior is covered by tests.
