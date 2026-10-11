---
project: maintenance-board
expect: done
---

# Work orders due today are marked "Overdue"

## Description

A work order that is due today already shows the red "Overdue" badge. Planners then chase technicians about work
that is not late yet, and the work orders that really are late get lost among them.

Steps to reproduce: open the board on the due date of an open work order, for example WO-1004 on 2026-10-14.

- Expected: "Due today", in the same amber as "Due tomorrow".
- Actual: "Overdue", in red.

## Acceptance criteria

- An open or in-progress work order shows "Due today" on its due date.
- "Overdue" starts the day after the due date.
- The other badges ("Due tomorrow", "Due in N days" and later dates) stay as they are.
- A test covers the due date itself, so this cannot come back unnoticed.
