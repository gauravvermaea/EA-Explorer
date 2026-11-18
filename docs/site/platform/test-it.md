---
title: Test it
summary: The checks before a change, the Python and SQL tests, the self-test, and the rule that every fix has a test.
group: The code
roles: platform-developer
---

## Why so much testing

EA Explorer holds an organisation's record and runs unattended on many machines. A bug that reaches an installation is
expensive to find and fix there. Tests catch it on your machine instead, and a test for every fix stops the same bug
coming back.

## The layers

| Layer | Command | What it checks |
| --- | --- | --- |
| Before anything | `.\eax dev check` (`--quick`, `--web`) | Lint, the Python tests, the documents' cross-checks, the help is ASCII; `--web` builds the screens |
| Python tests | `pytest` in `services/api` | Units and contracts, no database needed |
| Database checks | `tests/sql/phaseN_checks.sql` | Run in a transaction that is rolled back |
| The self-test | `.\eax test smoke` / `full` | The running installation: every role signs in, every page opens, the journeys, security, backups |

## The rule

Every fix comes with a test that fails without the fix and passes with it. Write the test first, watch it fail, then
fix.

## Read next

- [[make-a-change]]
- [[run-the-self-test]]
