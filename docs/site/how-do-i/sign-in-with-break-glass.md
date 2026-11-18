---
title: Sign in with break glass
summary: When sign-in itself is down: the break-glass password.
group: Security
roles: system-admin
screen: #/break-glass
---

## Why do this

If Keycloak itself fails, nobody can sign in the usual way. The break-glass password, kept safe outside EA Explorer, gets an administrator in to fix it; every use is logged.

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** You can get in when normal sign-in is down.

> **Before you start** You need the break-glass password.

## Steps

1. Open `https://<your EA Explorer address>/#/break-glass`.
2. Give the break-glass password, kept safe outside EA Explorer.
3. Fix sign-in; every break-glass sign-in is logged.
