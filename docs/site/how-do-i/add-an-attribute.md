---
title: Add an attribute to a type
summary: A field on an entity type: text, number, date, list, link.
group: Metamodels
roles: model-admin, industry-modeller
screen: #/metamodel/{m}/types
---

## Why do this

Attributes are the fields of an entity type: owner, cost, lifecycle status. Adding one changes what everyone can record about that type, so it goes through a metamodel draft and review. Choose attributes that answer real questions; each one asks people for effort. See [[metamodels]].

A metamodel change ripples: into what people may record, what reports read, what rules check and what integrations send. That is why it goes through drafts and review, and why each version is kept and can be compared.

**In TOGAF terms:** The content framework and content metamodel: what building blocks and relationships the architecture may hold. See [[ea-explorer-and-togaf]].

**The goal:** A type can hold one more piece of information.

> **Before you start** You need the Model Admin role on the model.

## Steps

1. Open the model, **Metamodel › Types**, and the type.
2. **New attribute**: name, kind, required or not, its list of values.
3. **Save**.
