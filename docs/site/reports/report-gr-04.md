---
title: GR-04 Gap resolutions and work packages
summary: How each gap is closed (build, buy, retire, replace...) and the work packages that close it; the gaps still undecided.
group: Gap analysis
roles: user, executive
---

## Why it matters

Gap analysis compares a baseline with a target and keeps the differences: the bridge, in ADM phase E, from the target architecture to the plan.

**In TOGAF terms:** ADM phase E, Opportunities and Solutions (gap analysis is also used in phases B to D). See [[ea-explorer-and-togaf]].

## Who it is for

Portfolio manager, Change manager, Enterprise architect, CIO.

## How to use it

Use it to follow the decisions on gaps: resolution and work packages.

## How to read it

Gaps without a resolution are undecided; gaps with a resolution but no work package are decided but not planned. Both should be empty before the roadmap is final.

## Where to find it

Open a model, **Reports › Reports**, and choose **Gap resolutions and work packages**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.gap_items`; its dashboard is `eax-gr04`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
