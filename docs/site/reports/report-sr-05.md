---
title: SR-05 Business process catalogue
summary: Processes and functions by level with owners and the roles that perform them.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

COO, Process owner, Business architect.

## How to use it

Use it to agree the process landscape and who performs each process.

## How to read it

Processes with no role are unassigned work; a role on very many processes may be a bottleneck. Levels show how deep the process model goes in each area.

## Where to find it

Open a model, **Reports › Reports**, and choose **Business process catalogue**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr05_process_catalogue`; its dashboard is `eax-sr05`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
