---
title: KR-01 KPI trends
summary: Each model's KPIs over time: entities by type, applications by TIME and lifecycle, total cost, quality score, orphans, end-of-life technology and the model's own KPIs, kept on the 1st of each month and on every tag.
group: KPI trends
roles: user, executive, model-admin
---

## Why it matters

KPI trends show how each model's key figures move over time, kept on the 1st of every month and at every tag.

**In TOGAF terms:** Architecture governance and the architecture capability: measuring the repository over time. See [[ea-explorer-and-togaf]].

## Who it is for

Enterprise architect, Architecture board, Model owner, CIO.

## How to use it

Use it to follow how each model moves month by month and between tags: choose a KPI (Entities, Applications by TIME, Total annual cost, Data quality score...) and the models to compare; Model Admins add their own KPIs on the model page.

## How to read it

Each line is a model (and, for KPIs split by type, TIME class or lifecycle, each part of it); a point is a snapshot kept on the 1st of a month or when the model was tagged. A rising orphan count or a falling quality score is the model drifting; end-of-life technology that does not fall is a plan not acted on.

## Where to find it

Open a model, **Reports › Reports**, and choose **KPI trends**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.kpi_trends`; its dashboard is `eax-kr01`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
