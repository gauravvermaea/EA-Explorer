---
title: Set up a DR site
summary: A second EA Explorer kept up to date with this one, read only, ready to take over.
group: Backups and recovery
roles: system-admin
---

> **Before you start** You need the Super Admin role on both sites, and a second installation of the same release
> (see Install and run: A server).

## Steps

1. **On the DR site**: System Admin › Running › Site pairings, **Make a key**. It is shown once: copy it.
2. **On this site**: the same page, **Pair with a site**: the DR site's address, the key, and **DR sync**.
3. **On the DR site**: accept the pairing. It becomes read only and is kept up to date by itself.
4. Rehearse now and then with the restore drill (System Admin › Backups and restores › Disaster recovery).

## Check it worked

Both sites show the pairing as paired; the batches list what was sent and committed.

## If the primary is lost

On the DR site: the DR pairing, **Stop and take over**. Then point the name people open at the DR site.

## Related

- [Install and run: A DR site](../install/dr-site.html)
- [Install and run: Switching to DR and back](../install/switch-to-dr.html)
