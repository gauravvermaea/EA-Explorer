---
title: SR-04 Data entity catalogue
summary: Business objects and data objects with owners and classification.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Data Officer, Data architect.

## How to use it

Use it with data owners to agree the data entities, their owners and classification.

## How to read it

Every data entity should have an owner and a classification; restricted and confidential data without an owner is a governance risk. Compare with [[report-sr-11|SR-11]] to see which applications touch each entity.

## Where to find it

Open a model, **Reports › Reports**, and choose **Data entity catalogue**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr04_data_catalogue`; its dashboard is `eax-sr04`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
