---
title: Restore everything from a backup
summary: The whole installation as it was; the maintenance page is shown meanwhile.
group: Backups and recovery
roles: system-admin
screen: #/admin/restores
---

## Why do this

Restoring everything is the last resort after serious loss or damage: all work since the backup is lost, and the maintenance page is up while it runs. A backup of now is taken first. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** The whole installation is back as it was at a backup.

> **Before you start** You need the Super Admin role.

## Steps

1. Open **System Admin › Restores**.
2. Pick the backup; choose **Everything**.
3. Read the warning about the maintenance page and accept it.
4. Type RESTORE to confirm. A backup of now is taken first.
