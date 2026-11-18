---
title: Watch a self-test as it runs
summary: The step running now, the counts and each result as it comes.
group: Running it
roles: system-admin, platform-developer
screen: #/admin/self-test/watch
---

## Why do this

A full self-test takes a while. Watching it shows each step and result as it comes, so after an update or while chasing a fault you see the first failure at once instead of waiting for the report.

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** You see a self-test as it runs.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Tools › Self-test** and the run.
2. **Watch**: follow each step.
3. **Stop** asks first; it keeps what it found.
