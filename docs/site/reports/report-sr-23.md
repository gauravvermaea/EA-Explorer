---
title: SR-23 Obsolescence risk
summary: Applications and capabilities at risk from technology past, near or phasing out of its end of life.
group: Standard
roles: user, executive, system-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Risk Officer, CTO, Chief Information Security Officer, Internal audit.

## How to use it

Use it to find applications and capabilities at risk from technology at or near its end of life.

## How to read it

Red is past end of life, amber within the warning period you choose. Critical applications in red are the first to remediate.

## Where to find it

Open a model, **Reports › Reports**, and choose **Obsolescence risk**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr23_obsolescence`; its dashboard is `eax-sr23`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
