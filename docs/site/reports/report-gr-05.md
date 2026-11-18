---
title: GR-05 Gap entities in the models
summary: The gaps added to the models as Gap entities, with the analysis, baseline and target they come from.
group: Gap analysis
roles: user, executive
---

## Why it matters

Gap analysis compares a baseline with a target and keeps the differences: the bridge, in ADM phase E, from the target architecture to the plan.

**In TOGAF terms:** ADM phase E, Opportunities and Solutions (gap analysis is also used in phases B to D). See [[ea-explorer-and-togaf]].

## Who it is for

Enterprise architect, Portfolio manager.

## How to use it

Use it to see the Gap entities in the models: the gaps recorded as part of the architecture.

## How to read it

Each Gap entity names its status, resolution and the analysis it came from; filter by the analysis or result tag to see one result's gaps.

## Where to find it

Open a model, **Reports › Reports**, and choose **Gap entities in the models**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.entity_std`; its dashboard is `eax-gr05`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
