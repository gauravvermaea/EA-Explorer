---
title: Build a metamodel in Excel
summary: A whole metamodel as one workbook: types, attributes, allowed relationships and rules, made into a model.
group: Metamodels
roles: industry-modeller, model-admin
screen: #/model-admin/wizards?wizard=new
---

## Why do this

Designing a metamodel is easier in a spreadsheet: types, attributes, pick lists and allowed relationships side by side, reviewed with colleagues. EA Explorer reads the workbook, checks it, and builds the metamodel from it. See [[metamodels]].

A metamodel change ripples: into what people may record, what reports read, what rules check and what integrations send. That is why it goes through drafts and review, and why each version is kept and can be compared.

**In TOGAF terms:** The content framework and content metamodel: what building blocks and relationships the architecture may hold. See [[ea-explorer-and-togaf]].

**The goal:** A whole metamodel designed in a workbook, then made into a model.

> **Before you start** You need the Model Creator role.

## Steps

1. **Model Admin › Wizards, Model from a metamodel workbook**: download the empty template, or any model's metamodel in
   the same layout.
2. Fill in the sheets: **Model**, **Domains** (code, name, colour), **Pick lists**, **Attributes**, **Types** (code,
   name, domain, ID prefix, notation, colour), **Type attributes** (which type has which attribute, required or not),
   **Relationship types**, **Allowed relationships** (with multiplicity: 1, 0..1, 1..*, 0..*, 2..5) and **Rules**.
3. Upload it and check what it would make.
4. Make a new model from it, blank (the workbook is the whole metamodel), or add it to an existing model (it adds and
   updates, never takes away).

## Related

- [Change a model's metamodel](../guides/change-a-metamodel.md)
- [Publish a reference model to the library](../guides/publish-a-reference-model.md)
