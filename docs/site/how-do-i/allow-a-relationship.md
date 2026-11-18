---
title: Allow a relationship between two types
summary: Which types may be related, and how.
group: Metamodels
roles: model-admin, industry-modeller
screen: #/metamodel/{m}/rels
---

## Why do this

The metamodel says which relationships are meaningful between which types. Allowing a new one lets people record a dependency the organisation cares about, while keeping out connections that would only add noise. See [[metamodels]].

A metamodel change ripples: into what people may record, what reports read, what rules check and what integrations send. That is why it goes through drafts and review, and why each version is kept and can be compared.

**In TOGAF terms:** The content framework and content metamodel: what building blocks and relationships the architecture may hold. See [[ea-explorer-and-togaf]].

**The goal:** Two types may now be related in a new way.

> **Before you start** You need the Model Admin role on the model.

## Steps

1. Open the model, **Metamodel › Relationships**.
2. **New**: the from type, the kind (composition, serving, flow…) and the to type.
3. Add relationship attributes if needed; **Save**.
