---
title: Get a token or an API key
summary: A credential for a script or another system, limited to what it needs.
group: Access for systems
roles: developer, system-admin
---

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
