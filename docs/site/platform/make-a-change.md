---
title: Make a change
summary: The pattern for a new feature from the database to the screen, and what "done" means.
group: The code
roles: platform-developer
---

## The pattern

1. **Agree it first**: what, why, and the decision it needs (a new number in `docs/decisions.md`).
2. **Reads** go in `repository.py` (one function per question); **writes** in a module of their own, in one transaction,
   audited, with a dry run where the change is big.
3. **Expose it** from a blueprint in `eax/api/` with marshmallow schemas; wrap it in `require_auth(permission)`.
4. **An MCP tool** in `mcp_server.py` when an agent would use it.
5. **A screen** in `services/web/src`, its menu entry in `menu.js`, its help in `help/catalogue.json`.
6. **The command line**, if it has one: `eaxcli`, the three launchers, `help.txt`.
7. **Tests**, then the documents.

## Who may do it

Every view checks permission first (403). The signed-in person is set on each database connection, and row-level
security and triggers apply the same rules, so every route (screens, API, MCP, SQL) obeys them.

## Definition of done

Tests pass; `docs/decisions.md`, the capabilities and phase notes current; the help (`help.txt`, the help catalogue)
and this website's pages updated; the release notes say what changed; no file over 50 MB.

## Read next

- [[database-changes-and-versions]]
