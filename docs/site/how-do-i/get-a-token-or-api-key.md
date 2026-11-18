---
title: Get a token or an API key
summary: A credential for a script or another system, limited to what it needs.
group: Access for systems
roles: developer, system-admin
screen: #/admin/machine-access
---

## Why do this

A token lets a script or system call the API with limited rights: only the areas and models it needs, for a set time. It is safer than sharing a person's password, and can be revoked at once. See [[bringing-data-in-and-out]].

Systems that talk to EA Explorer need identities of their own, limited to what they do, so their access can be watched and stopped without affecting people. This is part of keeping integration safe as well as useful.

**In TOGAF terms:** Outside the method: this keeps the repository connected to the systems that feed it, so the Architecture Repository stays current. See [[ea-explorer-and-togaf]].

**The goal:** A script or system can call EA Explorer safely.

> **Before you start** Your own token: any signed-in person. A service account's API key or a client certificate: an IT
> Admin or Super Admin.

## Steps

1. Your own: **Me › My tokens and keys**. For a system: **System Admin › Machine access**.
2. **New token**: choose the areas (read or read-write per API area), optionally only some models or projects, and an
   expiry.
3. Copy the secret: it is shown once.
4. Send it with every call as `Authorization: Bearer <token>`. A client certificate, trusted on the same page, signs in
   on the machine-access port instead.

## Check it worked

Machine access shows when each was last used; every call is in the change log.

## If something goes wrong

- Revoke it at once if it leaks; make a new one.

## Related

- [Call the REST API](call-the-rest-api.md)
