---
title: Schedule a command
summary: An eax command that runs by itself: a nightly backup, a weekly check, or once at a time.
group: Running it
roles: system-admin
screen: #/admin/commands
---

## Why do this

Backups, checks and exports are best run on a schedule. The command centre runs an eax command nightly, weekly or once, and keeps every run's history. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** A command runs by itself when it should.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Tools › Command centre**, **Schedules**.
2. **New schedule**: choose the command and its options, then when it runs: every night, every week, every hour, once,
   or a cron line. Times are in the installation's time zone.
3. A command that deletes everything needs a Super Admin and the installation's name, once, when the schedule is made.
4. **Save**. Every run is in the History.

## Check it worked

The schedule shows its next run; after it runs, its last result.

## Related

- [Take a backup and check it](../guides/take-and-check-a-backup.md)
