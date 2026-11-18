---
title: Restore part of the installation
summary: The databases, the files or the config, from a backup.
group: Backups and recovery
roles: system-admin
screen: #/admin/restores
---

## Why do this

Damage is often partial: a database corrupted, files deleted, a setting broken. Restoring only that part from a backup fixes it while everything else (including work done since) stays as it is. A backup of now is taken first, and the maintenance page warning is shown before it starts. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** The databases, the files or the config are back from a backup.

> **Before you start** You need the Super Admin role.

## Steps

1. Open **System Admin › Restores**.
2. Pick the backup; tick the parts: databases, files or config.
3. Read the maintenance page warning and accept it; type RESTORE. A backup of now is taken first.
