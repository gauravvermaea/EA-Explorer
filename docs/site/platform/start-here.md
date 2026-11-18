---
title: Working on EA Explorer itself: start here
summary: For developers changing EA Explorer: get the code, run it on your machine, find your way round, and the rules the project keeps.
group: Start here
roles: platform-developer
---

## Who this is for

People who change EA Explorer itself: fixing a bug, adding a screen, a report, an API call or an MCP tool, improving
the installer. (If you connect other systems to EA Explorer, see [[overview|integrating with EA Explorer]] instead.)

## The route

1. [[get-the-code]]: the repository and what is in it.
2. [[run-it-on-your-machine]]: a full installation on your laptop with Docker.
3. [[find-your-way-round-the-code]]: the services, the API, the screens, the command line.
4. [[debug-it]]: logs, the debug mode, the database, the browser.
5. [[test-it]]: the checks before a change, the tests, the self-test.
6. [[make-a-change]]: the pattern for a feature and the definition of done.
7. [[database-changes-and-versions]]: migrations and the version.
8. [[release-it]]: how a version reaches installations.

## The rules the project keeps

- Discuss before building; build what was asked; bugs before features; every fix has a test that fails without it.
- No platform-specific code: it runs the same on a laptop, a server and a container platform.
- No logic in the database: tables and rows in migrations only; the code decides.
- `eax.ps1`, `eax.sh`, `eaxcli/` and `eaxcli/help.txt` stay in step; `eax.ps1` and `help.txt` are plain ASCII.
- Plain British English in everything people read; no other EA platform or vendor named; no copyrighted text.
- Done means tests, documents, help, the help catalogue and the release notes, all current.

## Read next

- [[get-the-code]]
