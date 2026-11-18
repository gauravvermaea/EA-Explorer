---
title: Set who may reach EA Explorer by address
summary: The network addresses allowed in.
group: Security
roles: system-admin
screen: #/admin/security
---

## Why do this

The allow list limits which addresses can reach the site or its sensitive parts, adding a network layer to sign-in. See [[roles-and-access]].

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** Only trusted networks reach EA Explorer.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Security**.
2. Add the addresses or ranges allowed; check that yours is in.
3. **Save**.

## Related

- [Limit who can reach EA Explorer](limit-who-can-reach-ea-explorer.md)
