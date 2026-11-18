---
title: Add a person and give them roles
summary: People sign in through Keycloak; their roles on the installation come from Keycloak, and their roles on each model and project are given there.
group: People and access
roles: system-admin
---

> **Before you start** You need the Keycloak Admin or User Admin role to add people, and Model Admin or Project Admin on
> the model or project you give roles on.

## Steps

1. **Add the person in Keycloak** (or let them come from your directory, when EA Explorer signs in against it). Open
   `https://<your EA Explorer address>/auth/admin/`, choose the EA Explorer realm, then **Users › Add user**: their user
   name, name and email. Under **Credentials**, set a temporary password they change at their first sign-in.
2. **Give them their roles on the installation**, in Keycloak under **Role mapping**: for most people **user**; for
   admins **super-admin**, **it-admin**, **user-admin** or **auditor**; **model-creator** if they may make models;
   **library-admin**, **discovery-admin** or **architecture-board** where they need them.
3. **Give them roles on a model**: open the model, its **People** tab, then give the person a role: Model Admin, Model
   Sub Admin, Committer, Architect, History Viewer or Report Viewer.
4. **Give them roles on a project**: open the project, its **People** tab, then give the person a role: Project Admin,
   Lead Architect, Architect, Model Admin, Model Sub Admin or Stakeholder.

## Check it worked

System Admin › Users and roles: find the person; their EA Explorer roles, projects and models are listed. They can sign
in and see what their roles allow.

## If something goes wrong

- **They sign in but see almost nothing**: they have no role on any model or project yet; give one (steps 3 and 4).
- **A directory group should give a role**: map it once instead of giving the role to each person (see the related
  page).

## Related

- [Map directory groups to roles](map-directory-groups-to-roles.md)
- [Turn on multi-factor sign-in](turn-on-multi-factor-sign-in.md)
