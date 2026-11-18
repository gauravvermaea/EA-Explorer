---
title: GR-03 TOGAF gap matrix
summary: The TOGAF gap matrix: baseline elements down, target elements across; included, new and eliminated cells.
group: Gap analysis
roles: user, executive
---

## Why it matters

Gap analysis compares a baseline with a target and keeps the differences: the bridge, in ADM phase E, from the target architecture to the plan.

**In TOGAF terms:** ADM phase E, Opportunities and Solutions (gap analysis is also used in phases B to D). See [[ea-explorer-and-togaf]].

## Who it is for

Enterprise architect, Architecture board, Solution architect.

## How to use it

Use it as the TOGAF gap matrix: baseline elements down, target elements across.

## How to read it

A cell where an element appears on both sides is included (kept or changed); an element only in the baseline is eliminated (retire it, or add it back if it was dropped by accident); only in the target is new (build or buy it).

## Where to find it

Open a model, **Reports › Reports**, and choose **TOGAF gap matrix**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.gap_matrix`; its dashboard is `eax-gr03`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
