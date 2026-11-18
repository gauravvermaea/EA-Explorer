---
title: VP-35 Process/Event/Control/Product catalog view
summary: The model through the Process/Event/Control/Product catalog view: the processes, the events that start them, the controls on them and the products they deliver. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user, executive
---

## What it shows

**Its concerns:** The processes, the events that start them, the controls on them and the products they deliver. **For:** Process owners, Business Architects, risk. **Purpose:** Designing, informing.

**Element types shown:** Process, Event, Control, Product.

**Relationships shown:** Composition, Aggregation, Assignment, Realization, Serving, Access, Influence, Association, Triggering, Flow, Specialization. The heat map colours by **Lifecycle**.

**The TOGAF artifact it supports:** Process/Event/Control/Product catalog.

**Reports that go with it:** [[report-sr-05|SR-05]], [[report-tc-06|TC-06]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Process owner, Business architect, Chief Risk Officer.

## How to use it

Use it to look at the model the way the Process/Event/Control/Product catalog view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Process/Event/Control/Product catalog view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp35`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
