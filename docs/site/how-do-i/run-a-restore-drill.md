---
title: Run a restore drill
summary: Prove a backup restores, on a separate copy, without touching the live site.
group: Backups and recovery
roles: system-admin
screen: #/admin/disaster-recovery
---

## Why do this

A drill restores a backup onto a separate copy and checks it, so you know recovery works before you ever need it. It is the honest test of a backup. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** You know a backup restores, on a copy, without touching the live site.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Disaster recovery**.
2. **Restore drill**: pick the backup.
3. Read the report; the DR copy is left running for you to look at.
