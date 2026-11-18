---
title: Take a backup now
summary: A backup straight away, with a tag that says why.
group: Backups and recovery
roles: system-admin, model-admin
screen: #/admin/backups
---

## Why do this

Scheduled backups cover the normal case. Taking one now, with a tag that says why, is the habit that makes an upgrade, a big load or a restructure safe: if anything goes wrong, you can go back to just before it. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** A fresh backup exists before something risky.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Backups**, **Back up now**.
2. Give it a tag (why).
3. **Back up now**; it runs in the background.
