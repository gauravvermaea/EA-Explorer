---
title: MO Model overview
summary: How many entities of each type, the models and recent changes (MOD-010).
group: Standard
roles: user, executive, model-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Model owner, Enterprise architect, Architecture board.

## How to use it

Start here to see what a model holds and how actively it is being changed, before opening a specific report.

## How to read it

Large counts show where the model is detailed; types with few or no entities are gaps in coverage. The recent changes show whether the model is being kept up to date: no changes for months usually means stale content.

## Where to find it

Open a model, **Reports › Reports**, and choose **Model overview**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.mo_type_counts`; its dashboard is `eax-model-overview`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
