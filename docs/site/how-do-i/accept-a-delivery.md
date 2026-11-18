---
title: Accept a delivery
summary: Take in what another system sent; it is committed as your load.
group: Bringing data in
roles: model-admin, user
screen: #/metamodel/{m}/import
---

## Why do this

A delivery is a file another system sent: the application inventory, the server list, the HR teams. It waits until a person has looked at it, because automated data can be wrong in ways a machine does not notice: a renamed column, a test file sent by mistake, half the rows missing. Accepting it is your statement that it is right. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** Data another system sent becomes part of the model, under your name.

> **Before you start** You need Committer, Model Sub Admin or Model Admin on the model.

## Steps

1. Open the model, **Import and export › Deliveries**, and the delivery.
2. Check the new, changed, kept and problem rows.
3. **Accept**.
