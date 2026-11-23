---
title: VP-50 Risk register view
summary: The model through the Risk register view: every risk with its likelihood, impact, owner, treatment and the risk left after the controls. As a catalog, a matrix, a network and a heat map. EA Explorer's own view.
group: View
roles: user, executive, system-admin
---

## What it shows

**Its concerns:** Every risk with its likelihood, impact, owner, treatment and the risk left after the controls. **For:** Risk and security architects, the Architecture Board, risk owners. **Purpose:** Deciding, informing.

**Element types shown:** Assessment, Control, Driver.

**Relationships shown:** Influence, Association. The heat map colours by **ResidualRisk**.

**The TOGAF artifact it supports:** Risk Register.

**Reports that go with it:** [[report-sr-23|SR-23]], [[report-tc-04|TC-04]].

## Why it matters

Views from the ArchiMate 4 Specification each serve a set of stakeholders and concerns, by showing only the element and relationship types that matter to them. EA Explorer shows each one from your model as a catalogue, a matrix, a network and a heat map.

**In TOGAF terms:** An architecture view, addressing stakeholders' concerns; it usually supports the TOGAF artifact named below. See [[ea-explorer-and-togaf]].

## Who it is for

Chief Risk Officer, Chief Information Security Officer, Security architect, Architecture board, Internal audit.

## How to use it

Use it to look at the model the way the Risk register view's stakeholders need: only the element and relationship types that matter to their concerns.

## How to read it

The catalog lists the elements, the relationships table shows how they connect, and the heat map colours elements by the view's attribute. Missing elements of a type mean that part is not modelled yet.

## Where to find it

Open a model, **Reports › Reports**, and choose **Risk register view**; it opens its dashboard for that model. Every chart can be filtered, and most rows have **Open** to go to the entity in EA Explorer. The same data is in the model's OData feed for your own tools ([[odata-feeds]]).

For developers and report builders: it reads `rpt.vp_elements`; its dashboard is `eax-vp50`.

## Related

- [[views-and-reports]]
- [[open-a-standard-report]]
- [[build-your-own-report]]
