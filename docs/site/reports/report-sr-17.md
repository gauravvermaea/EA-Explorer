---
title: SR-17 Technology lifecycle and end of life
summary: Technology by lifecycle phase and end-of-life year, and what is past or near its end of life.
group: Standard
roles: user, executive, system-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CTO, Chief Risk Officer, Technology architect, IT operations.

## How to use it

Use it to plan technology upgrades and replacements by end-of-life date.

## How to read it

Rows past their end of life are red; those within the warning period you choose are amber. Plan the red ones now and the amber ones in the next budget cycle.

## Where to find it

Open a model, **Reports › Reports**, and choose **Technology lifecycle and end of life**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr17_technology_lifecycle`; its dashboard is `eax-sr17`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
