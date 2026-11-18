---
title: Versions, tags and merging
summary: How changes become part of a model, how you go back, and how several teams work on one model at once.
group: Versions and merging
roles: user, model-admin
---

## Every change has a history

In EA Explorer nothing is lost. A change to a model's content starts as **your uncommitted change**: only you and the
model's Committers see it. A **commit** makes it part of the model for everyone, with a message saying what and why
([[commit-your-changes]]). Every committed change keeps who, when, before and after, so any entity can be put back as
it was ([[roll-an-entity-back]]) and any commit undone ([[roll-back-a-commit]]). Review before commit is what lets an
organisation trust a model many people change.

## Tags: moments you can return to

A **tag** names a moment in a model, such as "Baseline 2026" or "Before the merger" ([[tag-a-model]]). Tags are what
projects compare (baseline against target), what KPIs are kept at, and what you go back to if needed
([[go-back-to-a-tag]]).

## Working copies and merging

For larger work, a **child model** is a working copy that can be changed freely and merged back when agreed: the
parent's admins review each change, accept or reject it, and merge it as one commit ([[merge-a-child-model-back]]).
Meanwhile the child can take the parent's newer changes ([[take-changes-from-the-parent]]). This is how a project
builds its target beside the live baseline without disturbing it.

## Read next

- [[models]]
- [[change-content-and-commit]]
