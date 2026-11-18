---
title: Give people roles on a model
summary: Who may read, change, commit and look after one model.
group: People and access
roles: model-admin
screen: #/metamodel/{m}/people
---

## Why do this

Roles on a model decide who may read it, change it, commit changes, and look after it. Giving them per model lets each owner run their own model without asking a System Admin. See [[roles-and-access]].

Access in EA Explorer is layered so each owner decides for their own part: System Admins for the installation, Model Admins for models, Project Admins for projects. Most people need only a few roles to do their work.

**In TOGAF terms:** The Preliminary phase's architecture capability: who does architecture work and with what authority. Sign-in itself is outside the method. See [[ea-explorer-and-togaf]].

**The goal:** The right people can do the right things on your model.

> **Before you start** You need the Model Admin role on the model.

## Steps

1. Open the model, its **People** tab.
2. Give a person a role, highest first:
   - **Model Admin**: everything on the model, including its metamodel and people.
   - **Model Sub Admin**: helps the Model Admin; reviews deliveries.
   - **Committer**: reviews and commits changes.
   - **Architect**: changes content (as uncommitted changes).
   - **History Viewer**: reads the model and its history.
   - **Report Viewer**: reads reports.
3. Take a role away when it is no longer needed.

To hand the model over to new Model Admins: Model Admin › Wizards, **Hand over**.

## Related

- [Add a person and give them roles](../guides/add-a-person-and-give-roles.md)
