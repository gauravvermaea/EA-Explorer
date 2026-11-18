---
title: SR-26 Completeness by type and owner
summary: How complete each type and owner is, and the entities missing required values.
group: Standard
roles: user, model-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Model owner, Enterprise architect.

## How to use it

Use it to drive data quality: which types and owners have the most missing required values.

## How to read it

Low completeness means reports on that type are unreliable. Send the list of entities missing values to their owners.

## Where to find it

Open a model, **Reports › Reports**, and choose **Completeness by type and owner**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr26_completeness`; its dashboard is `eax-sr26`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
