---
title: Map a Keycloak role
summary: Turn a directory group into an EA Explorer role.
group: People and access
roles: system-admin
screen: #/admin/users/mapping
---

## Why do this

Mapping a role means people get their EA Explorer access from the groups they are already in, so access follows your organisation's joiners, movers and leavers without manual work. See [[roles-and-access]].

Access in EA Explorer is layered so each owner decides for their own part: System Admins for the installation, Model Admins for models, Project Admins for projects. Most people need only a few roles to do their work.

**In TOGAF terms:** The Preliminary phase's architecture capability: who does architecture work and with what authority. Sign-in itself is outside the method. See [[ea-explorer-and-togaf]].

**The goal:** A directory group gives an EA Explorer role automatically.

> **Before you start** You need the User Admin role.

## Steps

1. Open **System Admin › Users and roles**, **Map a Keycloak role**.
2. Pick the group and the role.
3. **Save**; people in the group get the role at their next sign-in.

## Related

- [Map directory groups to roles](map-directory-groups-to-roles.md)
