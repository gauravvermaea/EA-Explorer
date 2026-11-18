---
title: Set when backups are taken
summary: The time of each kind of backup and how many are kept.
group: Backups and recovery
roles: system-admin
screen: #/admin/backups
---

## Why do this

The schedule decides when each kind of backup runs and how many are kept. It balances how much work you could lose against the space backups take. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** Backups happen when they should, and enough are kept.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Backups**.
2. Open a kind's schedule: set the time and how many to keep.
3. **Save**. Pinned backups are never removed.
