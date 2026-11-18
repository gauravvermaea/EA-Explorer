---
title: Get an administrator back in
summary: A forgotten password, a locked account or a lost phone, sorted from the machine.
group: Security
roles: system-admin
---

## Why do this

Lockouts happen: a forgotten password, too many attempts, a lost phone, sign-in itself down. Each has its own safe fix from the machine. See [[roles-and-access]].

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** An administrator who cannot sign in is back in, safely.

> **Before you start** You need to be on the machine EA Explorer runs on. This is only for the administrators; everyone
> else is helped by an administrator in Keycloak.

## The ways to do it

1. `eax access admins` lists the administrators, and whether each is enabled.
2. **A forgotten password**: `eax access reset-password <user name>` gives a temporary password, shown once; it must
   be changed at the next sign-in.
3. **Locked out after wrong passwords**: `eax access unlock <user name>`.
4. **A lost phone**: `eax access mfa-off <user name>` removes the authenticator; a new one is set up at the next
   sign-in.
5. **Sign-in itself is down**: the break-glass page (`/#/break-glass`) signs in with the break-glass password, kept
   offline by the Super Admins.

## Each task, one page

1. [List the administrators](../how-do-i/list-the-administrators.md)
2. [Reset an administrator's password](../how-do-i/reset-an-administrators-password.md)
3. [Unlock an administrator](../how-do-i/unlock-an-administrator.md)
4. [Remove a lost authenticator](../how-do-i/remove-a-lost-authenticator.md)
5. [Sign in with break glass](../how-do-i/sign-in-with-break-glass.md)

## Related

- [Install and run: A forgotten password or certificate](../install/forgotten.html)
