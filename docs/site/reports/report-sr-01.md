---
title: SR-01 Application portfolio inventory
summary: Every application with owner, lifecycle, criticality, cost, vendor, hosting and TIME.
group: Standard
roles: user, executive
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CIO, Application architect, Application owner, Portfolio manager.

## How to use it

Use it to review the application portfolio with owners: who owns what, what it costs, how critical it is and its TIME classification. Filter by lifecycle or owner and export it as the portfolio inventory.

## How to read it

Look for applications with no owner, no cost or no TIME: those are the data to complete first. High cost with Tolerate or Eliminate is where savings usually are; Invest with low criticality deserves a question.

## Where to find it

Open a model, **Reports › Reports**, and choose **Application portfolio inventory**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr01_application_inventory`; its dashboard is `eax-sr01`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
