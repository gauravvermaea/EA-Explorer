---
title: SR-16 Capability heatmap
summary: Capabilities coloured by the number of applications supporting them, by maturity and by criticality.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CEO, CIO, COO, Business architect.

## How to use it

Use it to show where capabilities are well or poorly supported, by applications, maturity and criticality.

## How to read it

Colours follow the bands set in the filters (for example, green for enough support, red for none or too many). Red on a critical capability is the first to address; change the thresholds in the filter to suit your estate.

## Where to find it

Open a model, **Reports › Reports**, and choose **Capability heatmap**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr02_capability_catalogue`; its dashboard is `eax-sr16`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
