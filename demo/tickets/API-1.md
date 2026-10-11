---
project: demo-api
expect: done
---

# Filter work orders by machine

## Description

The maintenance planner opens one machine at a time and needs only the work orders of that machine.

## Acceptance criteria

- `GET /work-orders?machineId=M-2` returns only the work orders of machine M-2.
- `machineId` combines with the existing `status` filter and with paging; `total` counts the filtered list.
- An unknown machine id returns 404 with `{ "error": "Machine not found" }`.
- The behavior is covered by tests.
