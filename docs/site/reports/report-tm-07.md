---
title: TM-07 Data security matrix
summary: Who and what accesses each item of data, with its classification: restricted and confidential data first.
group: TOGAF matrix
roles: user, executive, system-admin
---

## Why it matters

A matrix, in the TOGAF Standard's content framework, shows how two kinds of building block relate: rows of one kind, columns of the other, a mark where they are connected. It answers "what touches what" at a glance.

**In TOGAF terms:** A matrix of the TOGAF content framework (phase: C: data). See [[ea-explorer-and-togaf]].

## Who it is for

Chief Information Security Officer, Chief Data Officer, Security architect, Internal audit, Chief Compliance Officer.

## How to use it

Use it as the TOGAF Data security matrix: which items of one kind relate to which of another.

## How to read it

A filled cell is a relationship between the row and the column. Empty rows or columns are items with no link to the other kind; very full rows or columns are hubs.

## Where to find it

Open a model, **Reports › Reports**, and choose **Data security matrix**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.tm_data_security`; its dashboard is `eax-tm07`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
