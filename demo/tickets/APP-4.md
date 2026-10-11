---
project: demo-app
expect: done
---

# Filter documents by tag

## Description

Every document has tags (for example "guide", "security"), but the list cannot be filtered by them.
Readers of the guides want to see only the guides.

## Acceptance criteria

- Above the list there is one toggle button per tag that occurs in the data, in alphabetical order.
- Selecting a tag shows only documents with that tag. Selecting it again clears the filter.
- Only one tag can be selected at a time.
- The tag filter works together with the title search.
- The behavior is covered by tests.
