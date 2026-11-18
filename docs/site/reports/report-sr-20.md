---
title: SR-20 Cost by capability
summary: Application and technology annual cost rolled up to the capabilities they support.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CFO, CEO, CIO.

## How to use it

Use it to see what each capability costs, through the applications and technology that support it.

## How to read it

Costs roll up from applications and technology; a capability with high cost and low maturity or value is a candidate for review. Missing costs make a capability look cheaper than it is.

## Where to find it

Open a model, **Reports › Reports**, and choose **Cost by capability**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr20_cost_by_capability`; its dashboard is `eax-sr20`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
