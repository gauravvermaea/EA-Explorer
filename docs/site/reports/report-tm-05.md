---
title: TM-05 Location matrix
summary: What is at each location.
group: TOGAF matrix
roles: user, executive, system-admin
---

## What it shows

**Rows:** Location. **Columns:** Business Actor, Role, Collaboration, Business Interface, Application Component, Application Interface, Node, Device, System Software, Technology Interface, Communication Network, Path, Equipment, Facility, Distribution Network, Service, Process, Function, Event, Business Object, Data Object, Artifact, Material, Product, Capability.

## Why it matters

A matrix, in the TOGAF Standard's content framework, shows how two kinds of building block relate: rows of one kind, columns of the other, a mark where they are connected. It answers "what touches what" at a glance.

**In TOGAF terms:** A matrix of the TOGAF content framework (phase: B to D). See [[ea-explorer-and-togaf]].

## Who it is for

COO, Technology architect, IT operations.

## How to use it

Use it as the TOGAF Location matrix: which items of one kind relate to which of another.

## How to read it

A filled cell is a relationship between the row and the column. Empty rows or columns are items with no link to the other kind; very full rows or columns are hubs.

## Where to find it

Open a model, **Reports › Reports**, and choose **Location matrix**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.type_pairs`; its dashboard is `eax-tm05`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
