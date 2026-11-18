---
title: SR-29 Change activity
summary: Changes by week, model, person and kind over the last two years.
group: Standard
roles: user, executive, model-admin, system-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

Architecture board, Internal audit, Model owner.

## How to use it

Use it to see how actively models are maintained and by whom.

## How to read it

Steady activity shows a living repository; long quiet periods or one person doing all changes are risks to currency and continuity.

## Where to find it

Open a model, **Reports › Reports**, and choose **Change activity**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr29_change_activity`; its dashboard is `eax-sr29`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
