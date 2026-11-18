---
title: Put a model back to a tag
summary: The model as it was at a tag; a tag of now is taken first.
group: Versions and merging
roles: model-admin
screen: #/model-admin/wizards?wizard=restore
---

## Why do this

When a model has gone wrong (a bad load, a change of direction), going back to a tag restores it to that named moment. A tag of the current state is taken first, so even this can be undone. See [[versions-tags-and-merging]].

Nothing in EA Explorer is lost: every change is kept, moments can be named, and work can happen in copies that merge back after review. This is what lets many people change one model without fear.

**In TOGAF terms:** Phase H and the Architecture Repository: change to the baseline is controlled, recorded and reversible. See [[ea-explorer-and-togaf]].

**The goal:** A model is back as it was at a named moment.

> **Before you start** You need the Model Admin role on the model.

## Steps

1. Open **Model Admin › Wizards**, **Restore a tag**, and pick the model.
2. Pick the tag; read what changes.
3. Confirm.
