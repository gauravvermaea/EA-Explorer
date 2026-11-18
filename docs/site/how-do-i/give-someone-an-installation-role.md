---
title: Give someone a role on the installation
summary: User, Model Creator, Auditor, IT Admin and the other global roles.
group: People and access
roles: system-admin
screen: #/admin/users
---

## Why do this

Installation roles apply everywhere: User for everyone who signs in, and roles such as Model Creator, Auditor or IT Admin for wider work. They are given in Keycloak, or mapped from your directory's groups. See [[roles-and-access]].

Access in EA Explorer is layered so each owner decides for their own part: System Admins for the installation, Model Admins for models, Project Admins for projects. Most people need only a few roles to do their work.

**In TOGAF terms:** The Preliminary phase's architecture capability: who does architecture work and with what authority. Sign-in itself is outside the method. See [[ea-explorer-and-togaf]].

**The goal:** A person has the roles their work across EA Explorer needs.

> **Before you start** You need the User Admin or Keycloak Admin role.

## Steps

1. In Keycloak, open the person; **Role mapping**.
2. **Assign role**: for most people **user**; others as their work needs.
3. They have it at their next sign-in.
