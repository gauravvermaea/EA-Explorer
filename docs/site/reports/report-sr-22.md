---
title: SR-22 Impact analysis
summary: Everything that depends on a chosen entity, up to four steps away, with the path.
group: Standard
roles: user
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Solution architect, Change manager, Enterprise architect.

## How to use it

Use it before changing or retiring something: choose the entity in the filter to see everything that depends on it.

## How to read it

Depth 1 is directly affected; higher depths are knock-on effects. The path shows how each dependant is reached.

## Where to find it

Open a model, **Reports › Reports**, and choose **Impact analysis**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr22_impact`; its dashboard is `eax-sr22`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
