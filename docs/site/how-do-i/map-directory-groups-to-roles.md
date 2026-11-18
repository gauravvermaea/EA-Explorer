---
title: Map directory groups to roles
summary: Make a Keycloak role or a directory group give an EA Explorer role, so people get their roles from the groups they are already in.
group: People and access
roles: system-admin
---

> **Before you start** You need the User Admin or Super Admin role. Your directory (Active Directory or another LDAP, or
> your identity provider) is connected to Keycloak.

## Steps

1. Open **System Admin › Users and roles › Keycloak role mapping**.
2. Choose the Keycloak role or directory group, and the EA Explorer global role it gives (for example the group
   *EA-Architects* gives **user**, *EA-Admins* gives **it-admin**).
3. **Add**. The mapping applies at each person's next sign-in.

## Check it worked

A person in that group signs in again; System Admin › Users and roles shows the role on them, with where it came from.

## If something goes wrong

- **Nothing changed for the person**: they must sign out and in again. Check the group name is exactly as Keycloak
  sees it.
- **To take a mapping away**: Remove beside it; people keep any role given to them directly.

## Related

- [Add a person and give them roles](add-a-person-and-give-roles.md)
