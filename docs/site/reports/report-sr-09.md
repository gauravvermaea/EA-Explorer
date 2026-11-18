---
title: SR-09 Application against capability
summary: Which applications support which capabilities.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CIO, Business architect, Application architect.

## How to use it

Use it to see which applications support each capability, for rationalisation and impact questions.

## How to read it

A filled cell means the application supports the capability. Rows with many cells are broad platforms; columns with many cells are capabilities with overlap; empty columns are unsupported capabilities.

## Where to find it

Open a model, **Reports › Reports**, and choose **Application against capability**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr_matrix`; its dashboard is `eax-sr09`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
