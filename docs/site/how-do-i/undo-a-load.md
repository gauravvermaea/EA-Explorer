---
title: Undo a load
summary: Take back everything one load brought in.
group: Bringing data in
roles: user, model-admin
screen: #/metamodel/{m}/import/loads
---

## Why do this

If a load turns out to be wrong, undoing it removes everything it brought in at once, so a bad file never needs cleaning up by hand. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** Everything one load brought in is taken back.

> **Before you start** You need a role on the model that may change content (Architect or higher).

## Steps

1. Open the model, **Import and export**, its loads.
2. Open the load; **Undo**.
