---
title: Debug it
summary: Find out what is going wrong: debug mode, logs, diagnostics, the database, the API explorer and the browser.
group: Running locally
roles: platform-developer
---

## Why a routine

Most faults show themselves in one of a few places. Looking in the same order each time finds them fastest.

## The tools

| Tool | What it shows |
| --- | --- |
| `.\eax debug` | Starts like `up` but does not stop on a failure, then records every container's output to `work/logs/containers-<date-time>.log` until Ctrl+C. `.\eax debug api` records the API and database only |
| `.\eax clean-debug` | A clean start ending in debug mode |
| `.\eax logs <service>` | One container's log |
| `.\eax diag` | A diagnostics report: containers, health, recent errors |
| System Admin › Logs, Containers, Health | The same in the screens |
| System Admin › Tools › SQL | Read the database with your sign-in |
| `/api/docs` | Try any API call with your sign-in |
| The browser's developer tools | The screens' console and network calls; each API answer carries a request id that is in the API's log |
| `.\eax test smoke` and Self-test › Watch | The self-test as it runs, with screenshots and video of a failed browser journey |

## A routine that works

1. Reproduce it, and note the time.
2. Health and Containers: is a service down?
3. The browser's network tab: which call failed, with which status and request id?
4. The API's log at that time, by request id.
5. Fix, then add a test that fails without the fix ([[test-it]]).

## Read next

- [[test-it]]
