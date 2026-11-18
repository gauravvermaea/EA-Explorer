---
title: Revoke a token or API key
summary: Calls with it are refused at once.
group: Access for systems
roles: developer, system-admin, user
screen: #/admin/machine-access
---

## Why do this

When a token may have leaked, or the system using it is retired, revoking it stops every call with it immediately.

Systems that talk to EA Explorer need identities of their own, limited to what they do, so their access can be watched and stopped without affecting people. This is part of keeping integration safe as well as useful.

**In TOGAF terms:** Outside the method: this keeps the repository connected to the systems that feed it, so the Architecture Repository stays current. See [[ea-explorer-and-togaf]].

**The goal:** A token can no longer be used, at once.

## Steps

1. Open **Home › My tokens and keys** (or Machine access for a service account).
2. Find it; **Revoke**.
3. Confirm; it cannot be used again.
