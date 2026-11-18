---
title: HM Pick-list heatmaps
summary: How the values of every pick list are spread over entities (RPT-006).
group: Standard
roles: user, model-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Model owner, Data steward, Enterprise architect.

## How to use it

Use it to see how the values of each pick list (lifecycle, criticality, TIME...) are spread across entities.

## How to read it

A value with very many entities, or many entities with no value, shows where the data needs attention; set the bands in the filters.

## Where to find it

Open a model, **Reports › Reports**, and choose **Pick-list heatmaps**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.mo_pick_list_counts`; its dashboard is `eax-heatmaps`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
