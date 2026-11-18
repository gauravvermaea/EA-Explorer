---
title: Upload your organisation's certificate
summary: Your own certificate on the front door, used at once.
group: Security
roles: system-admin
screen: #/admin/secrets
---

## Why do this

Your organisation's own certificate on the front door removes browser warnings and meets security policy. It is checked and used at once, and the previous one is kept.

Security in EA Explorer is a set of layers: who can reach it, how they prove who they are, what their roles allow, and secrets no one can read. Each layer is set on the screens, and nothing here ever shows a secret's value.

**In TOGAF terms:** Outside the method: this protects the repository and who reaches it. See [[ea-explorer-and-togaf]].

**The goal:** People see your organisation's certificate when they open EA Explorer.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Secrets**.
2. **Front door certificate**: upload the certificate and its key.
3. Read the checks; **Use it**. The one before is kept.
