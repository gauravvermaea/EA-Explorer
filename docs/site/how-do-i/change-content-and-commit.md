---
title: Change content and commit it
summary: Add and change entities and relationships, then commit them so everyone sees them.
group: Working with content
roles: user
---

> **Before you start** You need the Architect role (or higher) on the model; committing needs Committer.

## Steps

1. Open the model. Change content in the **Grid** (a table: click a cell to edit; copy and paste from Excel) or in
   **Data entry** (one entity at a time in a form: choose a type, then **+ New** or open an entity).
2. Add relationships on the entity's Relations, or draw them in a drawn view; only the relationships the metamodel
   allows are offered.
3. Your changes are **uncommitted**: only you and the model's Committers see them. The **Changes** tab lists them.
4. **Commit** with a message saying what and why (for example *October figures added*). If you are not a Committer, a
   Committer reviews and commits them, or sends them back.

## If something goes wrong

- **A clash**: someone committed a change to the same thing after you started. For each clash choose yours or theirs.
- **Undo a commit**: the model's History, the commit, **Roll back** (a new commit that puts things back).

## Related

- [Load data from Excel](load-data-from-excel.md)
