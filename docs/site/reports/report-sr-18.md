---
title: SR-18 Application TIME quadrant
summary: Applications by functional and technical fit (Tolerate, Invest, Migrate, Eliminate), with the TIME set on each.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CIO, CFO, Portfolio manager.

## How to use it

Use it to agree the TIME decision for each application: Tolerate, Invest, Migrate or Eliminate.

## How to read it

High functional and high technical fit: Invest. High functional, low technical: Migrate. Low functional, high technical: Tolerate. Both low: Eliminate. Compare the quadrant with the TIME set on each application; disagreements are the ones to discuss.

## Where to find it

Open a model, **Reports › Reports**, and choose **Application TIME quadrant**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr18_application_fit`; its dashboard is `eax-sr18`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
