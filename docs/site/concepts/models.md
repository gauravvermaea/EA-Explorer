---
title: Models: what they are and how they relate
summary: Root, library and project models, parents and children, architecture levels, and why a model is more than one diagram.
group: Models
roles: model-admin, user, industry-modeller, project-admin
---

## A model is a body of knowledge

A model in EA Explorer is not a diagram; it is everything known about one scope of the organisation, held as entities
and relationships on a [[metamodels|metamodel]]. Any number of diagrams, catalogues and reports can be drawn from the
same model, and they never disagree, because they read the same content.

## The kinds of model

- **Root metamodels**: a metamodel with no content, the start of a family (ArchiMate 4, TOGAF, an industry's own).
- **Library models**: reference or template models offered to everyone: the shape of a bank, a standard set of
  capabilities. Anyone may copy one or make a child of it. See [[industry-models]].
- **Project models**: the working models people fill in, usually created for or used by an architecture project.

## Families: parents and children

A model can be a **child** of another. The child is a working copy: it can be changed freely, then **merged back**
into the parent when the work is agreed ([[merge-a-child-model-back]]), and it can take the parent's later changes.
A **separate copy** has no such link. Families let several teams work at once without stepping on each other, and
let a project build its target state beside the live baseline.

## Architecture levels

Each model sits at a level of the Architecture Landscape: **strategic** (the long view of the whole enterprise),
**segment** (one area, such as claims), **capability** (one capability in detail) or **transition** (a state between
today and the target). The level decides where the model appears in the [[architecture-repository]].

## Who looks after a model

Every model has at least one **Model Admin**, who decides who may do what on it, keeps its metamodel and quality, and
runs its wizards. See [[roles-and-access]].

## Read next

- [[create-a-model]]
- [[versions-tags-and-merging]]
