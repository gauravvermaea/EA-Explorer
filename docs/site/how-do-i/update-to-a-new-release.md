---
title: Update to a new release
summary: Move EA Explorer to a newer release, with a full backup first and a way back.
group: Running it
roles: system-admin
---

> **Before you start** You need the Super Admin or IT Admin role. Read the release's notes: they say what changes and
> anything to do before.

## Steps

1. Open **System Admin › Updates**. It shows the version installed and the newer releases offered, each with its notes.
2. Choose the release and **Update now**, or at a time (a banner tells people beforehand).
3. EA Explorer takes a pinned full backup first, then moves one release at a time.

On the machine: `eax update --list` shows what is offered; `eax update` moves to the newest.

## Check it worked

The version at the top left of every screen changes; everyone sees **What's new** once. Run the smoke test
(System Admin › Tools › Self-test, or `eax test smoke`).

## If something goes wrong

- A failed step stops and asks: **Retry** or **Roll back**. On the machine: `eax rollback` goes back to the release
  before, with its data as it was.

## Related

- [Run the self-test](run-the-self-test.md)
- [Releases](../releases/index.html)
