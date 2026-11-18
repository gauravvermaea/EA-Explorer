---
title: Check the health and alerts
summary: See whether every part of EA Explorer is up, what is wrong, and who is told.
group: Running it
roles: system-admin
---

## Why do this

A repository people rely on must be available. Health, alerts and logs together tell you what is wrong and where; this guide shows how they fit. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** You know EA Explorer is healthy and hear quickly when it is not.

> **Before you start** You need the Super Admin, IT Admin or Auditor role.

## The ways to do it

1. The dot in the top bar shows the overall health at a glance: green, amber or red.
2. **System Admin › Running › Health**: every part (the API, the databases, sign-in, reports, documents and the rest);
   open a red one to see why.
3. **System Admin › Running › Alerts**: the checks that run every minute (each service, the disks, memory, the
   certificate, the database, errors in the web log, the self-test) and the open alerts. Alerts go to the IT Admins and
   Super Admins, the webhooks and by email.
4. Acknowledge an alert to stop it repeating, or silence a check during planned work.

On the machine: `eax status` shows every container, the disks and what is running.

## If something goes wrong

- **A service keeps restarting**: System Admin › Running › Containers, the service, its log.
- **Everything is down**: on the machine, `eax status`, then `eax restart`.

## Each task, one page

1. [See the health of every part](../how-do-i/see-the-health-of-every-part.md)
2. [Set up alerts](../how-do-i/set-up-alerts.md)
3. [Acknowledge an alert](../how-do-i/acknowledge-an-alert.md)
4. [Silence a check during planned work](../how-do-i/silence-a-check.md)
5. [See the containers](../how-do-i/see-the-containers.md)
6. [Read the logs](../how-do-i/read-the-logs.md)

## Related

- [Run the self-test](../how-do-i/run-the-self-test.md)
