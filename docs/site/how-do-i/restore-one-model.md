---
title: Restore one model from a backup
summary: One model put back; the rest untouched.
group: Backups and recovery
roles: system-admin, model-admin
screen: #/admin/restores
---

## Why do this

When one model is damaged beyond what its tags can fix, restoring it from a backup puts it back without affecting other models or projects. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** One model is back from a backup; everything else is untouched.

> **Before you start** You need the Super Admin or IT Admin role. A Model Admin restores their own model from its tags.

## Steps

1. Open **System Admin › Restores**.
2. Pick the backup and the model.
3. Type RESTORE to confirm. The model is backed up first.

## Related

- [Restore a backup](../guides/restore-a-backup.md)
