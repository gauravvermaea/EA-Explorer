---
title: Rotate passwords and keys on a schedule
summary: Every one changed monthly, every three months, or once at a time.
group: Security
roles: system-admin
screen: #/admin/secrets
---

## Why do this

Regular rotation limits how long a leaked secret is useful. Scheduling it means it happens without anyone remembering, with the maintenance page warning when it runs.

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** Passwords and keys change on a schedule.

> **Before you start** You need the Super Admin role.

## Steps

1. Open **System Admin › Secrets**, **Schedule**.
2. Choose monthly, every three months, or one time.
3. **Save**; the maintenance page warning is shown when it runs.
