---
title: Running the installation
summary: What EA Explorer is made of, what keeps it healthy, and the jobs a System Admin owns.
group: Running it
roles: system-admin, developer
---

## What it is made of

EA Explorer runs as a set of containers on one machine or several: the screens and the front door, the API and its
job workers, the database, Keycloak for sign-in, reporting, documents, draw.io, the AI server and the operations
helper. Everything is open source and runs on your own servers or laptop. See [[see-the-estate]] and [[see-the-containers]].

## Keeping it healthy

- **Health and alerts**: a dot in the top bar, every part's state, checks every minute ([[check-health-and-alerts]]).
- **Backups**: taken on a schedule, checked by restoring ([[take-and-check-a-backup]], [[backups-and-recovery]]).
- **Secrets**: every password and key a file, rotated when you choose ([[rotate-passwords-and-keys]]).
- **Updates**: one release at a time, a pinned backup first, a roll back if needed ([[update-to-a-new-release]]).
- **The self-test**: the installation tests itself in its own fixtures ([[run-the-self-test]]).

Anything that puts the maintenance page up warns first and waits for you to accept.

## Read next

- [[backups-and-recovery]]
- [[follow-a-setup-guide]]
