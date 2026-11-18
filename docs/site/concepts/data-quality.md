---
title: Data quality: why it matters and how it is measured
summary: What good architecture data looks like, what goes wrong without it, and how EA Explorer scores and improves it.
group: Data quality
roles: model-admin, user, executive
---

## Why it matters

A repository is only worth what its data is worth. If owners are missing, a question about accountability has no
answer. If lifecycle dates are stale, a retirement plan is built on yesterday. If the same application is recorded
three times, impact analysis misses two thirds of the dependencies. People notice quickly when a repository is wrong,
and then they stop using it, and it decays further. Data quality is what keeps the repository trusted.

## What good looks like

- **Complete**: the attributes that matter are filled in (owner, status, cost where it is asked for).
- **Correct**: values follow the rules (a retirement date after the go-live date, an allowed value from the list).
- **Current**: entities have been looked at recently; nothing has gone stale.
- **Connected**: entities are related to what they should be; no orphans.
- **Unique**: each real thing is recorded once.

## How EA Explorer measures and improves it

Each model has a **quality score** built from those five, with weights its Model Admin sets
([[see-a-models-quality-score]], [[set-how-quality-is-measured]]). **Rules** check values as they are saved: an error
blocks a commit, a warning does not ([[add-a-quality-rule]], [[see-failing-checks]]). A **wizard** walks through what
is missing one entity at a time ([[run-the-data-quality-wizard]]), **duplicates** are found and merged
([[find-and-merge-duplicates]]), and System Admins see every model's score side by side ([[see-quality-across-models]]).

## Read next

- [[improve-data-quality]]
- [[metamodels]]
