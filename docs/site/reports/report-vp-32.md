---
title: VP-32 Value Stream catalog view
summary: The model through the Value Stream catalog view: the value streams the enterprise runs and who they serve. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user
---

## What it shows

**Its concerns:** The value streams the enterprise runs and who they serve. **For:** Business Architects, product owners. **Purpose:** Informing.

**Element types shown:** Value Stream.

**Relationships shown:** Composition, Aggregation, Assignment, Realization, Serving, Access, Influence, Association, Triggering, Flow, Specialization. The heat map colours by **Owner**.

**The TOGAF artifact it supports:** Value Stream catalog.

**Reports that go with it:** [[report-sr-14|SR-14]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Business architect, Product owner.

## How to use it

Use it to look at the model the way the Value Stream catalog view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Value Stream catalog view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp32`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
