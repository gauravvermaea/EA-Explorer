---
title: Rotate one password or key
summary: A new value for one password, key or certificate.
group: Security
roles: system-admin
screen: #/admin/secrets
---

## Why do this

If a password or key may have been exposed (pasted in the wrong place, held by someone who left), rotating it at once closes that door. Only the services that use it start again, so the rest of EA Explorer carries on undisturbed. See [[running-the-installation]].

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** One password or key is new.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Secrets**.
2. Find it by name; **Rotate**.
3. Confirm; what uses it is restarted if needed.

## Related

- [Rotate passwords and keys](../guides/rotate-passwords-and-keys.md)
