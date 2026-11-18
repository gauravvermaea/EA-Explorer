---
title: Take changes from the parent
summary: Bring the parent's newer metamodel and content down into a child.
group: Versions and merging
roles: model-admin
screen: #/model-admin/wizards?wizard=down
---

## Why do this

While a child is worked on, its parent may change. Taking the changes keeps the child current, and where both changed the same thing you choose which wins. See [[versions-tags-and-merging]].

Nothing in EA Explorer is lost: every change is kept, moments can be named, and work can happen in copies that merge back after review. This is what lets many people change one model without fear.

**In TOGAF terms:** Phase H and the Architecture Repository: change to the baseline is controlled, recorded and reversible. See [[ea-explorer-and-togaf]].

**The goal:** A child model is up to date with its parent.

> **Before you start** You need the Model Admin role on the model. (on the child)

## Steps

1. Open **Model Admin › Wizards**, **Propagate changes from the parent**, and pick the child.
2. See what changed in the parent; where both changed, choose which wins.
3. Confirm.
