---
title: VP-16 Requirements Realization view
summary: The model through the Requirements Realization view: which parts of the architecture realise each requirement. As a catalog, a matrix, a network and a heat map.
group: View
roles: user, executive
---

## What it shows

From the ArchiMate 4 Specification, Appendix C (The Open Group).

**Its concerns:** Which parts of the architecture realise each requirement. **For:** Enterprise and ICT Architects, Business Analysts, Requirements Managers. **Purpose:** Designing, deciding, informing.

**Element types shown:** Goal, Principle, Requirement, Outcome, Value, Meaning, Business Actor, Role, Collaboration, Business Interface, Application Component, Application Interface, Node, Device, System Software, Technology Interface, Communication Network, Path, Equipment, Facility, Distribution Network, Service, Process, Function, Event, Business Object, Data Object, Artifact, Material, Product, Course Of Action, Resource, Capability, Value Stream, Grouping.

**Relationships shown:** Composition, Aggregation, Assignment, Realization, Serving, Access, Influence, Association, Triggering, Flow, Specialization. The heat map colours by **Priority**.

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Solution architect, Enterprise architect, Chief Compliance Officer.

## How to use it

Use it to look at the model the way the Requirements Realization view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Requirements Realization view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp16`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
