---
title: Get the code
summary: Where the code lives, how it is laid out, and the documents to read first.
group: Start here
roles: platform-developer
---

## Why read before running

EA Explorer is a large, documented project. A few minutes with its own guides saves hours: they say how the owner
works, why things are as they are, and what state each part is in.

## The repository

The code is on GitHub (the link is at the foot of every page of this site). Clone it with git. The top level:

| Folder | What it holds |
| --- | --- |
| `services/api` | The Python API, job runner, MCP server, migrations, tests |
| `services/web` | The React screens (Vite), the nginx that serves them, this website's built copy |
| `services/ops`, `services/backup` | The operations helper and the backup service |
| `eaxcli/` | The `eax` command in Python (with `eax.ps1`, `eax.sh` and `eaxpy` launchers at the top) |
| `deploy/` | Compose files, templates, Keycloak realm, proxy, Jenkins, reports |
| `tools/` | Builders such as this website's |
| `docs/` | Architecture, database, decisions, phases, guides, this site's sources |
| `releases/` | Every release's notes |

## Read these first

1. `AGENTS.md`: how the owner works and the rules the product keeps.
2. `docs/architecture.md`: the containers, the code layout, the pattern for a feature.
3. `docs/handover.md`: where the work stands.
4. `docs/decisions.md`: every decision, numbered, with its reasons.

## Read next

- [[run-it-on-your-machine]]
