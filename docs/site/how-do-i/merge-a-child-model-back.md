---
title: Merge a child model back
summary: A child's changes sent to its parent, reviewed change by change, and merged as one commit.
group: Versions and merging
roles: model-admin
---

> **Before you start** You need Model Admin on the child to send, and Model Admin or Committer on the parent to review.

## Steps

1. On the child: Model Admin › Wizards, **Send for merge into the parent**. It shows what changed since its starting
   point; add a note and send.
2. On the parent: Architecture Work › **Merge requests**, open the request. Where both changed the same thing, it is a
   conflict.
3. Accept or reject each change (a reason for each rejection), then **merge** it as one commit. A merge report can be
   downloaded in Word.
4. Then the child is frozen, or refreshed from the parent to carry on.

## Related

- [Tag a model and compare](tag-and-compare.md)
