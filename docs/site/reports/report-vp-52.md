---
title: VP-52 Security requirements view
summary: The model through the Security requirements view: the security requirements, what they protect and the controls and parts of the architecture that meet them. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user, executive
---

## What it shows

**Its concerns:** The security requirements, what they protect and the controls and parts of the architecture that meet them. **For:** Security architects, solution architects. **Purpose:** Designing, deciding.

**Element types shown:** Security Requirement, Control, Application Component, Node, System Software, Data Object, Business Object, Service, Physical Application Component, Data Entity.

**Relationships shown:** Realization, Association. The heat map colours by **SecurityProperty**.

**The TOGAF artifact it supports:** Security Requirements.

**Reports that go with it:** [[report-tc-04|TC-04]], [[report-tm-07|TM-07]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Information Security Officer, Security architect, Solution architect.

## How to use it

Use it to look at the model the way the Security requirements view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Security requirements view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp52`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
