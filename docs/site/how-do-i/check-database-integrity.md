---
title: Check the database's integrity
summary: Indexes, tables, constraints and sequences checked; safe fixes only when switched on.
group: Running it
roles: system-admin
screen: #/admin/db-maintenance
---

## Why do this

Integrity checks look for problems under the surface: broken indexes, constraint breaches, sequences out of step. They run weekly and after every restore; running one now is wise before an upgrade or after an incident. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** You know the databases are sound.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Database maintenance**.
2. **Check the integrity now**.
3. Read the findings; anything that touches rows waits for a Super Admin.
