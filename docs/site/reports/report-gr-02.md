---
title: GR-02 Gaps by domain and type
summary: Kept, changed, new and eliminated elements by domain and entity type, for one or several gap analyses.
group: Gap analysis
roles: user
---

## Why it matters

Gap analysis compares a baseline with a target and keeps the differences: the bridge, in ADM phase E, from the target architecture to the plan.

**In TOGAF terms:** ADM phase E, Opportunities and Solutions (gap analysis is also used in phases B to D). See [[ea-explorer-and-togaf]].

## Who it is for

Enterprise architect, Business architect, Application architect, Technology architect.

## How to use it

Use it to see where the gaps are, by domain and entity type.

## How to read it

Large bars show the parts of the architecture that change most between baseline and target, and so where the work and the risk are.

## Where to find it

Open a model, **Reports › Reports**, and choose **Gaps by domain and type**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.gap_items`; its dashboard is `eax-gr02`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
