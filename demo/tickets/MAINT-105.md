---
project: maintenance-board
expect: rejected
---

# Offline mode with two-way SAP PM sync

## Description

The tablets in hall 2 lose Wi-Fi for hours at a time. The board has to keep working offline: technicians change
the status of work orders, add notes and photos, and when the connection is back, every change syncs both ways
with SAP PM, including when the planner changed the same work order in the meantime.

## Acceptance criteria

- The board works fully offline (service worker and a local database).
- Two-way sync with SAP PM notifications and orders through its OData API, with retries and conflict resolution.
- Photos are uploaded to the document management system and linked to the SAP order.
- Sign-in with the plant's single sign-on.
