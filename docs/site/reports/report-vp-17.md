---
title: VP-17 Motivation view
summary: The model through the Motivation view: the whole motivation of the enterprise: stakeholders, drivers, assessments, goals, outcomes, principles, requirements, meanings and values. As a catalog, a matrix, a network and a heat map.
group: View
roles: user, executive
---

## What it shows

From the ArchiMate 4 Specification, Appendix C (The Open Group).

**Its concerns:** The whole motivation of the enterprise: stakeholders, drivers, assessments, goals, outcomes, principles, requirements, meanings and values. **For:** Enterprise and ICT Architects, Business Analysts, Requirements Managers. **Purpose:** Designing, deciding, informing.

**Element types shown:** Stakeholder, Driver, Assessment, Goal, Principle, Requirement, Outcome, Value, Meaning, Grouping.

**Relationships shown:** Composition, Aggregation, Realization, Influence, Association, Specialization. The heat map colours by **Priority**.

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

CEO, Architecture board, Enterprise architect.

## How to use it

Use it to look at the model the way the Motivation view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Motivation view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp17`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
