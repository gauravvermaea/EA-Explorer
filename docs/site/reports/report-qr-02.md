---
title: QR-02 Completeness by type and owner
summary: Completeness, failing rules, stale entities and orphans by entity type and by owner, weakest first.
group: Data quality
roles: user, model-admin
---

## Why it matters

Data quality reports show how far each model can be trusted, and where to start improving it.

**In TOGAF terms:** Supports every phase: the content framework is only useful if its building blocks are complete and correct. See [[ea-explorer-and-togaf]].

## Who it is for

Model owner, Enterprise architect, Data steward.

## How to use it

Use it to see where the data is weakest and who should fix it: click a bar to drill down to the entities behind it, and Open on a row to fix the entity in EA Explorer.

## How to read it

Scores run from 0 to 100: half completeness, almost a third the share of entities failing no rule, a fifth the share that is not stale. The latest measurement of each model is shown; the trend shows every measurement.

## Where to find it

Open a model, **Reports › Reports**, and choose **Completeness by type and owner**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.quality_groups`; its dashboard is `eax-qr02`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
