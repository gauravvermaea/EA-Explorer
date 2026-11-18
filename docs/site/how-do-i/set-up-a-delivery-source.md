---
title: Set up a delivery source
summary: Another system sends its data to a model as deliveries, each previewed and accepted by a Committer.
group: Bringing data in
roles: model-admin, developer
screen: #/metamodel/{m}/import
---

## Why do this

A delivery source names a system that sends data, the folder it uses, whether its values win, and who is told. Set up once, it brings data in on every delivery for review. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** Another system can deliver data to a model.

> **Before you start** You need Model Admin on the model. For a system that sends through the API, a service account
> with a token (System Admin › Machine access).

## Steps

1. Open the model, **Import and export › Deliveries**.
2. Add a **source**: its name, its folder, whether its values win over EA Explorer's, who is told, and optionally the
   service account that sends it.
3. The system then sends deliveries in the Excel or CSV format, by a folder, the API or an upload (see the related
   page).
4. Each delivery is previewed (new, changed, kept, unchanged, problems) and waits. A Committer, Model Sub Admin or
   Model Admin **accepts** it (committed as their load, undone like any load) or **declines** it.

## Related

- [Send data with a delivery](../guides/send-data-with-a-delivery.md)
- [Push data with Python](push-data-with-python.md)
