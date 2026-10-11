---
project: maintenance-board
expect: done
---

# Show urgent work first in each column

## Description

The columns list work orders in the order they were created. A high-priority oil leak can sit at the bottom of
"Open", below routine inspections, and the morning meeting only gets to the top of each column.

## Acceptance criteria

- In every column, high priority comes first, then medium, then low.
- Within the same priority, the earliest due date comes first.
- The search keeps working on the sorted board.
- Covered by tests.
