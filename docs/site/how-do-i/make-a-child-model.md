---
title: Make a child model
summary: A copy that keeps its parent: its work merges back, and the parent's metamodel changes flow down.
group: Models
roles: model-admin
screen: #/model-admin/wizards?wizard=child
---

## Why do this

A child model lets a team or project work freely without disturbing the live model, then merge back what is agreed. It also takes the parent's later changes, so it does not drift. See [[versions-tags-and-merging]].

A model's life has stages: started, worked on, copied or split, handed over, locked or frozen at key moments, archived when done. Each stage has its wizard, and each asks before it changes anything.

**In TOGAF terms:** The Architecture Landscape in the Architecture Repository: the models at strategic, segment, capability and transition levels. See [[ea-explorer-and-togaf]].

**The goal:** A working copy that merges back and keeps up with its parent.

> **Before you start** You need the Model Admin role on the model.

## Steps

1. Open **Model Admin › Wizards** on the model.
2. Choose **Copy with the parent-child link**.
3. Name the child; choose what it takes; **Make a copy now**.
4. Give people roles on the child's People tab.

## Related

- [Merge a child model back](../guides/merge-a-child-model-back.md)
- [Make a separate copy of a model](make-a-separate-copy.md)
