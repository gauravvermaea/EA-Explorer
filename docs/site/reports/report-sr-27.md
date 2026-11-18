---
title: SR-27 Orphans and missing relationships
summary: Entities with no relationships, no parent and no children.
group: Standard
roles: user, model-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Model owner, Data steward.

## How to use it

Use it to find entities that are not connected to anything.

## How to read it

An orphan is often a duplicate, a leftover or an entity whose relationships were never captured; check each one and connect, merge or retire it.

## Where to find it

Open a model, **Reports › Reports**, and choose **Orphans and missing relationships**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr27_orphans`; its dashboard is `eax-sr27`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
