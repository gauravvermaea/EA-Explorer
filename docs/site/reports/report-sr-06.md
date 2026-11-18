---
title: SR-06 Interface and integration catalogue
summary: Flows and other links between applications and interfaces, source to target.
group: Standard
roles: user, system-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Integration architect, Solution architect, IT operations.

## How to use it

Use it to review integrations: what flows from which application to which, before a change to either end.

## How to read it

Each row is a link from source to target. Many links on one application make it a hub whose change ripples widely; an interface with no flows may be unused.

## Where to find it

Open a model, **Reports › Reports**, and choose **Interface and integration catalogue**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr06_interfaces`; its dashboard is `eax-sr06`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
