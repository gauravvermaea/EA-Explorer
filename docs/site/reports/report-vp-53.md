---
title: VP-53 Classified information view
summary: The model through the Classified information view: the information the enterprise holds, how it is classified and where it is held. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user, executive, model-admin
---

## What it shows

**Its concerns:** The information the enterprise holds, how it is classified and where it is held. **For:** Security and data architects, data stewards. **Purpose:** Informing, deciding.

**Element types shown:** Business Object, Data Object, Data Entity, Data Domain, Application Component, Physical Application Component.

**Relationships shown:** Access, Aggregation, Composition, Association. The heat map colours by **DataClassification**.

**The TOGAF artifact it supports:** Security Classification.

**Reports that go with it:** [[report-tm-07|TM-07]], [[report-sr-04|SR-04]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Information Security Officer, Chief Data Officer, Security architect, Data steward.

## How to use it

Use it to look at the model the way the Classified information view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Classified information view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp53`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
