---
project: maintenance-board
expect: done
---

# Filter the board by machine

## Description

In the morning meeting the planner goes through the board machine by machine. With a dozen work orders on the
board, picking out the ones for one machine takes too long.

## Acceptance criteria

- Next to the search box there is a select labelled "Machine". Its first option, "All machines", is the default;
  then one option per machine, by name.
- Choosing a machine shows only that machine's work orders, in all three columns. The column counts match what is
  shown.
- The machine filter and the search work together.
- Covered by tests.
