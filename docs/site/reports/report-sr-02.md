---
title: SR-02 Business capability catalogue
summary: The capability hierarchy with levels, owners, maturity and how many applications support each.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CEO, COO, Business architect, Business unit head.

## How to use it

Use it to agree the capability map with the business and to see which capabilities have support.

## How to read it

Each level is a step down the capability tree. Capabilities with no applications are unsupported or done by hand; many applications on one capability point to overlap (see [[report-sr-25|SR-25]]). Low maturity on a critical capability is a candidate for investment.

## Where to find it

Open a model, **Reports › Reports**, and choose **Business capability catalogue**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr02_capability_catalogue`; its dashboard is `eax-sr02`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
