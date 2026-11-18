---
title: Metamodels: the shape of a model
summary: What a metamodel is, why every model has one, the kinds EA Explorer offers, and how one changes safely.
group: Models
roles: model-admin, industry-modeller, user, developer
---

## What a metamodel is

A metamodel is the model of a model: it says what a model may contain. It lists the **entity types** (Capability,
Application Component, Business Process...), the **attributes** each type has (owner, cost, lifecycle status, a pick
list of values), and the **relationships** allowed between types (an Application Component may serve a Business
Process; a Capability may be composed of other Capabilities). It also groups types into **domains** (business, data,
application, technology, motivation) with a colour each.

## Why it matters

The metamodel is what makes a repository more than a drawing tool. Because every model follows its metamodel:

- people put the same kind of thing in the same place, so a question can be answered across the whole model;
- only meaningful relationships can be drawn, so impact analysis follows real dependencies;
- reports, views and data quality rules can be written once and work on every model built on the same metamodel;
- data from other systems can be checked before it loads.

A loose metamodel lets anything in and answers little; a strict one answers a lot but asks more of the people filling
it in. Choosing the balance is the Model Admin's job.

## The kinds you will meet

- **ArchiMate 4**: The Open Group's modelling language, a rich general-purpose metamodel.
- **The TOGAF content metamodel**: the entities the TOGAF Standard's deliverables talk about.
- **Industry metamodels**: banking, insurance, government and others, from the [[industry-models]] in the library.
- **Your own**: built in Excel ([[build-a-metamodel-in-excel]]) or by extending another ([[extend-from-another-model]]).

Models made from the same root share its metamodel; a child model inherits its parent's and can take its later
changes ([[take-changes-from-the-parent]]).

## Changing a metamodel safely

A change to a metamodel changes what everyone may record, so it is reviewed: it starts as a **draft**
([[start-a-metamodel-draft]]), is reviewed and accepted ([[review-a-metamodel-draft]]), and becomes a new version of
the metamodel with its note. Any two versions can be compared. See [[change-a-metamodel]].

## Read next

- [[models]]
- [[data-quality]]
