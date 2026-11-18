---
title: Restore a project
summary: A project put back from its backup, over itself or as a new project.
group: Backups and recovery
roles: project-admin
screen: #/projects/{p}/home
---

## Why do this

When a project has gone wrong, restoring from its backup puts it back; restoring as a new project lets you look at the old state beside the current one. A backup of now is taken first. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** A project is back as it was at a backup.

> **Before you start** You need the Project Admin role on the project.

## Steps

1. Open the project, **Home**, its backups.
2. **Restore**: over itself, or **Restore as a new project** and name it.
3. Confirm. A backup of now is taken first.
