---
project: demo-api
expect: done
---

# Bug: the first page of work orders skips the first items

## Description

`GET /work-orders?page=1&limit=2` should return work orders 1 and 2, but it returns 3 and 4.
The planner board therefore never shows the oldest open work orders.

## Acceptance criteria

- Page 1 starts with the first matching work order; page 2 continues right after page 1.
- A page beyond the end returns an empty `items` list with the correct `total`.
- A test reproduces the bug: it fails before the fix and passes after it.
