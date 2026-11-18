---
title: Delete a model
summary: Remove a model for good, after a backup.
group: Models
roles: model-admin
screen: #/model-admin/wizards?wizard=delete
---

## Why do this

Deleting is final, so it is rarely the right choice: archiving keeps a model out of the way without losing it. Delete only what was made by mistake or must not be kept; EA Explorer takes a backup first and refuses while other models depend on it.

A model's life has stages: started, worked on, copied or split, handed over, locked or frozen at key moments, archived when done. Each stage has its wizard, and each asks before it changes anything.

**In TOGAF terms:** The Architecture Landscape in the Architecture Repository: the models at strategic, segment, capability and transition levels. See [[ea-explorer-and-togaf]].

**The goal:** A model is gone for good, after a backup.

> **Before you start** You need the Model Admin role on the model. Archiving is usually better.

## Steps

1. Open **Model Admin › Wizards**, **Delete a model**.
2. Read what refers to it; a model others derive from cannot go.
3. Type its name to confirm. A backup is taken first.

## Related

- [Archive a model](archive-a-model.md)
