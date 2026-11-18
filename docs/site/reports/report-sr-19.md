---
title: SR-19 Criticality against technical health
summary: Business criticality against technical fit for every application.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CIO, CTO, Portfolio manager.

## How to use it

Use it to find critical applications in poor technical health.

## How to read it

Top left (high criticality, low technical fit) is the risk zone: critical to the business and fragile. Bubble size shows cost where it is known.

## Where to find it

Open a model, **Reports › Reports**, and choose **Criticality against technical health**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr18_application_fit`; its dashboard is `eax-sr19`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
