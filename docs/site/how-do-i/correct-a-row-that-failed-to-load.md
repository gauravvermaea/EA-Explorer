---
title: Correct a row that failed to load
summary: Fix one problem row of a load or delivery and check it again.
group: Bringing data in
roles: user, developer
screen: #/metamodel/{m}/import/loads
---

## Why do this

When a load or delivery has problem rows, the rest can still go in; the problems wait. Correcting a row on screen and checking it again saves sending the whole file again. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** A rejected row is fixed and loads.

> **Before you start** You need a role on the model that may change content (Architect or higher).

## Steps

1. Open the load or delivery; its problem rows.
2. **Correct** a row: fix the value; **Save and check again**.
