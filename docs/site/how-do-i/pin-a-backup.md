---
title: Pin a backup
summary: Keep a backup for good: pinned backups are never removed.
group: Backups and recovery
roles: system-admin
screen: #/admin/backups
---

## Why do this

Backups are removed as newer ones arrive. Pinning keeps one for good: the state before an upgrade, the year-end, the day of an audit. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** A backup is kept for good.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Backups**.
2. Find the backup; **Pin**.
3. Unpin it when it is no longer needed.
