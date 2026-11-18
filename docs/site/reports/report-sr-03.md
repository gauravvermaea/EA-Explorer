---
title: SR-03 Technology component inventory
summary: Technology components with version, vendor, lifecycle and end of life.
group: Standard
roles: user, executive, system-admin
---

## Why it matters

The standard reports answer the questions most architecture practices are asked again and again: what we have, what it costs, how it depends on what, and where the risks are. They work on any model built on a metamodel with the matching types and attributes.

**In TOGAF terms:** Architecture views and catalogues that address common stakeholder concerns, in phases B to F. See [[ea-explorer-and-togaf]].

## Who it is for

CTO, Technology architect, IT operations.

## How to use it

Use it to keep the technology inventory current and plan upgrades.

## How to read it

Check the end-of-life dates: anything past or within the next year needs a plan (see [[report-sr-17|SR-17]] and [[report-sr-23|SR-23]]). Missing versions or vendors mean the inventory cannot inform support-contract or risk decisions yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Technology component inventory**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.sr03_technology_inventory`; its dashboard is `eax-sr03`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
