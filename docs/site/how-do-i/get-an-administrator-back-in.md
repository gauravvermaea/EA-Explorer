---
title: Get an administrator back in
summary: A forgotten password, a locked account or a lost phone, sorted from the machine.
group: Security
roles: system-admin
---

> **Before you start** You need to be on the machine EA Explorer runs on. This is only for the administrators; everyone
> else is helped by an administrator in Keycloak.

## Steps

1. `eax access admins` lists the administrators, and whether each is enabled.
2. **A forgotten password**: `eax access reset-password <user name>` gives a temporary password, shown once; it must
   be changed at the next sign-in.
3. **Locked out after wrong passwords**: `eax access unlock <user name>`.
4. **A lost phone**: `eax access mfa-off <user name>` removes the authenticator; a new one is set up at the next
   sign-in.
5. **Sign-in itself is down**: the break-glass page (`/#/break-glass`) signs in with the break-glass password, kept
   offline by the Super Admins.

## Related

- [Install and run: A forgotten password or certificate](../install/forgotten.html)
