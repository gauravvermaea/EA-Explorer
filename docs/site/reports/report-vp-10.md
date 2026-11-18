---
title: VP-10 Process Cooperation view
summary: The model through the Process Cooperation view: how business processes work together, what triggers them and what they exchange. As a catalog, a matrix, a network and a heat map.
group: View
roles: user, executive
---

## What it shows

From the ArchiMate 4 Specification, Appendix C (The Open Group).

**Its concerns:** How business processes work together, what triggers them and what they exchange. **For:** Process and Domain Architects, Operational Managers. **Purpose:** Designing, deciding.

**Element types shown:** Business Actor, Role, Collaboration, Location, Business Interface, Process, Function, Event, Service, Business Object, Application Component, Application Interface, Data Object, Grouping.

**Relationships shown:** Composition, Aggregation, Assignment, Realization, Serving, Access, Influence, Association, Triggering, Flow, Specialization. The heat map colours by **Lifecycle**.

**The TOGAF artifact it supports:** Process Flow diagram.

**Reports that go with it:** [[report-sr-05|SR-05]], [[report-sr-13|SR-13]], [[report-tm-12|TM-12]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Process owner, COO, Business architect.

## How to use it

Use it to look at the model the way the Process Cooperation view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Process Cooperation view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp10`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
