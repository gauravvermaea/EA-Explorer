---
title: Roles and access
summary: Who may do what: roles on the installation, on each model and on each project, and where each is given.
group: People and access
roles: system-admin, model-admin, project-admin, user, executive
---

## Three layers of roles

- **On the installation** (given in Keycloak, or from your directory's groups): Super Admin, IT Admin, User Admin,
  Keycloak Admin, Auditor, Architecture Board, Discovery Admin, Model Creator, Library Admin, and User for everyone
  who signs in. See [[give-someone-an-installation-role]] and [[map-directory-groups-to-roles]].
- **On a model** (its People tab): Model Admin, Model Sub Admin, Committer, Architect, History Viewer, Report Viewer.
  See [[give-people-roles-on-a-model]].
- **On a project** (its set-up): Project Admin, Lead Architect, Architect, Model Admin, Model Sub Admin, Stakeholder.
  See [[give-people-roles-on-a-project]].

## Why it is done this way

Most people work on a few models and projects, and should see and change only those. Roles per model and per project
let each owner decide who joins their work, without asking a System Admin each time. What you may not use is simply
not shown, so screens stay simple. Machines get **service accounts** with tokens scoped to what they need
([[make-a-service-account]]).

## Read next

- [[add-a-person-and-give-roles]]
