---
title: VP-56 Data lineage view
summary: The model through the Data lineage view: where information comes from, the applications it passes through and the reports and analytics it feeds. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user, executive, model-admin
---

## What it shows

**Its concerns:** Where information comes from, the applications it passes through and the reports and analytics it feeds. **For:** Data architects, analytics owners. **Purpose:** Designing, informing.

**Element types shown:** Data Object, Data Entity, Application Component, Physical Application Component.

**Relationships shown:** Flow, Access, Realization, Serving, Association. The heat map colours by **DataClassification**.

**The TOGAF artifact it supports:** Data Lineage.

**Reports that go with it:** [[report-sr-11|SR-11]], [[report-sr-04|SR-04]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Data Officer, Data architect, Data steward.

## How to use it

Use it to look at the model the way the Data lineage view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Data lineage view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp56`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
