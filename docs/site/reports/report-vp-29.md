---
title: VP-29 Driver/Goal/Outcome catalog view
summary: The model through the Driver/Goal/Outcome catalog view: what drives the enterprise, the goals it sets and the outcomes that show progress. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user, executive
---

## What it shows

**Its concerns:** What drives the enterprise, the goals it sets and the outcomes that show progress. **For:** CxOs, Enterprise and Business Architects. **Purpose:** Deciding, informing.

**Element types shown:** Driver, Goal, Outcome.

**Relationships shown:** Composition, Aggregation, Realization, Influence, Association, Specialization. The heat map colours by **Priority**.

**The TOGAF artifact it supports:** Driver/Goal/Outcome catalog.

**Reports that go with it:** [[report-tc-03|TC-03]], [[report-sr-08|SR-08]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

CEO, Enterprise architect.

## How to use it

Use it to look at the model the way the Driver/Goal/Outcome catalog view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Driver/Goal/Outcome catalog view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp29`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
