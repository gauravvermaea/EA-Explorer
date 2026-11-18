---
title: DR-01 Dependencies of an entity
summary: Choose an entity: what it depends on (upstream) and what depends on it (downstream), up to six steps, with the path.
group: Dependency
roles: user, system-admin
---

## Why it matters

Dependency reports follow relationships step by step, upstream and downstream, to show what a change would affect and what something relies on.

**In TOGAF terms:** Impact analysis, used in every phase that weighs a change, and in phase H. See [[ea-explorer-and-togaf]].

## Who it is for

Solution architect, Enterprise architect, Change manager, IT operations.

## How to use it

Choose an entity in the filter to see what it depends on and what depends on it.

## How to read it

Upstream items can break it; downstream items break if it changes. The step count shows how far away each is.

## Where to find it

Open a model, **Reports › Reports**, and choose **Dependencies of an entity**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.dr_dependencies`; its dashboard is `eax-dr01`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
