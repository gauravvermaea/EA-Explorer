---
title: SR-15 Application interaction matrix
summary: Application-to-application flows.
group: Standard
roles: user
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Integration architect, Solution architect.

## How to use it

Use it to see application-to-application flows in one grid.

## How to read it

Each filled cell is a flow from the row application to the column one. Dense rows or columns are integration hubs; their change needs the most coordination.

## Where to find it

Open a model, **Reports › Reports**, and choose **Application interaction matrix**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr_matrix`; its dashboard is `eax-sr15`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
