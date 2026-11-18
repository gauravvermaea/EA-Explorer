---
title: Change content and commit it
summary: Add and change entities and relationships, then commit them so everyone sees them.
group: Working with content
roles: user
---

## Why do this

Changing a model is the everyday work of an architect. This guide shows the whole route: entering and editing, relationships, your uncommitted changes, review and commit, and what to do when changes clash. See [[versions-tags-and-merging]].

Content work is the everyday heart of architecture: recording what exists and what should, and how it all connects. EA Explorer checks it against the metamodel as you go and keeps it as your change until it is reviewed.

**In TOGAF terms:** Phases B, C and D: recording the building blocks and relationships of the baseline and target architectures. See [[ea-explorer-and-togaf]].

**The goal:** Your changes are made, reviewed and part of the model.

> **Before you start** You need the Architect role (or higher) on the model; committing needs Committer.

## The ways to do it

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

## Each task, one page

1. [Add an entity](../how-do-i/add-an-entity.md)
2. [Edit entities in the grid](../how-do-i/edit-entities-in-the-grid.md)
3. [Add a relationship between two entities](../how-do-i/add-a-relationship.md)
4. [Commit your changes](../how-do-i/commit-your-changes.md)
5. [Resolve a clash when committing](../how-do-i/resolve-a-clash-when-committing.md)
6. [Review and commit someone else's changes](../how-do-i/review-someone-elses-changes.md)
7. [Roll back a commit](../how-do-i/roll-back-a-commit.md)

## Related

- [Load data from Excel](../how-do-i/load-data-from-excel.md)
