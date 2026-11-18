---
title: Accept a pairing on the receiving site
summary: Let another site start sending to this one.
group: Running it
roles: system-admin
screen: #/admin/pairings
---

## Why do this

A pairing links two EA Explorer sites so one sends to the other: content between environments, or everything to a disaster recovery site. Nothing is sent until the receiving site accepts, so a site can never be filled by someone else without its admins agreeing. See [[backups-and-recovery]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** The other site may start sending to this one.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. On the receiving site: **System Admin › Site pairings**.
2. Open the pairing waiting; check where it comes from.
3. **Accept**. For DR sync this site becomes read only.
