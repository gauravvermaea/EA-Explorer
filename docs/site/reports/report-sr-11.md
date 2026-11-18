---
title: SR-11 Application against data entity (CRUD)
summary: Which applications create, read, update or delete which data (the access type in each cell).
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Data Officer, Data architect, Chief Information Security Officer.

## How to use it

Use it to find which applications create, read, update or delete each data entity (CRUD).

## How to read it

Each cell holds the access type. More than one application creating the same entity means more than one master: a data quality risk. An entity only read, never created, comes from outside the model.

## Where to find it

Open a model, **Reports › Reports**, and choose **Application against data entity (CRUD)**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr_matrix`; its dashboard is `eax-sr11`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
