---
title: Review a merge request
summary: Accept or reject, change by change, what a child sent.
group: Versions and merging
roles: model-admin
screen: #/merge-requests
---

## Why do this

A merge request carries a child model's changes back to its parent. Reviewing each change, accepting or rejecting with a reason, is what keeps the parent trustworthy. See [[versions-tags-and-merging]].

Nothing in EA Explorer is lost: every change is kept, moments can be named, and work can happen in copies that merge back after review. This is what lets many people change one model without fear.

**In TOGAF terms:** Phase H and the Architecture Repository: change to the baseline is controlled, recorded and reversible. See [[ea-explorer-and-togaf]].

**The goal:** A child's changes are checked before they reach the parent.

> **Before you start** You need the Model Admin role on the model. (on the parent)

## Steps

1. Open **Architecture Work › Merge requests**.
2. Open the request; accept or reject each change, with a reason.
3. **Merge**: the parent is tagged first.
