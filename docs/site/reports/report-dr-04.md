---
title: DR-04 Dependency counts and hot spots
summary: How many entities each entity depends on and how many depend on it, banded by thresholds you choose.
group: Dependency
roles: user, executive, system-admin
---

## Why it matters

Dependency reports follow relationships step by step, upstream and downstream, to show what a change would affect and what something relies on.

**In TOGAF terms:** Impact analysis, used in every phase that weighs a change, and in phase H. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Risk Officer, CTO, Solution architect, IT operations.

## How to use it

Use it to find dependency hot spots.

## How to read it

Entities with many dependants are hubs; with many dependencies, fragile. Set the bands in the filters.

## Where to find it

Open a model, **Reports › Reports**, and choose **Dependency counts and hot spots**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.dr_fan`; its dashboard is `eax-dr04`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
