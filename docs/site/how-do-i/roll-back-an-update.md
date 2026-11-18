---
title: Roll back an update
summary: The backup from before the update put back: code, data and settings.
group: Backups and recovery
roles: system-admin
screen: #/admin/updates
---

## Why do this

If an update causes problems, rolling back puts back the backup taken just before it: code, data and settings. Work done since the update is lost, so it warns and waits for you. See [[running-the-installation]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** EA Explorer is back on the release before the update.

> **Before you start** You need the Super Admin role.

## Steps

1. Open **System Admin › Updates**, **Roll back**.
2. Read what is lost (work since the update) and the maintenance page warning; accept it.
3. Confirm.
