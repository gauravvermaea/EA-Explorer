---
title: Check a backup restores
summary: Restore the newest backup into scratch copies and compare; nothing live changes.
group: Backups and recovery
roles: system-admin
screen: #/admin/backups
---

## Why do this

A backup is only as good as the restore it makes possible. Checking puts the newest backup into scratch copies and compares, without touching the live site, so you find out now rather than on the day you need it. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** You know your newest backup really restores.

> **Before you start** You need to run commands on the machine.

## Steps

1. On the machine: `eax verify`.
2. Read the result: each database and the files compared.
3. A failure says which part; take a new backup and verify again.
