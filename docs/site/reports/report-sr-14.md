---
title: SR-14 Capability against value stream
summary: Which capabilities enable which value stream stages.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CEO, COO, Business architect, Product owner.

## How to use it

Use it to see which capabilities enable each stage of a value stream.

## How to read it

A stage with no capability is not supported by the architecture; a capability on many stages is critical to the value delivered.

## Where to find it

Open a model, **Reports › Reports**, and choose **Capability against value stream**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr_matrix`; its dashboard is `eax-sr14`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
