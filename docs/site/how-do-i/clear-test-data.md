---
title: Clear the self-test's data
summary: Remove test fixtures and results for good.
group: Running it
roles: system-admin
screen: #/admin/self-test
---

## Why do this

The self-test makes its own models, projects and accounts to test in, so nothing real is touched. Clearing them when you no longer need their evidence keeps the database lean.

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** Old self-test data no longer takes up space.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Tools › Self-test**, **Test data**.
2. Tick what to remove.
3. Type DELETE to confirm; this cannot be undone.
