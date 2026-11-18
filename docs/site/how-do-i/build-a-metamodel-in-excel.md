---
title: Build a metamodel in Excel
summary: A whole metamodel as one workbook: types, attributes, allowed relationships and rules, made into a model.
group: Metamodels
roles: industry-modeller, model-admin
---

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

- [Change a model's metamodel](change-a-metamodel.md)
- [Publish a reference model to the library](publish-a-reference-model.md)
