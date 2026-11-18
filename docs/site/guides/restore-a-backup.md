---
title: Restore a backup
summary: Put back a model, a project, part of the installation or all of it, from a backup.
group: Backups and recovery
roles: system-admin, model-admin, project-admin
---

## Why do this

Restores range from one entity to the whole installation. Choosing the smallest scope that fixes the problem keeps everything else as it is. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** What was lost or damaged is back, at the right scope.

> **Before you start** Restoring the installation needs the Super Admin or IT Admin role; a model needs its Model Admin;
> a project its Project Admin. Take a backup first, so you can go back.

> **Careful** Restoring the whole installation puts back everything as it was at the backup: work done since is lost.
> EA Explorer is read only while it runs.

## The ways to do it

1. **A model**: Model Admin › Wizards on the model, **Restore a tag**, or its backups to restore it over itself or as a
   new model.
2. **A project**: the project's About tab, **Back up and restore**.
3. **Part of the installation** (the databases, the files or the config): System Admin › Backups and restores ›
   Backups, the backup, **Restore**, and choose the part. On the machine: `eax restore <backup> --what db`.
4. **Everything**: the same, choosing everything. On the machine: `eax restore <backup> --what full`.

## Check it worked

System Admin › Backups and restores › Restores shows each restore and its log. After a restore the database integrity
check runs by itself (System Admin › Running › Database maintenance).

## If something goes wrong

- Read the restore's log on the Restores page; it says which step stopped and why.
- `eax status` on the machine shows every container; `eax restart` brings them up again.

## Each task, one page

1. [Put a model back to a tag](../how-do-i/go-back-to-a-tag.md)
2. [Restore one model from a backup](../how-do-i/restore-one-model.md)
3. [Restore a project](../how-do-i/restore-a-project.md)
4. [Restore a project from a backup file](../how-do-i/restore-a-project-from-a-file.md)
5. [Restore part of the installation](../how-do-i/restore-part-of-the-installation.md)
6. [Restore everything from a backup](../how-do-i/restore-everything.md)
7. [Run a restore drill](../how-do-i/run-a-restore-drill.md)

## Related

- [Take a backup and check it](../guides/take-and-check-a-backup.md)
- [Install and run: Restores](../install/restores.html)
