---
title: What EA Explorer has for Model Admins
summary: You look after models: who works in them, their metamodel, their quality, their versions, and how they are copied, split and merged.
---

## Who this is for

People with the **Model Admin** role on a model (given on that model's People tab), and the **Model Sub Admin** who
helps them. A **Model Creator** (a global role) may make new models; a **Library Admin** looks after the model library.

## What you have

| Area | Where | What it gives you |
|---|---|---|
| Wizards | Model Admin › Wizards | Every model job guided: new model, copy, child, split, merge, freeze, extend the metamodel, hand over, tag, archive |
| Models | Model Admin › Models, and Model hierarchy | Every model you look after, and how they descend from one another |
| The model's page | Open a model | Its content (Grid, Data entry), views, quality, reports, KPIs, changes, history, tags, people and metamodel |
| The metamodel | The model's Metamodel tab; Model Admin › Metamodel drafts | Domains, entity types, attributes, pick lists, allowed relationships and rules; drafts reviewed before they are published |
| Quality | The model's Quality tab | A score, completeness, rules passed, freshness, orphans and likely duplicates, down to each entity |
| People | The model's People tab | Who may do what in this model |
| Merge requests | Architecture Work › Merge requests | Child models sent back to be merged, reviewed change by change |
| Library | Model Admin › Model library | Reference and template models to start new models from |

## How it is put together

- **A model** is a set of entities (a capability, an application, a node...) and the relationships between them, each
  of a type its metamodel allows. Every entity has an ID (for example APP-0012), its attributes, its history and its
  links.
- **The metamodel** says what a model may hold: domains (Strategy, Business, Application, Data, Technology and so on),
  entity types with their attributes, relationship types and which are allowed between which types (with how many),
  pick lists and validation rules. Every change to it is a published version with a note; children can be offered
  the new version (Push down).
- **Changes are private until committed**: what an Architect changes is their uncommitted change until a Committer
  (or the Architect, when allowed) commits it. Conflicts show at commit. Every commit can be rolled back.
- **Tags** are named moments of a model, to compare with, copy from or go back to.
- **Families**: a model can be a **copy** (on its own) or a **child** (it keeps its parent; its changes go back as a
  merge request, and the parent's changes can be pushed down to it).
- **Model roles**, highest first: Model Admin, Model Sub Admin, Committer, Architect, History Viewer, Report Viewer.

## Where to go next

- The tasks below, one page each.
- Building metamodels for a whole industry: [What EA Explorer has for industry model makers](industry-modeller.md).
