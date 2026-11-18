---
title: Run the self-test
summary: Check the installation works: the smoke test in a few minutes, or the full test.
group: Running it
roles: system-admin
---

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Tools › Self-test**.
2. **Smoke test**: every role signs in, every main area answers, every page opens and the key journeys work once (a
   few minutes). **Full test**: every API endpoint as every role, the database, security, and every page and journey
   in a browser.
3. Start it. It makes its own test data, tests, writes a report and removes what it made; nothing else changes.

On the machine: `eax test` (smoke) or `eax test full`.

## Check it worked

The run ends **Passed**. Its History entry has the report; each failure says what was asked and what came back.

## If something goes wrong

- **Run the failed ones again**: History, the run, or `eax test failed`: only what failed, showing each check then and
  now.

## Related

- [Check the health and alerts](check-health-and-alerts.md)
