---
title: Change a model's metamodel
summary: Add or change entity types, attributes, pick lists, allowed relationships and rules, reviewed before they are published.
group: Metamodels
roles: model-admin, industry-modeller
---

> **Before you start** You need the Model Admin role on the model.

## Steps

1. Open the model, its **Metamodel** tab: domains, entity types, attributes, pick lists, relationship types, allowed
   relationships (with how many: 1, 0..1, 1..*, 0..*) and rules.
2. Make the change. A change that needs a review waits as a **metamodel draft** (Model Admin › Metamodel drafts):
   others comment, then it is approved or rejected.
3. Approved, it is published as a new version with its note; any two versions can be compared.
4. **Push down**: offer the new version to the model's children (Model Admin › Wizards, Propagate to a child).

To take a whole set of types from another model: Model Admin › Wizards, **Extend from another model**.

## Check it worked

The Metamodel tab shows the new version; data entry and the import sheets offer the new types and attributes.

## Related

- [Build a metamodel in Excel](build-a-metamodel-in-excel.md)
