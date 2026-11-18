---
title: Set up a DR site
summary: A second EA Explorer kept up to date with this one, read only, ready to take over.
group: Backups and recovery
roles: system-admin
---

## Why do this

A disaster recovery site is kept up to date from the main one and can take over if the main site is lost. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** A second site is ready to take over.

> **Before you start** You need the Super Admin role on both sites, and a second installation of the same release
> (see Install and run: A server).

## The ways to do it

1. **On the DR site**: System Admin › Running › Site pairings, **Make a key**. It is shown once: copy it.
2. **On this site**: the same page, **Pair with a site**: the DR site's address, the key, and **DR sync**.
3. **On the DR site**: accept the pairing. It becomes read only and is kept up to date by itself.
4. Rehearse now and then with the restore drill (System Admin › Backups and restores › Disaster recovery).

## Check it worked

Both sites show the pairing as paired; the batches list what was sent and committed.

## If the primary is lost

On the DR site: the DR pairing, **Stop and take over**. Then point the name people open at the DR site.

## Each task, one page

1. [Make a pairing key](../how-do-i/make-a-pairing-key.md)
2. [Pair two sites](../how-do-i/pair-two-sites.md)
3. [Accept a pairing on the receiving site](../how-do-i/accept-a-pairing.md)
4. [Run a restore drill](../how-do-i/run-a-restore-drill.md)
5. [Switch to the DR site](../how-do-i/switch-to-the-dr-site.md)

## Related

- [Install and run: A DR site](../install/dr-site.html)
- [Install and run: Switching to DR and back](../install/switch-to-dr.html)
