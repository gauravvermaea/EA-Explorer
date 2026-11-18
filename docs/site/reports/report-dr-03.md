---
title: DR-03 Impact chain from technology to value stream
summary: Each technology, the applications it serves, the processes and capabilities they support and the value streams those enable, with end-of-life risk.
group: Dependency
roles: user, executive
---

## Why it matters

Dependency reports follow relationships step by step, upstream and downstream, to show what a change would affect and what something relies on.

**In TOGAF terms:** Impact analysis, used in every phase that weighs a change, and in phase H. See [[ea-explorer-and-togaf]].

## Who it is for

CTO, Chief Risk Officer, CIO, Technology architect, Enterprise architect.

## How to use it

Use it to trace each technology up to the value streams it ultimately supports.

## How to read it

A technology that reaches many value streams is business-critical even if it looks small; change it with care.

## Where to find it

Open a model, **Reports › Reports**, and choose **Impact chain from technology to value stream**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.dr_impact_chain`; its dashboard is `eax-dr03`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
