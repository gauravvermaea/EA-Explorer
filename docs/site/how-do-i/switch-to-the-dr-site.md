---
title: Switch to the DR site
summary: Stop following and take over on the DR site.
group: Backups and recovery
roles: system-admin
screen: #/admin/pairings
---

## Why do this

When the main site cannot be brought back quickly, the DR site stops following and becomes the main site. People are pointed at its address. See [[backups-and-recovery]].

Recovery is planned before it is needed: what to protect, how often, how to check it, and how far back each kind of restore reaches. EA Explorer takes a backup of now before any restore, so a restore can itself be undone.

**In TOGAF terms:** Outside the method: this protects the Architecture Repository itself, the record every ADM phase relies on. See [[ea-explorer-and-togaf]].

**The goal:** The DR site takes over when the main site is lost.

> **Before you start** You need the Super Admin role.

## Steps

1. On the DR site: **System Admin › Site pairings**.
2. **Stop and take over**: read what happens; accept.
3. Point people at the DR site's address.
