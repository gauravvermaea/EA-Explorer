---
title: TM-06 Data entity and business function matrix
summary: Which processes and functions create, read, update or delete which data.
group: TOGAF matrix
roles: user, executive
---

## What it shows

**Rows:** Process, Function. **Columns:** Business Object, Data Object.

## Why it matters

A matrix, in the TOGAF Standard's content framework, shows how two kinds of building block relate: rows of one kind, columns of the other, a mark where they are connected. It answers "what touches what" at a glance.

**In TOGAF terms:** A matrix of the TOGAF content framework (phase: C: data). See [[ea-explorer-and-togaf]].

## Who it is for

Chief Data Officer, Data architect, Process owner.

## How to use it

Use it as the TOGAF Data entity and business function matrix: which items of one kind relate to which of another.

## How to read it

A filled cell is a relationship between the row and the column. Empty rows or columns are items with no link to the other kind; very full rows or columns are hubs.

## Where to find it

Open a model, **Reports › Reports**, and choose **Data entity and business function matrix**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.type_pairs`; its dashboard is `eax-tm06`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
