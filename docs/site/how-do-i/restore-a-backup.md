---
title: Restore a backup
summary: Put back a model, a project, part of the installation or all of it, from a backup.
group: Backups and recovery
roles: system-admin, model-admin, project-admin
---

> **Before you start** Restoring the installation needs the Super Admin or IT Admin role; a model needs its Model Admin;
> a project its Project Admin. Take a backup first, so you can go back.

> **Careful** Restoring the whole installation puts back everything as it was at the backup: work done since is lost.
> EA Explorer is read only while it runs.

## Steps

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

## Related

- [Take a backup and check it](take-and-check-a-backup.md)
- [Install and run: Restores](../install/restores.html)
