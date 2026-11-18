---
title: Change a model's metamodel
summary: Add or change entity types, attributes, pick lists, allowed relationships and rules, reviewed before they are published.
group: Metamodels
roles: model-admin, industry-modeller
---

## Why do this

Changing a metamodel changes what everyone can record and what reports can rely on, so it is done through drafts, review and versions. See [[metamodels]].

A metamodel change ripples: into what people may record, what reports read, what rules check and what integrations send. That is why it goes through drafts and review, and why each version is kept and can be compared.

**In TOGAF terms:** The content framework and content metamodel: what building blocks and relationships the architecture may hold. See [[ea-explorer-and-togaf]].

**The goal:** A metamodel changes safely, reviewed, as a new version.

> **Before you start** You need the Model Admin role on the model.

## The ways to do it

1. Open the model, its **Metamodel** tab: domains, entity types, attributes, pick lists, relationship types, allowed
   relationships (with how many: 1, 0..1, 1..*, 0..*) and rules.
2. Make the change. A change that needs a review waits as a **metamodel draft** (Model Admin › Metamodel drafts):
   others comment, then it is approved or rejected.
3. Approved, it is published as a new version with its note; any two versions can be compared.
4. **Push down**: offer the new version to the model's children (Model Admin › Wizards, Propagate to a child).

To take a whole set of types from another model: Model Admin › Wizards, **Extend from another model**.

## Check it worked

The Metamodel tab shows the new version; data entry and the import sheets offer the new types and attributes.

## Each task, one page

1. [Start a metamodel draft](../how-do-i/start-a-metamodel-draft.md)
2. [Add an entity type](../how-do-i/add-an-entity-type.md)
3. [Add an attribute to a type](../how-do-i/add-an-attribute.md)
4. [Allow a relationship between two types](../how-do-i/allow-a-relationship.md)
5. [Review a metamodel draft](../how-do-i/review-a-metamodel-draft.md)
6. [Push changes to a child](../how-do-i/push-changes-to-a-child.md)
7. [Download a metamodel](../how-do-i/download-a-metamodel.md)

## Related

- [Build a metamodel in Excel](../how-do-i/build-a-metamodel-in-excel.md)
