---
title: SR-28 Duplicate candidates
summary: Entities of the same type with the same or similar names, with a similarity score.
group: Standard
roles: user, model-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Model owner, Data steward.

## How to use it

Use it to find likely duplicates before they spread into reports.

## How to read it

Pairs with a high similarity score are probably the same thing; open both and merge or rename.

## Where to find it

Open a model, **Reports › Reports**, and choose **Duplicate candidates**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr28_duplicates`; its dashboard is `eax-sr28`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
