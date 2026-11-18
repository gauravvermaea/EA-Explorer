---
title: Choose where releases come from
summary: The git repository and which channels are offered.
group: Running it
roles: system-admin
screen: #/admin/updates
---

## Why do this

Releases come from a git repository and are offered by channel: production, and optionally earlier channels for testing. Choosing them decides what System Admin › Updates offers this installation. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** EA Explorer offers the releases you want, from where you want.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Updates**, **Repository and channels**.
2. Paste the public git link (https); tick the channels.
3. **Save**.
