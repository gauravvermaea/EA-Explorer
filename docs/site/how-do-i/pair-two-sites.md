---
title: Pair two sites
summary: One site sends content, or everything for DR, to another.
group: Running it
roles: system-admin
screen: #/admin/pairings
---

## Why do this

Pairing keeps two sites in step: content from one environment to another, or everything to a disaster recovery site that can take over. See [[backups-and-recovery]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** One site sends content, or everything, to another.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. On the receiving site: **System Admin › Site pairings**, **Make a pairing key**; copy it.
2. On the sending site: **Pair with a site**: its address and the key.
3. Choose content sync or DR sync; **Pair**.
