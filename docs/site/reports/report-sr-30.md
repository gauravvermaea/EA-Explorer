---
title: SR-30 Comparison with the source model
summary: Each model against the model it was created from: kept, changed, new and removed entities (gap analysis).
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Enterprise architect, Architecture board.

## How to use it

Use it to see how a model has moved away from the model it was created from.

## How to read it

Kept means unchanged, changed has different values, new was added here, removed was dropped. Large numbers of changes may mean the source should be updated too, or the copy merged back.

## Where to find it

Open a model, **Reports › Reports**, and choose **Comparison with the source model**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr30_source_comparison`; its dashboard is `eax-sr30`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
