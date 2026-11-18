---
title: SR-24 Single points of failure
summary: Applications and technology ranked by dependants, and how many of them have no alternative.
group: Standard
roles: user, executive, system-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Risk Officer, CTO, IT operations.

## How to use it

Use it to find single points of failure: items many others depend on.

## How to read it

Items at the top have the most dependants; those with no alternative are the real single points of failure and need resilience or a backup plan.

## Where to find it

Open a model, **Reports › Reports**, and choose **Single points of failure**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr24_single_points`; its dashboard is `eax-sr24`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
