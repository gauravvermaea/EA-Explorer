---
title: SR-13 Process against role
summary: Which actors and roles perform or own which processes.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

COO, Process owner.

## How to use it

Use it to see who performs or owns each process.

## How to read it

Processes with no role are unowned; one role across many processes may need support.

## Where to find it

Open a model, **Reports › Reports**, and choose **Process against role**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr_matrix`; its dashboard is `eax-sr13`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
