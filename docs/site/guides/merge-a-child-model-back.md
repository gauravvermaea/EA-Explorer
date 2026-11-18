---
title: Merge a child model back
summary: A child's changes sent to its parent, reviewed change by change, and merged as one commit.
group: Versions and merging
roles: model-admin
---

## Why do this

Merging brings a working copy's changes back into the live model after review, so teams can work apart and still end up with one model. See [[versions-tags-and-merging]].

Nothing in EA Explorer is lost: every change is kept, moments can be named, and work can happen in copies that merge back after review. This is what lets many people change one model without fear.

**In TOGAF terms:** Phase H and the Architecture Repository: change to the baseline is controlled, recorded and reversible. See [[ea-explorer-and-togaf]].

**The goal:** A child's agreed work is in the parent.

> **Before you start** You need Model Admin on the child to send, and Model Admin or Committer on the parent to review.

## The ways to do it

1. On the child: Model Admin › Wizards, **Send for merge into the parent**. It shows what changed since its starting
   point; add a note and send.
2. On the parent: Architecture Work › **Merge requests**, open the request. Where both changed the same thing, it is a
   conflict.
3. Accept or reject each change (a reason for each rejection), then **merge** it as one commit. A merge report can be
   downloaded in Word.
4. Then the child is frozen, or refreshed from the parent to carry on.

## Each task, one page

1. [Send a child model for merge](../how-do-i/send-a-child-for-merge.md)
2. [Review a merge request](../how-do-i/review-a-merge-request.md)
3. [Take changes from the parent](../how-do-i/take-changes-from-the-parent.md)
4. [Freeze a model](../how-do-i/freeze-a-model.md)

## Related

- [Tag a model and compare](../guides/tag-and-compare.md)
