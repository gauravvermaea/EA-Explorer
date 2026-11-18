---
title: GR-01 Gap analyses
summary: Every gap analysis: its template, baseline and target (models or tags), when compared, and how many gaps are open.
group: Gap analysis
roles: user, executive
---

## Why it matters

Gap analysis compares a baseline with a target and keeps the differences: the bridge, in ADM phase E, from the target architecture to the plan.

**In TOGAF terms:** ADM phase E, Opportunities and Solutions (gap analysis is also used in phases B to D). See [[ea-explorer-and-togaf]].

## Who it is for

Enterprise architect, Architecture board, Change manager, CIO.

## How to use it

Use it to see every gap analysis, its baseline and target, and how much is still to decide.

## How to read it

New and eliminated are the gaps to act on; changed shows what moves; undecided counts gaps with no resolution yet: drive it to zero before the migration plan is agreed. Open goes to the analysis in EA Explorer.

## Where to find it

Open a model, **Reports › Reports**, and choose **Gap analyses**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.gap_analyses`; its dashboard is `eax-gr01`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
