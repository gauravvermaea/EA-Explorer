---
title: Decline a delivery
summary: Send a delivery back so nothing of it loads.
group: Bringing data in
roles: model-admin, user
screen: #/metamodel/{m}/import/deliveries
---

## Why do this

Declining is the safety valve of automated data: when a delivery is wrong, nothing of it reaches the model, and the reason goes back so the sending system can fix it and send again. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** A wrong delivery is sent back and nothing of it loads.

> **Before you start** You need Committer, Model Sub Admin or Model Admin on the model.

## Steps

1. Open the delivery.
2. **Decline**: give the reason (the source sends a corrected file).
3. Confirm.
