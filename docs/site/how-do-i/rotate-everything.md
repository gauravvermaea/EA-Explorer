---
title: Rotate every password and key
summary: Every one changed together, behind the maintenance page.
group: Security
roles: system-admin
screen: #/admin/secrets
---

## Why do this

Rotating every secret limits the damage of any that leaked, and is often required by policy or after staff leave. It runs behind the maintenance page, so it warns first. See [[running-the-installation]].

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** Every password and key is new.

> **Before you start** You need the Super Admin role.

## Steps

1. Open **System Admin › Secrets**, **Rotate all**.
2. Read the maintenance page warning and accept it.
3. Restart when asked. On Windows: `eax secrets rotate --all --restart` from PowerShell.
