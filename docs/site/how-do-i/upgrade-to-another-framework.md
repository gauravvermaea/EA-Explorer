---
title: Upgrade a model to another framework
summary: Move a model onto another metamodel, mapping each type.
group: Metamodels
roles: model-admin
screen: #/model-admin/wizards?wizard=upgrade
---

## Why do this

When an organisation changes its modelling framework, existing models need to move with it. Upgrading maps each type and relationship to the new metamodel; the model is tagged first. See [[metamodels]].

A metamodel change ripples: into what people may record, what reports read, what rules check and what integrations send. That is why it goes through drafts and review, and why each version is kept and can be compared.

**In TOGAF terms:** The content framework and content metamodel: what building blocks and relationships the architecture may hold. See [[ea-explorer-and-togaf]].

**The goal:** A model moves onto another metamodel, type by type.

> **Before you start** You need the Model Admin role on the model.

## Steps

1. Open **Model Admin › Wizards**, **Upgrade to another framework**.
2. Pick the model and the target framework.
3. Map each type and relationship; check; confirm. The model is tagged first.
