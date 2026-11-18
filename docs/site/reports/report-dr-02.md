---
title: DR-02 Dependency matrix between two types
summary: Choose the row type and the column type: every relationship between their entities.
group: Dependency
roles: user
---

## Why it matters

Dependency reports follow relationships step by step, upstream and downstream, to show what a change would affect and what something relies on.

**In TOGAF terms:** Impact analysis, used in every phase that weighs a change, and in phase H. See [[ea-explorer-and-togaf]].

## Who it is for

Enterprise architect, Solution architect, Application architect.

## How to use it

Choose a row type and a column type to see every relationship between their entities.

## How to read it

Filled cells are relationships; empty rows or columns are entities with no link to the other type.

## Where to find it

Open a model, **Reports › Reports**, and choose **Dependency matrix between two types**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.entity_pairs`; its dashboard is `eax-dr02`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
