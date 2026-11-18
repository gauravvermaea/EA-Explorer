---
title: VP-46 Business Service/Information diagram view
summary: The model through the Business Service/Information diagram view: the information each business service uses and who uses the service. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user
---

## What it shows

**Its concerns:** The information each business service uses and who uses the service. **For:** Business and Data Architects. **Purpose:** Designing.

**Element types shown:** Service, Business Service, Business Object, Data Entity, Business Actor, Actor.

**Relationships shown:** Access, Serving, Association. The heat map colours by **DataClassification**.

**The TOGAF artifact it supports:** Business Service/Information diagram.

**Reports that go with it:** [[report-tc-06|TC-06]], [[report-tm-06|TM-06]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Business architect, Data architect.

## How to use it

Use it to look at the model the way the Business Service/Information diagram view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Business Service/Information diagram view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp46`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
