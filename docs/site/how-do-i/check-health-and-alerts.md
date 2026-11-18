---
title: Check the health and alerts
summary: See whether every part of EA Explorer is up, what is wrong, and who is told.
group: Running it
roles: system-admin
---

> **Before you start** You need the Super Admin, IT Admin or Auditor role.

## Steps

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

## Related

- [Run the self-test](run-the-self-test.md)
