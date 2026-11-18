---
title: What EA Explorer has for platform developers
summary: You change EA Explorer itself: run the whole stack on your machine, find your way round the code, debug, test, and release.
---

## Who this is for

Developers who work on EA Explorer's own code: the API, the screens, the command line, the installer, the reports and
the self-test. Contributors to the open-source project, and teams who extend it for their organisation. (Developers
who connect other systems to EA Explorer have their own page: [[overview|Integrate]].)

## A day in your life

You pick up a change agreed with the owner: a new attribute on a screen, a fix for a failing job, a new MCP tool. You
pull the latest code, start the stack with `eax up`, reproduce the problem as one of the test accounts, read the API's
log by the request id the browser showed, write a test that fails, fix it, run `eax dev check`, update the help and
the decision log, and hand it over with the commands to rebuild.

## Where EA Explorer fits

EA Explorer is an open-source product built to be worked on: one Docker Compose stack that runs the same on a laptop as
on a server, its architecture, decisions and every phase written down in the repository, a check that runs everything
before a change, and a self-test that proves a running installation works. Your local installation is a real one,
with the demo estate and a test account for every role.

## Where you sit in TOGAF

You build the tool, not the architecture, so most of your work is outside the method. But the tool embodies it: the
ADM's phases in projects, the content metamodel, the Architecture Repository. Knowing the map
([[ea-explorer-and-togaf]]) tells you why a screen is shaped the way it is.

## What you have

| What | Where | What it is for |
| --- | --- | --- |
| The code and its documents | The GitHub repository | `AGENTS.md`, `docs/architecture.md`, `docs/handover.md`, `docs/decisions.md` |
| A local installation | `eax init laptop`, `eax up` | The whole stack with demo data and test accounts |
| Debugging | `eax debug`, `eax logs`, `eax diag`, System Admin › Logs | Container output, logs, diagnostics |
| The API explorer | `/api/docs` | Every call, to read and try |
| The checks | `eax dev check`, `pytest`, `eax test smoke` | Before and after every change |

## How it is put together

Containers behind an nginx front door: the React screens, a Flask API with its job runner and MCP server, PostgreSQL,
Keycloak for sign-in, reporting, documents and draw.io, the operations helper and backups. See
[[find-your-way-round-the-code]] and [[running-the-installation]].

## Where to go next

- [[start-here]]
